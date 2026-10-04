"""Вход через Яндекс ID (OAuth 2.0 authorization code + PKCE) и выход."""

import secrets
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from app.auth import Session, create_session, delete_session, set_session_cookie, sign_payload, unsign_payload, upsert_user
from app.config import Settings, get_settings
from app.yandex import YandexAuthError, YandexOAuthClient, authorize_url, new_pkce_pair

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "oauth_state"
STATE_TTL_SECONDS = 10 * 60  # код авторизации Яндекса живёт 10 минут
STATE_COOKIE_PATH = "/api/auth"

_client: YandexOAuthClient | None = None


def get_yandex_client(settings: Annotated[Settings, Depends(get_settings)]) -> YandexOAuthClient:
    global _client
    if _client is None:
        _client = YandexOAuthClient(settings.yandex_client_id, settings.yandex_client_secret)
    return _client


def _site_url(settings: Settings, path: str = "/", **query: str) -> str:
    url = settings.public_url.rstrip("/") + path
    return f"{url}?{urlencode(query)}" if query else url


def safe_next(path: str | None) -> str:
    """Путь для возврата после входа: только внутренний (защита от открытого редиректа на чужой сайт)."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def _login_error(settings: Settings, message: str) -> RedirectResponse:
    response = RedirectResponse(_site_url(settings, "/login", error=message), status.HTTP_302_FOUND)
    response.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)
    return response


@router.get("/yandex/login")
async def yandex_login(settings: Annotated[Settings, Depends(get_settings)], next: str | None = None) -> RedirectResponse:
    if not settings.yandex_client_id or not settings.yandex_client_secret:
        return _login_error(settings, "Вход через Яндекс не настроен на сервере")
    state = secrets.token_urlsafe(32)
    verifier, challenge = new_pkce_pair()
    response = RedirectResponse(
        authorize_url(settings.yandex_client_id, settings.yandex_redirect_uri, state, challenge),
        status.HTTP_302_FOUND,
    )
    response.set_cookie(
        STATE_COOKIE,
        sign_payload({"state": state, "verifier": verifier, "next": safe_next(next)}, settings.secret_key, STATE_TTL_SECONDS),
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=STATE_COOKIE_PATH,
    )
    return response


@router.get("/yandex/callback")
async def yandex_callback(
    request: Request,
    session: Session,
    settings: Annotated[Settings, Depends(get_settings)],
    yandex: Annotated[YandexOAuthClient, Depends(get_yandex_client)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        message = "Вход отменён" if error == "access_denied" else "Яндекс отклонил вход"
        return _login_error(settings, message)

    saved = unsign_payload(request.cookies.get(STATE_COOKIE, ""), settings.secret_key)
    if not code or not state or saved is None or not secrets.compare_digest(saved.get("state", ""), state):
        return _login_error(settings, "Сессия входа устарела, попробуйте ещё раз")

    try:
        access_token = await yandex.exchange_code(code, saved["verifier"])
        ya_user = await yandex.user_info(access_token)
    except YandexAuthError as exc:
        return _login_error(settings, str(exc))

    # Токен Яндекса нужен только чтобы узнать пользователя — не храним его
    user = await upsert_user(session, ya_user)
    token = await create_session(session, user, settings.session_ttl_days)
    response = RedirectResponse(_site_url(settings, safe_next(saved.get("next"))), status.HTTP_302_FOUND)
    response.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)
    set_session_cookie(response, token, settings)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: Session, settings: Annotated[Settings, Depends(get_settings)]) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await delete_session(session, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
