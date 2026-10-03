"""Сессии пользователей и получение текущего пользователя.

Вход выполняется через Яндекс ID (см. app/api/auth.py). После входа браузер получает HttpOnly-cookie
со случайным токеном сессии; в БД хранится только SHA-256 токена. Cookie выставляется с SameSite=Lax,
поэтому изменяющие запросы (POST/PUT/PATCH/DELETE) с чужих сайтов её не получают — это защищает от CSRF.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import User, UserSession
from app.yandex import YandexUser

DEV_YANDEX_ID = "dev"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    # SQLite возвращает naive datetime — считаем его UTC
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --- подписанные значения для временной cookie входа (state + PKCE verifier) ---

def sign_payload(data: dict[str, Any], secret: str, ttl_seconds: int) -> str:
    body = base64.urlsafe_b64encode(json.dumps({**data, "exp": int(time.time()) + ttl_seconds}).encode()).decode()
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def unsign_payload(value: str, secret: str) -> dict[str, Any] | None:
    body, _, signature = value.rpartition(".")
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not body or not hmac.compare_digest(signature, expected):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < time.time():
        return None
    return data


# --- пользователи и сессии ---

async def upsert_user(session: AsyncSession, ya: YandexUser) -> User:
    user = await session.scalar(select(User).where(User.yandex_id == ya.id))
    if user is None:
        user = User(yandex_id=ya.id)
        session.add(user)
    user.login = ya.login
    user.display_name = ya.display_name
    user.email = ya.email
    user.avatar_id = ya.avatar_id
    await session.commit()
    await session.refresh(user)
    return user


async def create_session(session: AsyncSession, user: User, ttl_days: int) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
        )
    )
    await session.commit()
    return token


async def delete_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    await session.commit()


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


async def _user_by_token(session: AsyncSession, token: str) -> User | None:
    row = await session.get(UserSession, hash_token(token))
    if row is None:
        return None
    if _utc(row.expires_at) <= datetime.now(timezone.utc):
        await session.delete(row)
        await session.commit()
        return None
    return await session.get(User, row.user_id)


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    user = await _user_by_token(session, token) if token else None
    if user is not None:
        return user
    if settings.dev_auth_bypass:
        return await upsert_user(session, YandexUser(id=DEV_YANDEX_ID, login="dev", display_name="Разработчик",
                                                     email=None, avatar_id=None))
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется вход")


CurrentUser = Annotated[User, Depends(get_current_user)]
Session = Annotated[AsyncSession, Depends(get_session)]
