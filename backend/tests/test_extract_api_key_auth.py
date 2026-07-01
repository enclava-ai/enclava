"""
Tests for Extract API Key Authentication

Tests the dual authentication pattern (JWT + API key) for extract endpoints
and verifies template-level access control.
"""

import pytest

from app.models.api_key import APIKey

# --- Unit Tests ---


def test_can_access_template_empty_list():
    """Empty allowed_extract_templates means all templates allowed"""
    api_key = APIKey(allowed_extract_templates=[])
    assert api_key.can_access_template("detailed_invoice")
    assert api_key.can_access_template("simple_receipt")
    assert api_key.can_access_template("expense_report")


def test_can_access_template_restricted():
    """Restricted API key can only access specified templates"""
    api_key = APIKey(allowed_extract_templates=["simple_receipt"])
    assert api_key.can_access_template("simple_receipt")
    assert not api_key.can_access_template("detailed_invoice")
    assert not api_key.can_access_template("expense_report")


def test_can_access_template_multiple():
    """API key with multiple templates can access all of them"""
    api_key = APIKey(allowed_extract_templates=["detailed_invoice", "expense_report"])
    assert api_key.can_access_template("detailed_invoice")
    assert not api_key.can_access_template("simple_receipt")
    assert api_key.can_access_template("expense_report")


def test_create_extract_key():
    """Factory creates correctly configured extract key"""
    key = APIKey.create_extract_key(
        user_id=1,
        name="Test Extract Key",
        key_hash="test_hash",
        key_prefix="test_pre",
        template_ids=["detailed_invoice"],
    )
    assert key.permissions == {"extract": True}
    assert "extract" in key.scopes
    assert key.allowed_extract_templates == ["detailed_invoice"]
    assert "/api/v1/extract/process" in key.allowed_endpoints
    assert "extract" in key.tags


def test_create_extract_key_all_templates():
    """Factory with no template_ids creates key allowing all templates"""
    key = APIKey.create_extract_key(
        user_id=1,
        name="Test Extract Key - All Templates",
        key_hash="test_hash",
        key_prefix="test_pre",
        template_ids=None,
    )
    assert key.allowed_extract_templates == []
    assert key.can_access_template("detailed_invoice")
    assert key.can_access_template("simple_receipt")


def test_add_allowed_template():
    """Add template to allowed list"""
    api_key = APIKey(allowed_extract_templates=["simple_receipt"])
    api_key.add_allowed_template("detailed_invoice")
    assert "detailed_invoice" in api_key.allowed_extract_templates
    assert "simple_receipt" in api_key.allowed_extract_templates
    assert len(api_key.allowed_extract_templates) == 2


def test_add_allowed_template_duplicate():
    """Adding duplicate template doesn't create duplicates"""
    api_key = APIKey(allowed_extract_templates=["simple_receipt"])
    api_key.add_allowed_template("simple_receipt")
    assert api_key.allowed_extract_templates.count("simple_receipt") == 1


def test_remove_allowed_template():
    """Remove template from allowed list"""
    api_key = APIKey(allowed_extract_templates=["detailed_invoice", "simple_receipt"])
    api_key.remove_allowed_template("simple_receipt")
    assert "detailed_invoice" in api_key.allowed_extract_templates
    assert "simple_receipt" not in api_key.allowed_extract_templates
    assert len(api_key.allowed_extract_templates) == 1


def test_to_dict_includes_extract_templates():
    """to_dict includes allowed_extract_templates field"""
    api_key = APIKey(
        id=1,
        name="Test Key",
        key_prefix="test_pre",
        user_id=1,
        is_active=True,
        allowed_extract_templates=["detailed_invoice"],
    )
    data = api_key.to_dict()
    assert "allowed_extract_templates" in data
    assert data["allowed_extract_templates"] == ["detailed_invoice"]


# --- Integration Tests ---
# Note: These require test fixtures and database setup
# Uncomment and implement when fixtures are available


# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_extract_process_with_api_key(client, db, test_user, test_file):
#     """Test processing document with API key authentication"""
#     from app.core.security import generate_api_key, get_api_key_hash
#
#     # Generate API key
#     raw_api_key = generate_api_key()
#     key_hash = get_api_key_hash(raw_api_key)
#     key_prefix = raw_api_key[:8]
#
#     # Create extract API key
#     api_key = APIKey.create_extract_key(
#         user_id=test_user.id,
#         name="Test Extract Key",
#         key_hash=key_hash,
#         key_prefix=key_prefix,
#         template_ids=["detailed_invoice"],
#     )
#     db.add(api_key)
#     await db.commit()
#
#     # Process document with API key
#     response = await client.post(
#         "/api/v1/extract/process",
#         headers={"Authorization": f"Bearer {raw_api_key}"},
#         files={"file": ("test.pdf", test_file, "application/pdf")},
#         data={"template": "detailed_invoice"},
#     )
#
#     assert response.status_code == 200
#     result = response.json()
#     assert result["success"] is True
#     assert "job_id" in result
#
#     # Verify job record has api_key_id set
#     from app.models.extract_job import ExtractJob
#     from sqlalchemy import select
#
#     stmt = select(ExtractJob).where(ExtractJob.id == result["job_id"])
#     job = await db.execute(stmt)
#     job = job.scalar_one()
#     assert job.api_key_id == api_key.id


# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_extract_process_template_restriction(client, db, test_user, test_file):
#     """Test API key cannot access unauthorized template"""
#     from app.core.security import generate_api_key, get_api_key_hash
#
#     # Generate API key restricted to simple_receipt
#     raw_api_key = generate_api_key()
#     key_hash = get_api_key_hash(raw_api_key)
#     key_prefix = raw_api_key[:8]
#
#     api_key = APIKey.create_extract_key(
#         user_id=test_user.id,
#         name="Test Extract Key - Restricted",
#         key_hash=key_hash,
#         key_prefix=key_prefix,
#         template_ids=["simple_receipt"],
#     )
#     db.add(api_key)
#     await db.commit()
#
#     # Try to process with detailed_invoice (not allowed)
#     response = await client.post(
#         "/api/v1/extract/process",
#         headers={"Authorization": f"Bearer {raw_api_key}"},
#         files={"file": ("test.pdf", test_file, "application/pdf")},
#         data={"template": "detailed_invoice"},
#     )
#
#     # Should get 403 error
#     assert response.status_code == 403
#     assert "Not authorized to use template" in response.json()["detail"]


# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_extract_list_jobs_scope_check(client, db, test_user):
#     """Test jobs endpoint requires extract scope"""
#     from app.core.security import generate_api_key, get_api_key_hash
#
#     # Create API key without extract scope
#     raw_api_key = generate_api_key()
#     key_hash = get_api_key_hash(raw_api_key)
#     key_prefix = raw_api_key[:8]
#
#     api_key = APIKey(
#         name="Test Key - No Extract Scope",
#         key_hash=key_hash,
#         key_prefix=key_prefix,
#         user_id=test_user.id,
#         is_active=True,
#         permissions={},
#         scopes=["other_scope"],  # Missing extract scope
#     )
#     db.add(api_key)
#     await db.commit()
#
#     # Try to list jobs
#     response = await client.get(
#         "/api/v1/extract/jobs",
#         headers={"Authorization": f"Bearer {raw_api_key}"},
#     )
#
#     # Should get 403 error
#     assert response.status_code == 403
#     assert "extract" in response.json()["detail"]


# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_extract_templates_scope_check(client, db, test_user):
#     """Test templates endpoint requires extract scope"""
#     from app.core.security import generate_api_key, get_api_key_hash
#
#     # Create API key without extract scope
#     raw_api_key = generate_api_key()
#     key_hash = get_api_key_hash(raw_api_key)
#     key_prefix = raw_api_key[:8]
#
#     api_key = APIKey(
#         name="Test Key - No Extract Scope",
#         key_hash=key_hash,
#         key_prefix=key_prefix,
#         user_id=test_user.id,
#         is_active=True,
#         permissions={},
#         scopes=["other_scope"],  # Missing extract scope
#     )
#     db.add(api_key)
#     await db.commit()
#
#     # Try to list templates
#     response = await client.get(
#         "/api/v1/extract/templates",
#         headers={"Authorization": f"Bearer {raw_api_key}"},
#     )
#
#     # Should get 403 error
#     assert response.status_code == 403
#     assert "extract" in response.json()["detail"]


# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_extract_process_with_jwt(client, db, test_user, test_file, auth_headers):
#     """Test processing document with JWT authentication (existing functionality)"""
#     # Process document with JWT
#     response = await client.post(
#         "/api/v1/extract/process",
#         headers=auth_headers,  # JWT token
#         files={"file": ("test.pdf", test_file, "application/pdf")},
#         data={"template": "detailed_invoice"},
#     )
#
#     assert response.status_code == 200
#     result = response.json()
#     assert result["success"] is True
#     assert "job_id" in result


# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_extract_no_auth(client):
#     """Test extract endpoints require authentication"""
#     # Try to process without auth
#     response = await client.get("/api/v1/extract/jobs")
#
#     # Should get 401 error
#     assert response.status_code == 401
#     assert "Authentication required" in response.json()["detail"]
