from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.services.calculator import EarlyPaymentInput, LoanParams


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    yandex_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    login: Mapped[str] = mapped_column(String(255), default="")
    display_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", server_default="Europe/Moscow")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    debts: Mapped[list["Debt"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """Серверная сессия. В cookie лежит случайный токен, в БД — только его SHA-256."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    principal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    annual_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    term_months: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    first_payment_date: Mapped[date] = mapped_column(Date)
    schedule_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="debts")
    early_payments: Mapped[list["EarlyPayment"]] = relationship(
        back_populates="debt", cascade="all, delete-orphan", lazy="selectin", order_by="EarlyPayment.date"
    )
    paid_periods: Mapped[list["PaidPeriod"]] = relationship(
        back_populates="debt", cascade="all, delete-orphan", lazy="selectin"
    )

    def loan_params(self) -> LoanParams:
        return LoanParams(
            principal=Decimal(self.principal),
            annual_rate=Decimal(self.annual_rate),
            term_months=self.term_months,
            start_date=self.start_date,
            first_payment_date=self.first_payment_date,
            schedule_type=self.schedule_type,  # type: ignore[arg-type]
        )

    def early_inputs(self) -> list[EarlyPaymentInput]:
        return [
            EarlyPaymentInput(date=ep.date, amount=Decimal(ep.amount), mode=ep.mode, id=ep.id)  # type: ignore[arg-type]
            for ep in self.early_payments
        ]

    def paid_set(self) -> set[int]:
        return {p.period_no for p in self.paid_periods}


class EarlyPayment(Base):
    __tablename__ = "early_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    mode: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    debt: Mapped[Debt] = relationship(back_populates="early_payments")


class PaidPeriod(Base):
    __tablename__ = "paid_periods"

    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"), primary_key=True)
    period_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    debt: Mapped[Debt] = relationship(back_populates="paid_periods")
