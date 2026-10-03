from datetime import date
from decimal import Decimal as D

from app.services.calculator import (
    EarlyPaymentInput,
    LoanParams,
    accrue_interest,
    add_months,
    annuity_payment,
    build_schedule,
    money,
)
from app.services.summary import summarize


def loan(**overrides) -> LoanParams:
    params = dict(
        principal=D("1000000"),
        annual_rate=D("12"),
        term_months=12,
        start_date=date(2025, 1, 15),
        first_payment_date=date(2025, 2, 15),
        schedule_type="annuity",
    )
    params.update(overrides)
    return LoanParams(**params)


def regular(rows):
    return [r for r in rows if r.kind == "regular"]


def assert_consistent(rows, principal):
    assert rows[-1].balance_after == 0
    assert sum(r.principal for r in rows) == principal
    for r in rows:
        assert r.payment == r.principal + r.interest
        assert r.principal >= 0 and r.interest >= 0


def test_add_months_clamps_to_month_end():
    base = date(2025, 1, 31)
    assert add_months(base, 1, 31) == date(2025, 2, 28)
    assert add_months(base, 2, 31) == date(2025, 3, 31)
    assert add_months(base, 3, 31) == date(2025, 4, 30)
    assert add_months(date(2023, 12, 31), 2, 31) == date(2024, 2, 29)
    assert add_months(date(2025, 11, 15), 2, 15) == date(2026, 1, 15)


def test_interest_across_leap_year_boundary():
    interest = accrue_interest(D("366000"), D("10"), date(2024, 12, 15), date(2025, 1, 15))
    expected = D("366000") * D("0.1") * 17 / 366 + D("366000") * D("0.1") * 14 / 365
    assert money(interest) == money(expected)


def test_annuity_payment_reference_value():
    # Классический пример: 1 000 000 под 12% на 12 месяцев
    assert annuity_payment(D("1000000"), D("0.01"), 12) == D("88848.79")
    assert annuity_payment(D("120000"), D("0"), 12) == D("10000.00")


def test_annuity_schedule():
    rows = build_schedule(loan())
    assert len(rows) == 12
    assert_consistent(rows, D("1000000"))
    # первый период: 31 день, проценты по дням
    assert rows[0].interest == D("10191.78")
    assert rows[0].payment == D("88848.79")
    # все платежи кроме последнего одинаковые; последний корректирующий — проценты по дням
    # расходятся с месячной ставкой аннуитета, разница набегает в пределах ~1% платежа
    assert {r.payment for r in rows[:-1]} == {D("88848.79")}
    assert abs(rows[-1].payment - D("88848.79")) < D("888")
    assert rows[0].date == date(2025, 2, 15)
    assert rows[-1].date == date(2026, 1, 15)


def test_differentiated_schedule():
    rows = build_schedule(loan(principal=D("120000"), schedule_type="differentiated"))
    assert len(rows) == 12
    assert_consistent(rows, D("120000"))
    assert {r.principal for r in rows} == {D("10000.00")}
    # платёж убывает
    payments = [r.payment for r in rows]
    assert payments[0] > payments[-1]


def test_differentiated_rounding_remainder_goes_to_last_period():
    rows = build_schedule(loan(principal=D("100000"), term_months=3, schedule_type="differentiated"))
    assert [r.principal for r in rows] == [D("33333.33"), D("33333.33"), D("33333.34")]


def test_zero_rate():
    rows = build_schedule(loan(principal=D("120000"), annual_rate=D("0")))
    assert len(rows) == 12
    assert all(r.interest == 0 for r in rows)
    assert all(r.payment == D("10000.00") for r in rows)


def test_early_reduce_term_annuity():
    base = build_schedule(loan())
    ep = EarlyPaymentInput(date=date(2025, 4, 15), amount=D("300000"), mode="reduce_term", id=1)
    rows = build_schedule(loan(), [ep])
    reg = regular(rows)
    assert_consistent(rows, D("1000000"))
    assert len(reg) < len(base)
    # платёж не изменился (кроме последнего)
    assert {r.payment for r in reg[:-1]} == {D("88848.79")}
    early = [r for r in rows if r.kind == "early"]
    assert len(early) == 1
    # досрочка в дату платежа идёт после регулярного платежа — процентов нет
    assert early[0].interest == 0
    assert early[0].principal == D("300000")
    assert rows.index(early[0]) == 3  # после 3-го регулярного платежа (15.04)


def test_early_reduce_payment_annuity():
    ep = EarlyPaymentInput(date=date(2025, 4, 15), amount=D("300000"), mode="reduce_payment", id=1)
    rows = build_schedule(loan(), [ep])
    reg = regular(rows)
    assert_consistent(rows, D("1000000"))
    assert len(reg) == 12
    assert reg[3].payment < D("88848.79")
    assert reg[0].payment == D("88848.79")
    new_payments = {r.payment for r in reg[3:-1]}
    assert len(new_payments) == 1


def test_early_payment_between_dates_pays_accrued_interest_first():
    ep = EarlyPaymentInput(date=date(2025, 3, 1), amount=D("100000"), mode="reduce_payment", id=1)
    rows = build_schedule(loan(), [ep])
    assert_consistent(rows, D("1000000"))
    early = next(r for r in rows if r.kind == "early")
    balance_before = rows[0].balance_after
    expected_interest = money(accrue_interest(balance_before, D("12"), date(2025, 2, 15), date(2025, 3, 1)))
    assert early.interest == expected_interest
    assert early.principal == D("100000") - expected_interest
    # следующий регулярный платёж начисляет проценты только с 01.03
    second = regular(rows)[1]
    assert second.interest == money(accrue_interest(early.balance_after, D("12"), date(2025, 3, 1), date(2025, 3, 15)))


def test_early_payment_closes_debt():
    rows = build_schedule(loan(), [EarlyPaymentInput(date=date(2025, 2, 15), amount=D("2000000"), mode="reduce_term", id=1)])
    assert len(regular(rows)) == 1
    assert rows[-1].kind == "early"
    assert rows[-1].balance_after == 0
    assert rows[-1].payment == rows[0].balance_after  # погашен ровно остаток


def test_early_payment_after_close_is_ignored():
    rows = build_schedule(loan(), [EarlyPaymentInput(date=date(2030, 1, 1), amount=D("1000"), mode="reduce_term", id=1)])
    assert all(r.kind == "regular" for r in rows)


def test_early_reduce_term_differentiated():
    params = loan(principal=D("120000"), schedule_type="differentiated")
    rows = build_schedule(params, [EarlyPaymentInput(date=date(2025, 3, 15), amount=D("30000"), mode="reduce_term", id=1)])
    assert_consistent(rows, D("120000"))
    reg = regular(rows)
    assert len(reg) == 9
    assert {r.principal for r in reg} == {D("10000.00")}


def test_early_reduce_payment_differentiated():
    params = loan(principal=D("120000"), schedule_type="differentiated")
    rows = build_schedule(params, [EarlyPaymentInput(date=date(2025, 3, 15), amount=D("30000"), mode="reduce_payment", id=1)])
    assert_consistent(rows, D("120000"))
    reg = regular(rows)
    assert len(reg) == 12
    # после досрочки остаток 70000 на 10 периодов
    assert reg[2].principal == D("7000.00")


def test_reduce_payment_after_reduce_term_keeps_shortened_term():
    params = loan(principal=D("3000000"), annual_rate=D("16.5"), term_months=240,
                  start_date=date(2026, 1, 10), first_payment_date=date(2026, 2, 10))
    first = EarlyPaymentInput(date=date(2026, 9, 1), amount=D("500000"), mode="reduce_term", id=1)
    second = EarlyPaymentInput(date=date(2026, 10, 10), amount=D("200000"), mode="reduce_payment", id=2)
    term_after_first = len(regular(build_schedule(params, [first])))
    rows = build_schedule(params, [first, second])
    assert_consistent(rows, D("3000000"))
    reg = regular(rows)
    assert len(reg) == term_after_first
    assert reg[9].payment < reg[8].payment  # платёж уменьшился после второй досрочки


def test_multiple_early_payments_same_date_ordered_by_id():
    eps = [
        EarlyPaymentInput(date=date(2025, 5, 15), amount=D("1000"), mode="reduce_term", id=2),
        EarlyPaymentInput(date=date(2025, 5, 15), amount=D("2000"), mode="reduce_term", id=1),
    ]
    rows = build_schedule(loan(), eps)
    early = [r for r in rows if r.kind == "early"]
    assert [r.early_payment_id for r in early] == [1, 2]
    assert_consistent(rows, D("1000000"))


def test_random_early_payments_keep_invariants():
    import random
    from datetime import timedelta

    rnd = random.Random(20260927)
    for case in range(300):
        schedule_type = rnd.choice(["annuity", "differentiated"])
        principal = D(rnd.randint(10_000, 5_000_000))
        params = loan(principal=principal, annual_rate=D(str(rnd.choice([0, 3.9, 12, 16.5, 29.9]))),
                      term_months=rnd.randint(3, 240), schedule_type=schedule_type,
                      first_payment_date=date(2025, 1, 15) + timedelta(days=rnd.randint(10, 60)))
        eps = []
        periods_before = len(regular(build_schedule(params)))
        for n in range(rnd.randint(1, 4)):
            ep = EarlyPaymentInput(
                date=params.start_date + timedelta(days=rnd.randint(0, 30 * periods_before)),
                amount=money(principal * D(str(rnd.uniform(0.01, 0.3)))),
                mode=rnd.choice(["reduce_term", "reduce_payment"]),
                id=n + 1,
            )
            eps.append(ep)
            rows = build_schedule(params, eps)
            assert_consistent(rows, principal)
            periods_after = len(regular(rows))
            if ep.mode == "reduce_payment":
                assert periods_after <= periods_before, (case, eps)
            periods_before = periods_after


def test_summary():
    rows = build_schedule(loan())
    summary = summarize(D("1000000"), rows, {1, 2}, today=date(2025, 5, 1))
    assert summary.paid_count == 2
    assert summary.remaining_balance == rows[1].balance_after
    assert summary.next_payment == rows[2]
    assert summary.overdue_count == 1  # 15.04 не оплачен
    assert not summary.is_closed
    assert summary.total_interest == sum(r.interest for r in rows)

    closed = summarize(D("1000000"), rows, set(range(1, 13)), today=date(2025, 5, 1))
    assert closed.is_closed and closed.remaining_balance == 0 and closed.progress == 1.0
