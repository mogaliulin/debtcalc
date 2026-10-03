"""Расчёт графика платежей по кредиту.

Чистые функции без обращения к БД: на вход параметры кредита и досрочные платежи,
на выход — список строк графика. График никогда не хранится, а пересчитывается
при каждом запросе, поэтому удаление ошибочного досрочного платежа — это просто
удаление входной записи.

Правила расчёта:
* даты платежей — first_payment_date + k месяцев, день клампится к концу месяца;
* проценты начисляются по дням: остаток × ставка × дни / (365 | 366);
* аннуитетный платёж считается по месячной ставке (ставка / 12), последний
  платёж корректируется так, чтобы остаток стал ровно нулевым;
* досрочный платёж сначала гасит проценты, накопленные к его дате, остаток идёт
  в тело долга; если дата совпадает с датой регулярного платежа — применяется
  после него;
* reduce_term — платёж (аннуитет) / тело (дифф.) прежние, срок сокращается;
  reduce_payment — срок прежний, платёж пересчитывается.
"""

from __future__ import annotations

import calendar
import copy
import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Literal, Sequence

ScheduleType = Literal["annuity", "differentiated"]
EarlyMode = Literal["reduce_term", "reduce_payment"]
RowKind = Literal["regular", "early"]

CENT = Decimal("0.01")
ZERO = Decimal("0")
MAX_PERIODS = 1200


@dataclass(frozen=True)
class LoanParams:
    principal: Decimal
    annual_rate: Decimal  # в процентах, например 12.5
    term_months: int
    start_date: date
    first_payment_date: date
    schedule_type: ScheduleType


@dataclass(frozen=True)
class EarlyPaymentInput:
    date: date
    amount: Decimal
    mode: EarlyMode
    id: int | None = None


@dataclass(frozen=True)
class ScheduleRow:
    period_no: int | None  # только для регулярных платежей
    date: date
    kind: RowKind
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance_after: Decimal
    early_payment_id: int | None = None
    early_mode: EarlyMode | None = None


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def add_months(base: date, months: int, day: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def accrue_interest(balance: Decimal, annual_rate: Decimal, start: date, end: date) -> Decimal:
    """Проценты за [start, end) по дням с учётом високосных лет. Без округления."""
    if end <= start or balance <= 0 or annual_rate == 0:
        return ZERO
    rate = annual_rate / 100
    total = ZERO
    cursor = start
    while cursor < end:
        segment_end = min(end, date(cursor.year + 1, 1, 1))
        days_in_year = 366 if calendar.isleap(cursor.year) else 365
        total += balance * rate * (segment_end - cursor).days / days_in_year
        cursor = segment_end
    return total


def annuity_payment(balance: Decimal, monthly_rate: Decimal, periods: int) -> Decimal:
    if periods <= 0:
        return money(balance)
    if monthly_rate == 0:
        return money(balance / periods)
    growth = (1 + monthly_rate) ** periods
    return money(balance * monthly_rate * growth / (growth - 1))


def annuity_periods_needed(balance: Decimal, monthly_rate: Decimal, payment: Decimal) -> int | None:
    """Сколько периодов нужно, чтобы погасить balance фиксированным платежом."""
    if payment <= 0:
        return None
    if monthly_rate == 0:
        return max(1, math.ceil(balance / payment))
    remainder = 1 - float(balance * monthly_rate / payment)
    if remainder <= 0:
        return None  # платёж не покрывает проценты
    periods = -math.log(remainder) / math.log(1 + float(monthly_rate))
    return max(1, math.ceil(periods - 1e-9))


class _Engine:
    def __init__(self, loan: LoanParams) -> None:
        self.loan = loan
        self.monthly_rate = loan.annual_rate / 100 / 12
        self.balance = loan.principal
        self.planned_last = loan.term_months
        self.cursor = loan.start_date  # проценты начислены и учтены по эту дату
        self.carry = ZERO  # начисленные, но не погашенные проценты
        self.payment = annuity_payment(self.balance, self.monthly_rate, self.planned_last)
        self.principal_part = money(self.balance / self.planned_last)
        self.rows: list[ScheduleRow] = []

    @property
    def is_annuity(self) -> bool:
        return self.loan.schedule_type == "annuity"

    def payment_date(self, period_no: int) -> date:
        first = self.loan.first_payment_date
        return add_months(first, period_no - 1, first.day)

    def run(self, early_payments: Iterable[EarlyPaymentInput]) -> list[ScheduleRow]:
        pending = sorted(early_payments, key=lambda ep: (ep.date, ep.id or 0))
        # при высокой ставке и неровном первом периоде аннуитет по формуле гасит долг
        # раньше срока договора — фиксируем фактический срок как плановый
        self.planned_last = self._actual_last_period(1)
        idx = 0
        period = 1
        while self.balance > 0 and period <= MAX_PERIODS:
            pay_date = self.payment_date(period)
            while idx < len(pending) and pending[idx].date < pay_date and self.balance > 0:
                self._early(pending[idx], next_period=period)
                idx += 1
            if self.balance <= 0:
                break
            self._regular(period, pay_date)
            while idx < len(pending) and pending[idx].date == pay_date:
                if self.balance > 0:
                    self._early(pending[idx], next_period=period + 1)
                idx += 1
            period += 1
        return self.rows

    def _regular(self, period: int, pay_date: date) -> None:
        interest = money(self.carry + accrue_interest(self.balance, self.loan.annual_rate, self.cursor, pay_date))
        self.carry = ZERO
        is_last = period >= self.planned_last
        if self.is_annuity:
            principal = self.payment - interest
            if is_last or principal >= self.balance:
                principal = self.balance
            principal = max(principal, ZERO)
        else:
            principal = self.balance if is_last else min(self.principal_part, self.balance)
        self.balance -= principal
        self.cursor = pay_date
        self.rows.append(
            ScheduleRow(
                period_no=period,
                date=pay_date,
                kind="regular",
                payment=principal + interest,
                interest=interest,
                principal=principal,
                balance_after=self.balance,
            )
        )

    def _early(self, ep: EarlyPaymentInput, next_period: int) -> None:
        interest_due = money(self.carry + accrue_interest(self.balance, self.loan.annual_rate, self.cursor, ep.date))
        interest_paid = min(ep.amount, interest_due)
        self.carry = interest_due - interest_paid
        principal = min(ep.amount - interest_paid, self.balance)
        self.balance -= principal
        self.cursor = max(self.cursor, ep.date)
        self.rows.append(
            ScheduleRow(
                period_no=None,
                date=ep.date,
                kind="early",
                payment=interest_paid + principal,
                interest=interest_paid,
                principal=principal,
                balance_after=self.balance,
                early_payment_id=ep.id,
                early_mode=ep.mode,
            )
        )
        if self.balance > 0:
            self._recalculate(ep.mode, next_period)

    def _actual_last_period(self, next_period: int) -> int:
        """Номер последнего периода, если дальше платить только по текущему графику."""
        sim = copy.copy(self)
        sim.rows = []
        period = next_period
        while sim.balance > 0 and period <= MAX_PERIODS:
            sim._regular(period, sim.payment_date(period))
            period += 1
        return max(period - 1, next_period)

    def _recalculate(self, mode: EarlyMode, next_period: int) -> None:
        # planned_last всегда держим равным фактическому последнему периоду графика,
        # иначе следующий reduce_payment растянет платёж на устаревший (больший) срок
        self.planned_last = max(self.planned_last, next_period)
        if mode == "reduce_payment":
            remaining = self.planned_last - next_period + 1
            if self.is_annuity:
                self.payment = annuity_payment(self.balance, self.monthly_rate, remaining)
            else:
                self.principal_part = money(self.balance / remaining)
        else:
            if self.is_annuity:
                needed = annuity_periods_needed(self.balance, self.monthly_rate, self.payment)
            else:
                needed = math.ceil(self.balance / self.principal_part) if self.principal_part > 0 else None
            if needed is not None:
                self.planned_last = min(self.planned_last, next_period + needed - 1)
        # формула аннуитета — лишь оценка (проценты считаются по дням), уточняем прогоном
        self.planned_last = self._actual_last_period(next_period)


def build_schedule(loan: LoanParams, early_payments: Sequence[EarlyPaymentInput] = ()) -> list[ScheduleRow]:
    return _Engine(loan).run(early_payments)
