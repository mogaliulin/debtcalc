"""Клиент Яндекс ID: OAuth 2.0 authorization code + PKCE.

Документация: https://yandex.ru/dev/id/doc/ru/codes/code-url
и https://yandex.ru/dev/id/doc/ru/user-information
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
USER_INFO_URL = "https://login.yandex.ru/info"


class YandexAuthError(Exception):
    pass


@dataclass(frozen=True)
class YandexUser:
    id: str
    login: str
    display_name: str
    email: str | None
    avatar_id: str | None


def new_pkce_pair() -> tuple[str, str]:
    """Возвращает (code_verifier, code_challenge) для метода S256."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(client_id: str, redirect_uri: str, state: str, code_challenge: str) -> str:
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(query)}"


def parse_user(info: dict[str, Any]) -> YandexUser:
    if not info.get("id"):
        raise YandexAuthError("Яндекс не вернул идентификатор пользователя")
    avatar_id = None if info.get("is_avatar_empty", True) else info.get("default_avatar_id")
    return YandexUser(
        id=str(info["id"]),
        login=str(info.get("login") or ""),
        display_name=str(info.get("display_name") or info.get("real_name") or info.get("login") or ""),
        email=info.get("default_email"),
        avatar_id=avatar_id,
    )


class YandexOAuthClient:
    def __init__(self, client_id: str, client_secret: str, http: httpx.AsyncClient | None = None) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = http

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=10)
        return self._http

    async def exchange_code(self, code: str, code_verifier: str) -> str:
        http = await self._client()
        try:
            response = await http.post(
                TOKEN_URL,
                data={"grant_type": "authorization_code", "code": code, "code_verifier": code_verifier},
                auth=(self.client_id, self.client_secret),
            )
        except httpx.HTTPError as exc:
            raise YandexAuthError("Не удалось связаться с Яндекс ID") from exc
        payload = response.json() if response.content else {}
        if response.status_code != 200 or "access_token" not in payload:
            raise YandexAuthError(payload.get("error_description") or payload.get("error") or "Ошибка получения токена")
        return payload["access_token"]

    async def user_info(self, access_token: str) -> YandexUser:
        http = await self._client()
        try:
            response = await http.get(
                USER_INFO_URL, params={"format": "json"}, headers={"Authorization": f"OAuth {access_token}"}
            )
        except httpx.HTTPError as exc:
            raise YandexAuthError("Не удалось связаться с Яндекс ID") from exc
        if response.status_code != 200:
            raise YandexAuthError("Не удалось получить данные пользователя")
        return parse_user(response.json())
