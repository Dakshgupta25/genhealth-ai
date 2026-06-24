"""
Tests for the health records router.

Covers: list records, get record, verify, delete, timeline, entities.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from tests.conftest import create_test_user, auth_headers
from app.models.health_record import HealthRecord


async def _create_record_in_db(db, owner_id, record_type="prescription") -> HealthRecord:
    """Helper: directly insert a HealthRecord into the test DB."""
    import uuid
    record = HealthRecord(
        id=uuid.uuid4(),
        owner_id=owner_id,
        record_type=record_type,
        extraction_status="done",
        is_verified_by_user=False,
    )
    db.add(record)
    await db.flush()
    return record


# ─── GET /records/ ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_records_empty(client: AsyncClient, test_user):
    """New user has no health records."""
    response = await client.get("/api/v1/records/", headers=auth_headers(test_user))
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_list_records_pagination(client: AsyncClient, test_user, db_session):
    """Pagination parameters are respected."""
    for i in range(5):
        await _create_record_in_db(db_session, test_user.id, "prescription")

    response = await client.get(
        "/api/v1/records/?page=1&per_page=3",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 3
    assert data["meta"]["total"] == 5
    assert data["meta"]["has_next"] is True


@pytest.mark.asyncio
async def test_list_records_unauthenticated(client: AsyncClient):
    """Unauthenticated request returns 401."""
    response = await client.get("/api/v1/records/")
    assert response.status_code == 401


# ─── GET /records/:id ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_record_success(client: AsyncClient, test_user, db_session):
    """Can fetch a specific record by ID."""
    record = await _create_record_in_db(db_session, test_user.id)
    response = await client.get(
        f"/api/v1/records/{record.id}",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(record.id)


@pytest.mark.asyncio
async def test_get_record_not_found(client: AsyncClient, test_user):
    """Fetching a non-existent record returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(
        f"/api/v1/records/{fake_id}",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_record_another_users_record(client: AsyncClient, db_session):
    """Cannot access another user's record."""
    user_a = await create_test_user(db_session, email="usera@example.com")
    user_b = await create_test_user(db_session, email="userb@example.com")
    record = await _create_record_in_db(db_session, user_a.id)

    response = await client.get(
        f"/api/v1/records/{record.id}",
        headers=auth_headers(user_b),  # User B trying to access User A's record
    )
    assert response.status_code == 404  # Should not be visible to user B


# ─── PATCH /records/:id/verify ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_record(client: AsyncClient, test_user, db_session):
    """Verifying a record marks it as verified."""
    record = await _create_record_in_db(db_session, test_user.id)
    assert record.is_verified_by_user is False

    response = await client.patch(
        f"/api/v1/records/{record.id}/verify",
        json={"corrections": None},
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_verified_by_user"] is True


# ─── DELETE /records/:id ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_record(client: AsyncClient, test_user, db_session):
    """Deleting a record removes it from the list."""
    record = await _create_record_in_db(db_session, test_user.id)
    record_id = str(record.id)

    del_resp = await client.delete(
        f"/api/v1/records/{record_id}",
        headers=auth_headers(test_user),
    )
    assert del_resp.status_code == 200

    get_resp = await client.get(
        f"/api/v1/records/{record_id}",
        headers=auth_headers(test_user),
    )
    assert get_resp.status_code == 404


# ─── GET /records/timeline ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_empty(client: AsyncClient, test_user):
    """Timeline is empty for a new user."""
    response = await client.get("/api/v1/records/timeline", headers=auth_headers(test_user))
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_timeline_has_records(client: AsyncClient, test_user, db_session):
    """Timeline includes uploaded records ordered by date."""
    await _create_record_in_db(db_session, test_user.id, "lab_report")
    await _create_record_in_db(db_session, test_user.id, "prescription")

    response = await client.get("/api/v1/records/timeline", headers=auth_headers(test_user))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2


# ─── GET /records/entities ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_entities_empty(client: AsyncClient, test_user):
    """Entity list is empty when no records have been processed."""
    response = await client.get("/api/v1/records/entities", headers=auth_headers(test_user))
    assert response.status_code == 200
    assert response.json()["data"] == []
