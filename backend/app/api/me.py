from fastapi import APIRouter

from app.auth import CurrentUser, Session
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(tags=["me"])


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        login=user.login,
        display_name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        timezone=user.timezone,
    )


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UserUpdate, user: CurrentUser, session: Session) -> UserOut:
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return user_out(user)
