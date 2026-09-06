"""Shared pytest fixtures.

Two kinds of tests live in this suite:

* **Unit / routing tests** use the `client` fixture — a plain TestClient with
  no database. The client is not used as a context manager, so the `lifespan`
  hook (which would call `init_db`) never runs.
* **Integration tests** use the `db_client` fixture, which runs the real app
  against a throwaway PostgreSQL database. If no database is reachable those
  tests skip rather than fail, so the suite still runs anywhere.

Redis and Celery are stubbed for integration tests: the JWT blocklist lookup
returns False and outbound email is captured in memory, so no broker or SMTP
server is needed.
"""

import asyncio
import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import src.auth.dependencies as auth_dependencies
import src.auth.router as auth_router_module
import src.businesses.routes as business_routes
from src import app
from src.auth.utils import create_url_safe_token
from src.db import models  # noqa: F401  (registers tables on SQLModel.metadata)
from src.db.main import get_session

API_PREFIX = "/api/v1"

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sales:sales@localhost:5432/sales_insight_test",
)

DEFAULT_PASSWORD = "testpass123"


# ---------------------------------------------------------------------------
# Plain client (no database) — used by the routing/validation tests
# ---------------------------------------------------------------------------
@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Integration database
# ---------------------------------------------------------------------------
async def _ensure_database() -> None:
    """Create the test database if it does not exist yet."""
    import asyncpg

    parts = urlsplit(TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    db_name = parts.path.lstrip("/")
    admin_dsn = parts._replace(path="/postgres").geturl()

    connection = await asyncpg.connect(admin_dsn)
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await connection.close()


async def _reset_schema(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)
        await connection.run_sync(SQLModel.metadata.create_all)


@pytest.fixture(scope="session")
def engine():
    """A test-database engine, or skip the whole integration suite."""
    try:
        asyncio.run(_ensure_database())
    except Exception as exc:  # noqa: BLE001 — any failure means "no database"
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")

    # NullPool: fixtures and the TestClient run on different event loops, and
    # asyncpg connections cannot be shared across loops.
    test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    asyncio.run(_reset_schema(test_engine))
    yield test_engine
    asyncio.run(test_engine.dispose())


class _CapturedEmails:
    """Stand-in for the Celery `send_email` task."""

    def __init__(self) -> None:
        self.sent: list[tuple[list[str], str, str]] = []

    def delay(self, recipients, subject, body):
        self.sent.append((recipients, subject, body))


@pytest.fixture
def emails() -> _CapturedEmails:
    return _CapturedEmails()


@pytest.fixture
def db_client(engine, emails, monkeypatch) -> TestClient:
    """The real app, wired to the test database, with Redis/Celery stubbed."""
    # Fresh schema per test keeps tenant tests independent of each other.
    asyncio.run(_reset_schema(engine))

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_session():
        async with session_factory() as session:
            yield session

    async def no_blocklist(_jti: str) -> bool:
        return False

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(auth_dependencies, "token_in_blocklist", no_blocklist)
    monkeypatch.setattr(business_routes, "send_email", emails)
    monkeypatch.setattr(auth_router_module, "send_email", emails)

    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers used across the integration tests
# ---------------------------------------------------------------------------
def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_user(
    client: TestClient, email: str, password: str = DEFAULT_PASSWORD
) -> str:
    """Sign up, verify by email token, log in — returns the access token."""
    username = email.split("@")[0]
    response = client.post(
        f"{API_PREFIX}/auth/signup",
        json={
            "first_name": username.title(),
            "last_name": "Tester",
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text

    # Exercise the real verification endpoint rather than flipping the flag.
    token = create_url_safe_token({"email": email})
    assert client.get(f"{API_PREFIX}/auth/verify/{token}").status_code == 200

    login = client.post(
        f"{API_PREFIX}/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def create_business(client: TestClient, token: str, name: str) -> dict:
    response = client.post(
        f"{API_PREFIX}/businesses/", json={"name": name}, headers=auth_headers(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_product(
    client: TestClient, token: str, business_uid: str, name: str, price: float
) -> dict:
    response = client.post(
        f"{API_PREFIX}/businesses/{business_uid}/products/",
        json={"name": name, "category": "Test", "unit_price": price},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_customer(
    client: TestClient, token: str, business_uid: str, name: str
) -> dict:
    response = client.post(
        f"{API_PREFIX}/businesses/{business_uid}/customers/",
        json={"name": name, "email": f"{name.lower()}@example.com", "region": "EMEA"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def invite_and_accept(
    client: TestClient,
    owner_token: str,
    business_uid: str,
    email: str,
    role: str = "employee",
    member_token: str | None = None,
) -> str:
    """Invite `email` and accept the invitation — returns the member's token.

    Creates and verifies the account unless `member_token` is given, which
    covers inviting someone who already has an account.
    """
    invite = client.post(
        f"{API_PREFIX}/businesses/{business_uid}/members/invite",
        json={"email": email, "role": role},
        headers=auth_headers(owner_token),
    )
    assert invite.status_code == 201, invite.text
    invite_token = invite.json()["invite_token"]

    if member_token is None:
        member_token = make_user(client, email)
    accepted = client.post(
        f"{API_PREFIX}/businesses/invitations/accept",
        json={"token": invite_token},
        headers=auth_headers(member_token),
    )
    assert accepted.status_code == 200, accepted.text
    return member_token
