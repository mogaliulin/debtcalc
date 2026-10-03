import os
import tempfile
from pathlib import Path

_db_path = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path.as_posix()}"
os.environ["DEV_AUTH_BYPASS"] = "false"
os.environ["PUBLIC_URL"] = "http://testserver"
os.environ["YANDEX_CLIENT_ID"] = "test-client-id"
os.environ["YANDEX_CLIENT_SECRET"] = "test-client-secret"
os.environ["SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.auth import create_session, upsert_user  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.yandex import YandexUser  # noqa: E402


@pytest.fixture(autouse=True)
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def logged_in_client(yandex_id: str) -> AsyncClient:
    async with SessionLocal() as session:
        user = await upsert_user(
            session, YandexUser(id=yandex_id, login=f"user{yandex_id}", display_name="Иван", email=None, avatar_id=None)
        )
        token = await create_session(session, user, ttl_days=1)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver", cookies={"session": token})


@pytest.fixture
async def client():
    async with await logged_in_client("42") as c:
        yield c


@pytest.fixture
async def other_client():
    async with await logged_in_client("777") as c:
        yield c


@pytest.fixture
async def anon_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
