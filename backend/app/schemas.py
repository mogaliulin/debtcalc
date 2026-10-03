from datetime import date
from decimal import Decimal
from typing import Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ScheduleType = Literal["annuity", "differentiated"]
EarlyMode = Literal["reduce_term", "reduce_payment"]


class LoanIn(BaseModel):
    principal: Decimal = Field(gt=0, le=Decimal("1000000000000"), decimal_places=2)
    annual_rate: Decimal = Field(ge=0, le=999, decimal_places=3)
    term_months: int = Field(ge=1, le=600)
    start_date: date
    first_payment_date: date
    schedule_type: ScheduleType = "annuity"

    @model_validator(mode="after")
    def check_dates(self) -> "LoanIn":
        if self.first_payment_date <= self.start_date:
            raise ValueError("Дата первого платежа должна быть позже даты выдачи")
        if (self.first_payment_date - self.start_date).days > 366:
            raise ValueError("Первый платёж не может быть позже чем через год после выдачи")
        return self


class DebtCreate(LoanIn):
    name: str = Field(min_length=1, max_length=100)


class DebtUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EarlyPaymentCreate(BaseModel):
    date: date
    amount: Decimal = Field(gt=0, le=Decimal("1000000000000"), decimal_places=2)
    mode: EarlyMode


class EarlyPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    amount: Decimal
    mode: EarlyMode


class ScheduleRowOut(BaseModel):
    period_no: int | None
    date: date
    kind: Literal["regular", "early"]
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance_after: Decimal
    is_paid: bool
    is_overdue: bool
    early_payment_id: int | None = None
    early_mode: EarlyMode | None = None


class SummaryOut(BaseModel):
    principal: Decimal
    remaining_balance: Decimal
    total_payments: Decimal
    total_interest: Decimal
    close_date: date | None
    periods_count: int
    paid_count: int
    overdue_count: int
    next_payment: ScheduleRowOut | None
    progress: float
    is_closed: bool


class DebtOut(BaseModel):
    id: int
    name: str
    principal: Decimal
    annual_rate: Decimal
    term_months: int
    start_date: date
    first_payment_date: date
    schedule_type: ScheduleType
    early_payments: list[EarlyPaymentOut]
    summary: SummaryOut


class ScheduleOut(BaseModel):
    rows: list[ScheduleRowOut]
    summary: SummaryOut


class UserOut(BaseModel):
    id: int
    login: str
    display_name: str
    email: str | None
    avatar_url: str | None
    timezone: str


class UserUpdate(BaseModel):
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("Неизвестный часовой пояс")
        return value
