from decimal import Decimal as D

DEBT = {
    "name": "Ипотека",
    "principal": "1000000",
    "annual_rate": "12",
    "term_months": 12,
    "start_date": "2025-01-15",
    "first_payment_date": "2025-02-15",
    "schedule_type": "annuity",
}


async def create(client, **overrides):
    response = await client.post("/api/debts", json={**DEBT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


async def test_calculate_preview(client):
    body = {k: v for k, v in DEBT.items() if k != "name"}
    response = await client.post("/api/calculate", json=body)
    assert response.status_code == 200
    data = response.json()
    assert len(data["rows"]) == 12
    assert D(data["rows"][0]["payment"]) == D("88848.79")


async def test_validation(client):
    response = await client.post("/api/debts", json={**DEBT, "first_payment_date": "2025-01-10"})
    assert response.status_code == 422
    response = await client.post("/api/debts", json={**DEBT, "principal": "-5"})
    assert response.status_code == 422


async def test_debt_crud(client):
    debt = await create(client)
    assert debt["summary"]["periods_count"] == 12
    assert D(debt["summary"]["remaining_balance"]) == D("1000000")

    listing = (await client.get("/api/debts")).json()
    assert [d["id"] for d in listing] == [debt["id"]]

    renamed = (await client.patch(f"/api/debts/{debt['id']}", json={"name": "Авто"})).json()
    assert renamed["name"] == "Авто"

    assert (await client.delete(f"/api/debts/{debt['id']}")).status_code == 204
    assert (await client.get(f"/api/debts/{debt['id']}")).status_code == 404
    assert (await client.get("/api/debts")).json() == []


async def test_other_user_cannot_access(client, other_client):
    debt = await create(client)
    assert (await other_client.get(f"/api/debts/{debt['id']}")).status_code == 404
    assert (await other_client.delete(f"/api/debts/{debt['id']}")).status_code == 404
    assert (await other_client.get("/api/debts")).json() == []


async def test_mark_and_unmark_paid(client):
    debt = await create(client)
    url = f"/api/debts/{debt['id']}/periods/1/paid"
    schedule = (await client.put(url)).json()
    assert schedule["rows"][0]["is_paid"] is True
    assert schedule["summary"]["paid_count"] == 1
    assert schedule["summary"]["next_payment"]["period_no"] == 2
    assert (await client.put(url)).status_code == 200  # идемпотентно

    schedule = (await client.delete(url)).json()
    assert schedule["rows"][0]["is_paid"] is False
    assert (await client.put(f"/api/debts/{debt['id']}/periods/99/paid")).status_code == 404


async def test_early_payment_flow(client):
    debt = await create(client)
    base = f"/api/debts/{debt['id']}"
    for n in range(1, 13):
        await client.put(f"{base}/periods/{n}/paid")

    response = await client.post(
        f"{base}/early-payments", json={"date": "2025-04-15", "amount": "300000", "mode": "reduce_term"}
    )
    assert response.status_code == 201, response.text
    schedule = response.json()
    regular = [r for r in schedule["rows"] if r["kind"] == "regular"]
    early = [r for r in schedule["rows"] if r["kind"] == "early"]
    assert len(regular) < 12 and len(early) == 1
    # отметки об оплате исчезнувших периодов удалены
    assert schedule["summary"]["paid_count"] == len(regular)

    # удаление ошибочной досрочки возвращает исходный график
    schedule = (await client.delete(f"{base}/early-payments/{early[0]['early_payment_id']}")).json()
    assert len(schedule["rows"]) == 12
    assert (await client.delete(f"{base}/early-payments/{early[0]['early_payment_id']}")).status_code == 404

    detail = (await client.get(base)).json()
    assert detail["early_payments"] == []


async def test_early_payment_validation(client):
    debt = await create(client)
    base = f"/api/debts/{debt['id']}/early-payments"
    too_early = await client.post(base, json={"date": "2024-12-01", "amount": "1000", "mode": "reduce_term"})
    assert too_early.status_code == 422
    after_close = await client.post(base, json={"date": "2030-01-01", "amount": "1000", "mode": "reduce_term"})
    assert after_close.status_code == 422
    too_much = await client.post(base, json={"date": "2025-02-15", "amount": "5000000", "mode": "reduce_term"})
    assert too_much.status_code == 422
    assert "Максимум" in too_much.json()["detail"]
