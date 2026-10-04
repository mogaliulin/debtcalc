from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.api.auth import get_yandex_client, safe_next
from app.db import SessionLocal
from app.main import app
from app.models import ListInvite
from tests.test_api import DEBT, create
from tests.test_auth import FakeYandex


async def invite(owner, role="editor") -> str:
    response = await owner.post("/api/sharing/invites", json={"role": role})
    assert response.status_code == 201, response.text
    url = response.json()["url"]
    assert url.startswith("http://testserver/invite/")
    return url.rsplit("/", 1)[1]


async def join(owner, member, role="editor") -> int:
    token = await invite(owner, role)
    response = await member.post(f"/api/invites/{token}/accept")
    assert response.status_code == 200, response.text
    return response.json()["owner"]["user_id"]


async def test_invite_preview_and_accept(client, other_client):
    token = await invite(client, "editor")

    preview = (await other_client.get(f"/api/invites/{token}")).json()
    assert preview["owner"]["login"] == "user42"
    assert preview["role"] == "editor"
    assert preview["is_own"] is False and preview["current_role"] is None

    accepted = (await other_client.post(f"/api/invites/{token}/accept")).json()
    assert accepted["role"] == "editor"

    lists = (await other_client.get("/api/lists")).json()
    assert [(item["is_own"], item["role"]) for item in lists] == [(True, "owner"), (False, "editor")]
    assert lists[1]["owner"]["display_name"] == "Иван"

    # приглашение одноразовое
    assert (await other_client.post(f"/api/invites/{token}/accept")).status_code == 404
    assert (await other_client.get(f"/api/invites/{token}")).status_code == 404


async def test_editor_manages_shared_list(client, other_client):
    owner_id = await join(client, other_client, "editor")
    own_debt = await create(client)

    listing = (await other_client.get("/api/debts", params={"list_id": owner_id})).json()
    assert [d["id"] for d in listing] == [own_debt["id"]]
    assert listing[0]["role"] == "editor" and listing[0]["owner_id"] == owner_id

    # участник создаёт долг в чужом списке — он принадлежит владельцу списка
    response = await other_client.post("/api/debts", params={"list_id": owner_id}, json={**DEBT, "name": "Авто"})
    assert response.status_code == 201
    new_debt = response.json()
    assert new_debt["owner_id"] == owner_id
    assert {d["name"] for d in (await client.get("/api/debts")).json()} == {"Ипотека", "Авто"}
    # собственный список участника не изменился
    assert (await other_client.get("/api/debts")).json() == []

    debt_id = own_debt["id"]
    assert (await other_client.put(f"/api/debts/{debt_id}/periods/1/paid")).status_code == 200
    early = await other_client.post(
        f"/api/debts/{debt_id}/early-payments", json={"date": "2025-03-01", "amount": "100000", "mode": "reduce_term"}
    )
    assert early.status_code == 201
    assert (await other_client.patch(f"/api/debts/{debt_id}", json={"name": "Дом"})).status_code == 200
    assert (await client.get(f"/api/debts/{debt_id}")).json()["name"] == "Дом"
    assert (await client.get(f"/api/debts/{debt_id}/schedule")).json()["summary"]["paid_count"] == 1
    assert (await other_client.delete(f"/api/debts/{new_debt['id']}")).status_code == 204


async def test_viewer_is_read_only(client, other_client):
    owner_id = await join(client, other_client, "viewer")
    debt = await create(client)
    debt_id = debt["id"]

    assert (await other_client.get("/api/debts", params={"list_id": owner_id})).status_code == 200
    viewed = await other_client.get(f"/api/debts/{debt_id}")
    assert viewed.status_code == 200 and viewed.json()["role"] == "viewer"
    assert (await other_client.get(f"/api/debts/{debt_id}/schedule")).status_code == 200

    forbidden = [
        other_client.post("/api/debts", params={"list_id": owner_id}, json=DEBT),
        other_client.patch(f"/api/debts/{debt_id}", json={"name": "X"}),
        other_client.delete(f"/api/debts/{debt_id}"),
        other_client.put(f"/api/debts/{debt_id}/periods/1/paid"),
        other_client.delete(f"/api/debts/{debt_id}/periods/1/paid"),
        other_client.post(
            f"/api/debts/{debt_id}/early-payments", json={"date": "2025-03-01", "amount": "1000", "mode": "reduce_term"}
        ),
    ]
    for request in forbidden:
        response = await request
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "У вас доступ только для просмотра"
    # владелец по-прежнему видит свой долг неизменённым
    assert (await client.get(f"/api/debts/{debt_id}")).json()["role"] == "owner"


async def test_owner_changes_role_and_removes_member(client, other_client):
    owner_id = await join(client, other_client, "viewer")
    members = (await client.get("/api/sharing/members")).json()
    assert [(m["user"]["login"], m["role"]) for m in members] == [("user777", "viewer")]
    member_id = members[0]["user"]["user_id"]

    debt = await create(client)
    assert (await other_client.put(f"/api/debts/{debt['id']}/periods/1/paid")).status_code == 403
    assert (await client.patch(f"/api/sharing/members/{member_id}", json={"role": "editor"})).json()["role"] == "editor"
    assert (await other_client.put(f"/api/debts/{debt['id']}/periods/1/paid")).status_code == 200

    assert (await client.delete(f"/api/sharing/members/{member_id}")).status_code == 204
    assert (await other_client.get("/api/debts", params={"list_id": owner_id})).status_code == 404
    assert (await other_client.get(f"/api/debts/{debt['id']}")).status_code == 404
    assert len((await other_client.get("/api/lists")).json()) == 1


async def test_member_can_leave(client, other_client):
    owner_id = await join(client, other_client)
    assert (await other_client.delete(f"/api/lists/{owner_id}/membership")).status_code == 204
    assert (await other_client.get("/api/debts", params={"list_id": owner_id})).status_code == 404
    assert (await other_client.delete(f"/api/lists/{owner_id}/membership")).status_code == 404
    assert (await client.get("/api/sharing/members")).json() == []


async def test_member_cannot_manage_owner_sharing(client, other_client):
    await join(client, other_client, "editor")
    member_id = (await client.get("/api/sharing/members")).json()[0]["user"]["user_id"]
    owner_id = (await client.get("/api/me")).json()["id"]
    # управление доступом относится только к собственному списку: чужих участников не видно и не удалить
    assert (await other_client.get("/api/sharing/members")).json() == []
    assert (await other_client.delete(f"/api/sharing/members/{member_id}")).status_code == 404
    assert (await other_client.patch(f"/api/sharing/members/{owner_id}", json={"role": "viewer"})).status_code == 404
    token = await invite(client)
    invite_id = (await client.get("/api/sharing/invites")).json()[0]["id"]
    assert (await other_client.delete(f"/api/sharing/invites/{invite_id}")).status_code == 404
    assert (await other_client.get(f"/api/invites/{token}")).status_code == 200


async def test_no_access_without_invite(client, other_client):
    owner_id = (await client.get("/api/me")).json()["id"]
    await create(client)
    assert (await other_client.get("/api/debts", params={"list_id": owner_id})).status_code == 404
    assert (await other_client.post("/api/debts", params={"list_id": owner_id}, json=DEBT)).status_code == 404
    assert (await other_client.get("/api/debts", params={"list_id": 999999})).status_code == 404


async def test_revoked_expired_and_own_invites(client, other_client):
    token = await invite(client)
    invites = (await client.get("/api/sharing/invites")).json()
    assert len(invites) == 1 and invites[0]["url"] is None  # ссылку повторно не показываем
    assert (await client.delete(f"/api/sharing/invites/{invites[0]['id']}")).status_code == 204
    assert (await other_client.post(f"/api/invites/{token}/accept")).status_code == 404

    token = await invite(client)
    async with SessionLocal() as session:
        stored = await session.scalar(select(ListInvite))
        stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()
    assert (await other_client.post(f"/api/invites/{token}/accept")).status_code == 404
    assert (await client.get("/api/sharing/invites")).json() == []  # просроченные чистятся

    token = await invite(client)
    assert (await client.get(f"/api/invites/{token}")).json()["is_own"] is True
    assert (await client.post(f"/api/invites/{token}/accept")).status_code == 422


async def test_reaccept_updates_role(client, other_client):
    await join(client, other_client, "viewer")
    await join(client, other_client, "editor")
    assert [m["role"] for m in (await client.get("/api/sharing/members")).json()] == ["editor"]


async def test_login_returns_to_invite_page(anon_client):
    app.dependency_overrides[get_yandex_client] = lambda: FakeYandex()
    response = await anon_client.get("/api/auth/yandex/login", params={"next": "/invite/abc"})
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    response = await anon_client.get("/api/auth/yandex/callback", params={"code": "1", "state": state})
    assert response.headers["location"] == "http://testserver/invite/abc"


def test_safe_next():
    assert safe_next("/invite/abc?x=1") == "/invite/abc?x=1"
    for bad in [None, "", "https://evil.example", "//evil.example", "/\\evil.example", "invite"]:
        assert safe_next(bad) == "/"
