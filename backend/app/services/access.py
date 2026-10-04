"""Права доступа к спискам долгов.

Список долгов — это все долги одного пользователя-владельца (Debt.user_id). Владелец может открыть
доступ к своему списку другим пользователям с ролью editor (всё, кроме управления доступом)
или viewer (только просмотр).
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ListMember, User

Role = Literal["owner", "editor", "viewer"]
MemberRole = Literal["editor", "viewer"]


async def list_role(session: AsyncSession, user: User, owner_id: int) -> Role | None:
    if owner_id == user.id:
        return "owner"
    member = await session.get(ListMember, (owner_id, user.id))
    return member.role if member else None  # type: ignore[return-value]


def can_edit(role: Role | None) -> bool:
    return role in ("owner", "editor")


async def require_list_role(session: AsyncSession, user: User, owner_id: int, *, write: bool = False) -> Role:
    """Роль пользователя в списке. Нет доступа — 404 (не раскрываем, что список существует), только просмотр — 403."""
    role = await list_role(session, user, owner_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Список не найден")
    if write and not can_edit(role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "У вас доступ только для просмотра")
    return role
