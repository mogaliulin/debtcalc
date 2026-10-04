"""Сборка ответов API: вычисляет график долга и накладывает отметки об оплате."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models import Debt, User
from app.schemas import DebtOut, EarlyPaymentOut, ScheduleOut, ScheduleRowOut, SummaryOut
from app.services.access import Role
from app.services.calculator import ScheduleRow, build_schedule
from app.services.summary import ScheduleSummary, summarize


def today_for(user: User) -> date:
    try:
        return datetime.now(ZoneInfo(user.timezone)).date()
    except Exception:
        return date.today()


def row_out(row: ScheduleRow, paid: set[int], today: date) -> ScheduleRowOut:
    is_paid = row.kind == "early" or row.period_no in paid
    return ScheduleRowOut(
        period_no=row.period_no,
        date=row.date,
        kind=row.kind,
        payment=row.payment,
        interest=row.interest,
        principal=row.principal,
        balance_after=row.balance_after,
        is_paid=is_paid,
        is_overdue=not is_paid and row.date < today,
        early_payment_id=row.early_payment_id,
        early_mode=row.early_mode,
    )


def summary_out(summary: ScheduleSummary, paid: set[int], today: date) -> SummaryOut:
    return SummaryOut(
        principal=summary.principal,
        remaining_balance=summary.remaining_balance,
        total_payments=summary.total_payments,
        total_interest=summary.total_interest,
        close_date=summary.close_date,
        periods_count=summary.periods_count,
        paid_count=summary.paid_count,
        overdue_count=summary.overdue_count,
        next_payment=row_out(summary.next_payment, paid, today) if summary.next_payment else None,
        progress=summary.progress,
        is_closed=summary.is_closed,
    )


def compute(debt: Debt, today: date) -> tuple[list[ScheduleRow], ScheduleSummary, set[int]]:
    rows = build_schedule(debt.loan_params(), debt.early_inputs())
    paid = debt.paid_set()
    return rows, summarize(debt.loan_params().principal, rows, paid, today), paid


def debt_out(debt: Debt, today: date, role: Role) -> DebtOut:
    _, summary, paid = compute(debt, today)
    return DebtOut(
        id=debt.id,
        name=debt.name,
        principal=debt.principal,
        annual_rate=debt.annual_rate,
        term_months=debt.term_months,
        start_date=debt.start_date,
        first_payment_date=debt.first_payment_date,
        schedule_type=debt.schedule_type,  # type: ignore[arg-type]
        early_payments=[EarlyPaymentOut.model_validate(ep) for ep in debt.early_payments],
        summary=summary_out(summary, paid, today),
        owner_id=debt.user_id,
        role=role,
    )


def schedule_out(debt: Debt, today: date) -> ScheduleOut:
    rows, summary, paid = compute(debt, today)
    return ScheduleOut(
        rows=[row_out(r, paid, today) for r in rows],
        summary=summary_out(summary, paid, today),
    )
