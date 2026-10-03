from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, Session
from app.models import Debt, EarlyPayment, PaidPeriod, User
from app.schemas import DebtCreate, DebtOut, DebtUpdate, EarlyPaymentCreate, LoanIn, ScheduleOut
from app.services.calculator import EarlyPaymentInput, LoanParams, build_schedule
from app.services.debt_view import debt_out, row_out, schedule_out, summary_out, today_for
from app.services.summary import summarize

router = APIRouter(tags=["debts"])

# id-заглушка для ещё не сохранённого досрочного платежа: сортируется последним среди платежей той же даты
_PENDING_EARLY_ID = 2**62
_UNPROCESSABLE = 422


async def _get_debt(session: AsyncSession, user: User, debt_id: int) -> Debt:
    debt = await session.scalar(
        select(Debt)
        .where(Debt.id == debt_id, Debt.user_id == user.id)
        .execution_options(populate_existing=True)
    )
    if debt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Долг не найден")
    return debt


async def _drop_stale_paid_marks(session: AsyncSession, debt: Debt) -> None:
    """Удаляет отметки об оплате периодов, которых больше нет в графике (срок сократился)."""
    rows = build_schedule(debt.loan_params(), debt.early_inputs())
    last_period = max((r.period_no for r in rows if r.period_no is not None), default=0)
    await session.execute(
        delete(PaidPeriod).where(PaidPeriod.debt_id == debt.id, PaidPeriod.period_no > last_period)
    )


@router.post("/calculate", response_model=ScheduleOut)
async def calculate(payload: LoanIn, user: CurrentUser) -> ScheduleOut:
    today = today_for(user)
    params = LoanParams(**payload.model_dump())
    rows = build_schedule(params)
    summary = summarize(params.principal, rows, set(), today)
    return ScheduleOut(rows=[row_out(r, set(), today) for r in rows], summary=summary_out(summary, set(), today))


@router.get("/debts", response_model=list[DebtOut])
async def list_debts(user: CurrentUser, session: Session) -> list[DebtOut]:
    debts = await session.scalars(select(Debt).where(Debt.user_id == user.id).order_by(Debt.created_at, Debt.id))
    today = today_for(user)
    return [debt_out(d, today) for d in debts]


@router.post("/debts", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
async def create_debt(payload: DebtCreate, user: CurrentUser, session: Session) -> DebtOut:
    debt = Debt(user_id=user.id, **payload.model_dump())
    session.add(debt)
    await session.commit()
    return debt_out(await _get_debt(session, user, debt.id), today_for(user))


@router.get("/debts/{debt_id}", response_model=DebtOut)
async def get_debt(debt_id: int, user: CurrentUser, session: Session) -> DebtOut:
    return debt_out(await _get_debt(session, user, debt_id), today_for(user))


@router.patch("/debts/{debt_id}", response_model=DebtOut)
async def update_debt(debt_id: int, payload: DebtUpdate, user: CurrentUser, session: Session) -> DebtOut:
    debt = await _get_debt(session, user, debt_id)
    debt.name = payload.name
    await session.commit()
    return debt_out(await _get_debt(session, user, debt_id), today_for(user))


@router.delete("/debts/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(debt_id: int, user: CurrentUser, session: Session) -> Response:
    debt = await _get_debt(session, user, debt_id)
    await session.delete(debt)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/debts/{debt_id}/schedule", response_model=ScheduleOut)
async def get_schedule(debt_id: int, user: CurrentUser, session: Session) -> ScheduleOut:
    return schedule_out(await _get_debt(session, user, debt_id), today_for(user))


@router.put("/debts/{debt_id}/periods/{period_no}/paid", response_model=ScheduleOut)
async def mark_paid(debt_id: int, period_no: int, user: CurrentUser, session: Session) -> ScheduleOut:
    debt = await _get_debt(session, user, debt_id)
    rows = build_schedule(debt.loan_params(), debt.early_inputs())
    if not any(r.period_no == period_no for r in rows):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Такого периода нет в графике")
    if period_no not in debt.paid_set():
        session.add(PaidPeriod(debt_id=debt.id, period_no=period_no))
        await session.commit()
    return schedule_out(await _get_debt(session, user, debt_id), today_for(user))


@router.delete("/debts/{debt_id}/periods/{period_no}/paid", response_model=ScheduleOut)
async def unmark_paid(debt_id: int, period_no: int, user: CurrentUser, session: Session) -> ScheduleOut:
    debt = await _get_debt(session, user, debt_id)
    await session.execute(
        delete(PaidPeriod).where(PaidPeriod.debt_id == debt.id, PaidPeriod.period_no == period_no)
    )
    await session.commit()
    return schedule_out(await _get_debt(session, user, debt_id), today_for(user))


@router.post("/debts/{debt_id}/early-payments", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def add_early_payment(
    debt_id: int, payload: EarlyPaymentCreate, user: CurrentUser, session: Session
) -> ScheduleOut:
    debt = await _get_debt(session, user, debt_id)
    if payload.date < debt.start_date:
        raise HTTPException(_UNPROCESSABLE, "Дата досрочного платежа раньше даты выдачи")

    candidate = EarlyPaymentInput(date=payload.date, amount=payload.amount, mode=payload.mode, id=_PENDING_EARLY_ID)
    rows = build_schedule(debt.loan_params(), [*debt.early_inputs(), candidate])
    applied = next((r for r in rows if r.early_payment_id == _PENDING_EARLY_ID), None)
    if applied is None:
        raise HTTPException(_UNPROCESSABLE, "К этой дате долг уже погашен")
    if applied.payment < payload.amount:
        raise HTTPException(
            _UNPROCESSABLE,
            f"Сумма больше необходимой для полного погашения на эту дату. Максимум: {applied.payment:.2f}",
        )

    session.add(EarlyPayment(debt_id=debt.id, date=payload.date, amount=payload.amount, mode=payload.mode))
    await session.commit()
    debt = await _get_debt(session, user, debt_id)
    await _drop_stale_paid_marks(session, debt)
    await session.commit()
    return schedule_out(await _get_debt(session, user, debt_id), today_for(user))


@router.delete("/debts/{debt_id}/early-payments/{early_payment_id}", response_model=ScheduleOut)
async def delete_early_payment(
    debt_id: int, early_payment_id: int, user: CurrentUser, session: Session
) -> ScheduleOut:
    debt = await _get_debt(session, user, debt_id)
    result = await session.execute(
        delete(EarlyPayment).where(EarlyPayment.id == early_payment_id, EarlyPayment.debt_id == debt.id)
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Досрочный платёж не найден")
    await session.commit()
    debt = await _get_debt(session, user, debt_id)
    await _drop_stale_paid_marks(session, debt)
    await session.commit()
    return schedule_out(await _get_debt(session, user, debt_id), today_for(user))
