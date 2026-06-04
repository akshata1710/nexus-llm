import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from core.database import get_db, Base

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = override_get_db
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def registered_user(client):
    resp = await client.post("/auth/register", json={
        "email": "akshata@nexus.ai",
        "password": "securepass123",
        "full_name": "Akshata Shinde",
        "team": "platform",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def auth_headers(client, registered_user):
    resp = await client.post("/auth/login", json={
        "email": "akshata@nexus.ai",
        "password": "securepass123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/auth/register", json={
        "email": "new@nexus.ai",
        "password": "password123",
        "full_name": "New User",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@nexus.ai"
    assert data["role"] == "engineer"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client, registered_user):
    resp = await client.post("/auth/register", json={
        "email": "akshata@nexus.ai",
        "password": "anotherpass",
        "full_name": "Duplicate",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client):
    resp = await client.post("/auth/register", json={
        "email": "short@nexus.ai",
        "password": "abc",
        "full_name": "Short Pass",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, registered_user):
    resp = await client.post("/auth/login", json={
        "email": "akshata@nexus.ai",
        "password": "securepass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, registered_user):
    resp = await client.post("/auth/login", json={
        "email": "akshata@nexus.ai",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post("/auth/login", json={
        "email": "ghost@nexus.ai",
        "password": "somepassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh(client, registered_user):
    login = await client.post("/auth/login", json={
        "email": "akshata@nexus.ai",
        "password": "securepass123",
    })
    refresh_token = login.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_access_token_cannot_refresh(client, auth_headers):
    access_token = auth_headers["Authorization"].split(" ")[1]
    resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client, auth_headers, registered_user):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "akshata@nexus.ai"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_api_key(client, auth_headers):
    resp = await client.post("/keys", json={"name": "my-dev-key"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"].startswith("nx-")
    assert "key_prefix" in data
    assert len(data["key"]) > 20


@pytest.mark.asyncio
async def test_api_key_not_shown_in_list(client, auth_headers):
    await client.post("/keys", json={"name": "hidden-key"}, headers=auth_headers)
    resp = await client.get("/keys", headers=auth_headers)
    assert resp.status_code == 200
    for key in resp.json():
        assert "key" not in key or key.get("key") is None


@pytest.mark.asyncio
async def test_authenticate_with_api_key(client, auth_headers):
    create_resp = await client.post("/keys", json={"name": "auth-test-key"}, headers=auth_headers)
    full_key = create_resp.json()["key"]
    resp = await client.get("/auth/me", headers={"X-API-Key": full_key})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_revoke_api_key(client, auth_headers):
    create_resp = await client.post("/keys", json={"name": "to-revoke"}, headers=auth_headers)
    key_id = create_resp.json()["id"]
    full_key = create_resp.json()["key"]
    revoke_resp = await client.delete(f"/keys/{key_id}", headers=auth_headers)
    assert revoke_resp.status_code == 204
    resp = await client.get("/auth/me", headers={"X-API-Key": full_key})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rotate_api_key(client, auth_headers):
    create_resp = await client.post("/keys", json={"name": "to-rotate"}, headers=auth_headers)
    key_id = create_resp.json()["id"]
    old_full_key = create_resp.json()["key"]
    rotate_resp = await client.post(f"/keys/{key_id}/rotate", headers=auth_headers)
    assert rotate_resp.status_code == 200
    new_full_key = rotate_resp.json()["key"]
    new_resp = await client.get("/auth/me", headers={"X-API-Key": new_full_key})
    assert new_resp.status_code == 200
    old_resp = await client.get("/auth/me", headers={"X-API-Key": old_full_key})
    assert old_resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_rejected(client):
    resp = await client.get("/auth/me", headers={"X-API-Key": "nx-totallyfakekey"})
    assert resp.status_code == 401
