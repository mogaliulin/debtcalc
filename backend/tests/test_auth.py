from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from app.api.auth import STATE_COOKIE, get_yandex_client
from app.auth import hash_token, sign_payload, unsign_payload
from app.db import SessionLocal
from app.main import app
from app.models import UserSession
from app.yandex import YandexAuthError, YandexUser, parse_user


class FakeYandex:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def exchange_code(self, code: str, code_verifier: str) -> str:
        self.calls.append((code, code_verifier))
        if self.fail:
            raise YandexAuthError("Код устарел")
        return "ya-token"

    async def user_info(self, access_token: str) -> YandexUser:
        return YandexUser(id="1000", login="ivan", display_name="Иван И.", email="ivan@yandex.ru", avatar_id="0/0-0")


async def start_login(anon_client):
    response = await anon_client.get("/api/auth/yandex/login")
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    return response, location, parse_qs(location.query)


async def test_login_redirects_to_yandex_with_pkce(anon_client):
    response, location, query = await start_login(anon_client)
    assert f"{location.scheme}://{location.netloc}{location.path}" == "https://oauth.yandex.ru/authorize"
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == ["http://testserver/api/auth/yandex/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0] and query["code_challenge"][0]
    set_cookie = response.headers["set-cookie"]
    assert STATE_COOKIE in set_cookie and "HttpOnly" in set_cookie


async def test_full_login_flow(anon_client):
    fake = FakeYandex()
    app.dependency_overrides[get_yandex_client] = lambda: fake
    _, _, query = await start_login(anon_client)

    response = await anon_client.get("/api/auth/yandex/callback", params={"code": "1234567", "state": query["state"][0]})
    assert response.status_code == 302
    assert response.headers["location"] == "http://testserver/"
    assert fake.calls and fake.calls[0][0] == "1234567"
    assert anon_client.cookies.get("session")

    me = (await anon_client.get("/api/me")).json()
    assert me["login"] == "ivan"
    assert me["email"] == "ivan@yandex.ru"
    assert me["avatar_url"].startswith("https://avatars.yandex.net/get-yapic/0/0-0/")

    # повторный вход того же пользователя не создаёт дубль
    _, _, query = await start_login(anon_client)
    await anon_client.get("/api/auth/yandex/callback", params={"code": "7654321", "state": query["state"][0]})
    assert (await anon_client.get("/api/me")).json()["id"] == me["id"]

    assert (await anon_client.post("/api/auth/logout")).status_code == 204
    assert (await anon_client.get("/api/me")).status_code == 401


async def test_callback_rejects_wrong_state(anon_client):
    app.dependency_overrides[get_yandex_client] = lambda: FakeYandex()
    await start_login(anon_client)
    response = await anon_client.get("/api/auth/yandex/callback", params={"code": "1", "state": "forged"})
    assert response.headers["location"].startswith("http://testserver/login?error=")
    assert (await anon_client.get("/api/me")).status_code == 401


async def test_callback_without_state_cookie(anon_client):
    app.dependency_overrides[get_yandex_client] = lambda: FakeYandex()
    response = await anon_client.get("/api/auth/yandex/callback", params={"code": "1", "state": "x"})
    assert "/login?error=" in response.headers["location"]


async def test_callback_user_denied(anon_client):
    response = await anon_client.get("/api/auth/yandex/callback", params={"error": "access_denied"})
    assert "/login?error=" in response.headers["location"]


async def test_callback_token_exchange_failure(anon_client):
    app.dependency_overrides[get_yandex_client] = lambda: FakeYandex(fail=True)
    _, _, query = await start_login(anon_client)
    response = await anon_client.get("/api/auth/yandex/callback", params={"code": "1", "state": query["state"][0]})
    assert "/login?error=" in response.headers["location"]
    assert (await anon_client.get("/api/me")).status_code == 401


async def test_expired_session_rejected(client):
    async with SessionLocal() as session:
        row = await session.get(UserSession, hash_token(client.cookies["session"]))
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()
    assert (await client.get("/api/me")).status_code == 401


async def test_api_requires_auth(anon_client):
    assert (await anon_client.get("/api/debts")).status_code == 401
    anon_client.cookies.set("session", "garbage")
    assert (await anon_client.get("/api/debts")).status_code == 401


def test_signed_payload():
    value = sign_payload({"state": "s"}, "key", 60)
    assert unsign_payload(value, "key")["state"] == "s"
    assert unsign_payload(value, "other-key") is None
    assert unsign_payload(value[:-1] + ("0" if value[-1] != "0" else "1"), "key") is None
    assert unsign_payload(sign_payload({"state": "s"}, "key", -1), "key") is None


def test_parse_user():
    user = parse_user({"id": "5", "login": "a", "display_name": "A", "default_email": "a@ya.ru",
                       "default_avatar_id": "1/2", "is_avatar_empty": False})
    assert (user.id, user.email, user.avatar_id) == ("5", "a@ya.ru", "1/2")
    assert parse_user({"id": "5", "login": "a", "default_avatar_id": "1/2", "is_avatar_empty": True}).avatar_id is None


async def test_me(client):
    response = await client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["login"] == "user42"
    response = await client.patch("/api/me", json={"timezone": "Asia/Yekaterinburg"})
    assert response.json()["timezone"] == "Asia/Yekaterinburg"
    assert (await client.patch("/api/me", json={"timezone": "Mars/Base"})).status_code == 422


async def test_yandex_client_requests():
    import base64

    import httpx

    from app.yandex import YandexOAuthClient

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth.yandex.ru":
            seen["auth"] = request.headers["authorization"]
            seen["form"] = parse_qs(request.content.decode())
            return httpx.Response(200, json={"access_token": "AQA", "token_type": "bearer"})
        seen["info_auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"id": "9", "login": "petr", "is_avatar_empty": True})

    client = YandexOAuthClient("cid", "csecret", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    token = await client.exchange_code("1234567", "verifier")
    user = await client.user_info(token)
    assert seen["auth"] == "Basic " + base64.b64encode(b"cid:csecret").decode()
    assert seen["form"] == {"grant_type": ["authorization_code"], "code": ["1234567"], "code_verifier": ["verifier"]}
    assert seen["info_auth"] == "OAuth AQA"
    assert user.id == "9" and user.display_name == "petr"

    def bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Code has expired"})

    failing = YandexOAuthClient("cid", "csecret", http=httpx.AsyncClient(transport=httpx.MockTransport(bad)))
    try:
        await failing.exchange_code("1", "v")
    except YandexAuthError as exc:
        assert "expired" in str(exc)
    else:
        raise AssertionError("ожидалась ошибка")
