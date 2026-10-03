"""Сводка по вычисленному графику с учётом отметок об оплате."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Collection, Sequence

from app.services.calculator import ZERO, ScheduleRow


@dataclass(frozen=True)
class ScheduleSummary:
    principal: Decimal
    remaining_balance: Decimal
    total_payments: Decimal
    total_interest: Decimal
    close_date: date | None
    periods_count: int
    paid_count: int
    overdue_count: int
    next_payment: ScheduleRow | None
    progress: float
    is_closed: bool


def summarize(
    principal: Decimal,
    rows: Sequence[ScheduleRow],
    paid_periods: Collection[int],
    today: date,
) -> ScheduleSummary:
    remaining = principal
    next_payment: ScheduleRow | None = None
    overdue = 0
    paid_count = 0
    periods = 0
    for row in rows:
        is_done = row.kind == "early" or row.period_no in paid_periods
        if is_done:
            remaining = row.balance_after
        if row.kind != "regular":
            continue
        periods += 1
        if row.period_no in paid_periods:
            paid_count += 1
            continue
        if next_payment is None:
            next_payment = row
        if row.date < today:
            overdue += 1

    is_closed = next_payment is None
    if is_closed:
        remaining = ZERO
    progress = float((principal - remaining) / principal) if principal > 0 else 1.0
    return ScheduleSummary(
        principal=principal,
        remaining_balance=remaining,
        total_payments=sum((r.payment for r in rows), ZERO),
        total_interest=sum((r.interest for r in rows), ZERO),
        close_date=rows[-1].date if rows else None,
        periods_count=periods,
        paid_count=paid_count,
        overdue_count=overdue,
        next_payment=next_payment,
        progress=round(max(0.0, min(1.0, progress)), 4),
        is_closed=is_closed,
    )
