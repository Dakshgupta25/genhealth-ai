"""
Tests for the family router.

Covers: add member, list members, update, delete, invite, tree, shared risks.
"""

import pytest
from httpx import AsyncClient
from uuid import UUID

from tests.conftest import create_test_user, auth_headers
from app.models.family import FamilyMember


# ─── POST /family/members ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_family_member_success(client: AsyncClient, test_user):
    """Authenticated user can add a family member."""
    response = await client.post(
        "/api/v1/family/members",
        json={"name": "Rajesh Sharma", "relationship": "father", "gender": "male"},
        headers=auth_headers(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Rajesh Sharma"
    assert data["data"]["relationship"] == "father"
    assert data["data"]["generation"] == 1


@pytest.mark.asyncio
async def test_add_family_member_unauthenticated(client: AsyncClient):
    """Unauthenticated request to add member returns 401."""
    response = await client.post(
        "/api/v1/family/members",
        json={"name": "Someone", "relationship": "mother"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_add_family_member_missing_fields(client: AsyncClient, test_user):
    """Adding a member without required fields returns 422."""
    response = await client.post(
        "/api/v1/family/members",
        json={"name": "No Relationship"},   # Missing 'relationship'
        headers=auth_headers(test_user),
    )
    assert response.status_code == 422


# ─── GET /family/members ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_family_members_empty(client: AsyncClient, test_user):
    """New user has no family members initially."""
    response = await client.get(
        "/api/v1/family/members",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_family_members_after_add(client: AsyncClient, test_user):
    """After adding a member, they appear in the list."""
    await client.post(
        "/api/v1/family/members",
        json={"name": "Priya Sharma", "relationship": "mother"},
        headers=auth_headers(test_user),
    )
    response = await client.get(
        "/api/v1/family/members",
        headers=auth_headers(test_user),
    )
    assert response.status_code == 200
    members = response.json()["data"]
    assert len(members) >= 1
    assert any(m["name"] == "Priya Sharma" for m in members)


# ─── PATCH /family/members/:id ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_family_member(client: AsyncClient, test_user):
    """Updating a family member changes their fields."""
    # First create a member
    create_resp = await client.post(
        "/api/v1/family/members",
        json={"name": "Old Name", "relationship": "brother"},
        headers=auth_headers(test_user),
    )
    member_id = create_resp.json()["data"]["id"]

    # Now update
    update_resp = await client.patch(
        f"/api/v1/family/members/{member_id}",
        json={"name": "New Name"},
        headers=auth_headers(test_user),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_nonexistent_member(client: AsyncClient, test_user):
    """Updating a non-existent member returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.patch(
        f"/api/v1/family/members/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(test_user),
    )
    assert response.status_code == 404


# ─── DELETE /family/members/:id ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_family_member(client: AsyncClient, test_user):
    """Deleting a family member removes them from the list."""
    create_resp = await client.post(
        "/api/v1/family/members",
        json={"name": "To Delete", "relationship": "sister"},
        headers=auth_headers(test_user),
    )
    member_id = create_resp.json()["data"]["id"]

    del_resp = await client.delete(
        f"/api/v1/family/members/{member_id}",
        headers=auth_headers(test_user),
    )
    assert del_resp.status_code == 200

    list_resp = await client.get("/api/v1/family/members", headers=auth_headers(test_user))
    members = list_resp.json()["data"]
    assert not any(m["id"] == member_id for m in members)


# ─── GET /family/tree ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_family_tree(client: AsyncClient, test_user):
    """Family tree endpoint returns correct structure."""
    await client.post(
        "/api/v1/family/members",
        json={"name": "Tree Dad", "relationship": "father"},
        headers=auth_headers(test_user),
    )
    response = await client.get("/api/v1/family/tree", headers=auth_headers(test_user))
    assert response.status_code == 200
    tree = response.json()["data"]
    assert "members" in tree
    assert "user_id" in tree
    assert tree["user_id"] == str(test_user.id)


# ─── GET /family/shared-risks ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shared_risks_empty(client: AsyncClient, test_user):
    """Shared risks returns empty list for a user with no disease data."""
    response = await client.get("/api/v1/family/shared-risks", headers=auth_headers(test_user))
    assert response.status_code == 200
    assert response.json()["data"]["patterns"] == []


# ─── POST /family/invite ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_invite_no_contact(client: AsyncClient, test_user):
    """Invite without email or phone returns 400."""
    # First add a member to invite
    create_resp = await client.post(
        "/api/v1/family/members",
        json={"name": "Invite Target", "relationship": "sister"},
        headers=auth_headers(test_user),
    )
    member_id = create_resp.json()["data"]["id"]

    # Invite with no contact method
    invite_resp = await client.post(
        "/api/v1/family/invite",
        json={"family_member_id": member_id},
        headers=auth_headers(test_user),
    )
    assert invite_resp.status_code == 400
    assert invite_resp.json()["detail"]["code"] == "MISSING_CONTACT"
