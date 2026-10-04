"""Совместный доступ к списку долгов: участники, приглашения по ссылке, выход из чужого списка."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, Session, as_utc, hash_token
from app.config import Settings, get_settings
from app.models import ListInvite, ListMember, User
from app.schemas import InviteCreate, InviteOut, InvitePreview, ListOut, MemberOut, MemberUpdate, PersonOut
from app.services.access import list_role

router = APIRouter(tags=["sharing"])

INVITE_TTL = timedelta(days=7)
MAX_ACTIVE_INVITES = 20


def person(user: User) -> PersonOut:
    return PersonOut(user_id=user.id, display_name=user.name, login=user.login, avatar_url=user.avatar_url)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _drop_expired_invites(session: AsyncSession, owner_id: int) -> None:
    await session.execute(delete(ListInvite).where(ListInvite.owner_id == owner_id, ListInvite.expires_at <= _now()))


async def _invite_by_token(session: AsyncSession, token: str) -> ListInvite:
    invite = await session.scalar(select(ListInvite).where(ListInvite.token_hash == hash_token(token)))
    if invite is None or as_utc(invite.expires_at) <= _now():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приглашение не найдено или устарело")
    return invite


# --- списки, доступные текущему пользователю ---

@router.get("/lists", response_model=list[ListOut])
async def my_lists(user: CurrentUser, session: Session) -> list[ListOut]:
    memberships = await session.scalars(select(ListMember).where(ListMember.member_id == user.id))
    shared = sorted(memberships, key=lambda m: m.owner.name.lower())
    return [ListOut(owner=person(user), role="owner", is_own=True)] + [
        ListOut(owner=person(m.owner), role=m.role, is_own=False) for m in shared  # type: ignore[arg-type]
    ]


@router.delete("/lists/{owner_id}/membership", status_code=status.HTTP_204_NO_CONTENT)
async def leave_list(owner_id: int, user: CurrentUser, session: Session) -> Response:
    result = await session.execute(
        delete(ListMember).where(ListMember.owner_id == owner_id, ListMember.member_id == user.id)
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Вы не участник этого списка")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- участники собственного списка (управляет только владелец) ---

@router.get("/sharing/members", response_model=list[MemberOut])
async def list_members(user: CurrentUser, session: Session) -> list[MemberOut]:
    members = await session.scalars(select(ListMember).where(ListMember.owner_id == user.id))
    return [
        MemberOut(user=person(m.member), role=m.role)  # type: ignore[arg-type]
        for m in sorted(members, key=lambda m: m.member.name.lower())
    ]


@router.patch("/sharing/members/{member_id}", response_model=MemberOut)
async def update_member(member_id: int, payload: MemberUpdate, user: CurrentUser, session: Session) -> MemberOut:
    member = await session.get(ListMember, (user.id, member_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")
    member.role = payload.role
    await session.commit()
    return MemberOut(user=person(member.member), role=payload.role)


@router.delete("/sharing/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(member_id: int, user: CurrentUser, session: Session) -> Response:
    result = await session.execute(
        delete(ListMember).where(ListMember.owner_id == user.id, ListMember.member_id == member_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- приглашения в собственный список ---

@router.get("/sharing/invites", response_model=list[InviteOut])
async def list_invites(user: CurrentUser, session: Session) -> list[InviteOut]:
    await _drop_expired_invites(session, user.id)
    await session.commit()
    invites = await session.scalars(
        select(ListInvite).where(ListInvite.owner_id == user.id).order_by(ListInvite.created_at.desc(), ListInvite.id.desc())
    )
    return [InviteOut(id=i.id, role=i.role, expires_at=as_utc(i.expires_at)) for i in invites]  # type: ignore[arg-type]


@router.post("/sharing/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreate,
    user: CurrentUser,
    session: Session,
    settings: Annotated[Settings, Depends(get_settings)],
) -> InviteOut:
    await _drop_expired_invites(session, user.id)
    active = await session.scalar(select(func.count()).select_from(ListInvite).where(ListInvite.owner_id == user.id))
    if (active or 0) >= MAX_ACTIVE_INVITES:
        raise HTTPException(422, "Слишком много активных приглашений — отзовите ненужные")
    token = secrets.token_urlsafe(24)
    invite = ListInvite(owner_id=user.id, token_hash=hash_token(token), role=payload.role, expires_at=_now() + INVITE_TTL)
    session.add(invite)
    await session.commit()
    url = f"{settings.public_url.rstrip('/')}/invite/{token}"
    return InviteOut(id=invite.id, role=payload.role, expires_at=as_utc(invite.expires_at), url=url)


@router.delete("/sharing/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(invite_id: int, user: CurrentUser, session: Session) -> Response:
    result = await session.execute(
        delete(ListInvite).where(ListInvite.id == invite_id, ListInvite.owner_id == user.id)
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приглашение не найдено")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- принятие приглашения ---

@router.get("/invites/{token}", response_model=InvitePreview)
async def preview_invite(token: str, user: CurrentUser, session: Session) -> InvitePreview:
    invite = await _invite_by_token(session, token)
    return InvitePreview(
        owner=person(invite.owner),
        role=invite.role,  # type: ignore[arg-type]
        is_own=invite.owner_id == user.id,
        current_role=await list_role(session, user, invite.owner_id),
    )


@router.post("/invites/{token}/accept", response_model=ListOut)
async def accept_invite(token: str, user: CurrentUser, session: Session) -> ListOut:
    invite = await _invite_by_token(session, token)
    if invite.owner_id == user.id:
        raise HTTPException(422, "Это приглашение в ваш собственный список")
    owner, role = invite.owner, invite.role

    # приглашение одноразовое: удаляем первым, чтобы одновременное второе принятие получило 404
    result = await session.execute(delete(ListInvite).where(ListInvite.id == invite.id))
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приглашение не найдено или устарело")
    member = await session.get(ListMember, (owner.id, user.id))
    if member is None:
        session.add(ListMember(owner_id=owner.id, member_id=user.id, role=role))
    else:
        member.role = role
    await session.commit()
    return ListOut(owner=person(owner), role=role, is_own=False)  # type: ignore[arg-type]
