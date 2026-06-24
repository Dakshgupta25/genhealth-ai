"""
Tests for the authentication router.

Covers: signup, login, token refresh, logout, OTP verify, password reset, /me.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from tests.conftest import create_test_user, auth_headers


# ─── POST /auth/signup ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    """Signup with valid data returns 201 and a token pair."""
    response = await client.post("/api/v1/auth/signup", json={
        "email": "newuser@example.com",
        "full_name": "New User",
        "password": "SecurePass1",
        "role": "patient",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "tokens" in data["data"]
    assert "access_token" in data["data"]["tokens"]
    assert data["data"]["user"]["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient, db_session):
    """Signup with an already-registered email returns 409."""
    await create_test_user(db_session, email="dupe@example.com")
    response = await client.post("/api/v1/auth/signup", json={
        "email": "dupe@example.com",
        "full_name": "Duplicate",
        "password": "SecurePass1",
    })
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_signup_weak_password(client: AsyncClient):
    """Signup with a password lacking uppercase or digit returns 422."""
    response = await client.post("/api/v1/auth/signup", json={
        "email": "weakpwd@example.com",
        "full_name": "Weak User",
        "password": "alllowercase",   # No uppercase or digit
    })
    assert response.status_code == 422


# ─── POST /auth/login ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session):
    """Login with correct credentials returns 200 with tokens."""
    await create_test_user(db_session, email="loginuser@example.com")
    response = await client.post("/api/v1/auth/login", json={
        "email": "loginuser@example.com",
        "password": "TestPass1",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]["tokens"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session):
    """Login with wrong password returns 401."""
    await create_test_user(db_session, email="wrongpwd@example.com")
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrongpwd@example.com",
        "password": "WrongPass1",
    })
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Login with unknown email returns 401."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "SomePass1",
    })
    assert response.status_code == 401


# ─── GET /auth/me ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, test_user):
    """Authenticated user can fetch their own profile."""
    response = await client.get(
        "/api/v1/auth/me",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["email"] == test_user.email


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """Unauthenticated request to /me returns 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    """Request with a malformed token returns 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert response.status_code == 401


# ─── PATCH /auth/me ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, test_user):
    """Authenticated user can update their profile fields."""
    response = await client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Updated Name", "phone": "+91-9876543210"},
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["full_name"] == "Updated Name"


# ─── POST /auth/logout ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout(client: AsyncClient, test_user):
    """Authenticated user can log out successfully."""
    response = await client.post(
        "/api/v1/auth/logout",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


# ─── POST /auth/verify-email ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_invalid_otp(client: AsyncClient, test_user, mock_redis):
    """Submitting a wrong OTP returns 400."""
    mock_redis.get = AsyncMock(return_value="123456")
    response = await client.post("/api/v1/auth/verify-email", json={
        "email": test_user.email,
        "otp": "999999",  # Wrong OTP
    })
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_OTP"


@pytest.mark.asyncio
async def test_verify_email_correct_otp(client: AsyncClient, test_user, mock_redis):
    """Submitting the correct OTP verifies the email."""
    import hashlib, secrets
    mock_redis.get = AsyncMock(return_value="654321")
    mock_redis.delete = AsyncMock(return_value=1)
    response = await client.post("/api/v1/auth/verify-email", json={
        "email": test_user.email,
        "otp": "654321",
    })
    assert response.status_code == 200
    assert response.json()["success"] is True
