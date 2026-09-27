"""
Milestone 4 Adversarial Stress & Multi-Tenant Isolation Verification Suite
==========================================================================
Challenger 2 Empirical Verification Suite for:
1. Multi-tenant isolation boundaries in `backend/auth/security.py:check_tenant_access`
   across all roles (Admin, Officers, Merchants, Public Users, Unknown).
2. Cloud safety guard evasion resistance (`_is_cloud_production_path` and `_check_safety_guard`).
3. Storage path alignment invariants across container and deployment configurations.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from fastapi import HTTPException, status

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import (
    _check_safety_guard,
    _is_cloud_production_path,
    list_reviews,
    list_officer_reviews,
)
from auth.security import (
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
    ROLE_USER,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


# ═════════════════════════════════════════════════════════════════════════════
# 1. ADVERSARIAL MULTI-TENANT ISOLATION BOUNDARY TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialTenantIsolation:
    """Stress tests for `check_tenant_access` across all roles, edge cases, and boundary bypass attempts."""

    # ── Role: ADMIN ──
    def test_admin_global_statutory_oversight(self):
        """Admin has unconstrained statutory oversight across all organizations and ownership."""
        _ensure_test_isolation()
        admin = {"username": "superadmin", "role": ROLE_ADMIN, "organization_id": "org_ministry"}
        
        # Org A resource
        assert check_tenant_access(admin, {"id": "1", "organization_id": "org_a", "owner_user_id": "user_a"}) is True
        # Org B resource
        assert check_tenant_access(admin, {"id": "2", "organization_id": "org_b", "owner_user_id": "user_b"}) is True
        # Unassigned / empty organization resource
        assert check_tenant_access(admin, {"id": "3", "organization_id": "", "owner_user_id": ""}) is True
        # Resource with None organization
        assert check_tenant_access(admin, {"id": "4", "organization_id": None, "owner_user_id": None}) is True

    # ── Role: ENFORCEMENT & AUDIT OFFICERS ──
    def test_officer_scoped_strictly_to_assigned_organization(self):
        """Officers can only access resources matching their exact organization_id."""
        _ensure_test_isolation()
        officer = {"username": "officer_kaul", "role": ROLE_ENFORCEMENT, "organization_id": "org_north"}
        audit_off = {"username": "auditor_rao", "role": ROLE_AUDIT, "organization_id": "org_north"}

        # Matching org resource -> Allowed
        res_matching = {"id": "r1", "organization_id": "org_north", "owner_user_id": "merchant_x"}
        assert check_tenant_access(officer, res_matching) is True
        assert check_tenant_access(audit_off, res_matching) is True

        # Cross-tenant org resource -> Strictly Denied
        res_cross = {"id": "r2", "organization_id": "org_south", "owner_user_id": "merchant_y"}
        assert check_tenant_access(officer, res_cross) is False
        assert check_tenant_access(audit_off, res_cross) is False

        # Cross-tenant with exception raising
        with pytest.raises(HTTPException) as exc_info:
            check_tenant_access(officer, res_cross, raise_exception=True)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_officer_fails_closed_when_officer_org_is_missing_or_whitespace(self):
        """Officers with missing or unassigned organization cannot access any organizational resource."""
        _ensure_test_isolation()
        res_org = {"id": "r1", "organization_id": "org_north", "owner_user_id": "merchant_x"}
        
        for blank_org in ["", "   ", None]:
            unassigned_officer = {"username": "officer_roaming", "role": ROLE_ENFORCEMENT, "organization_id": blank_org}
            assert check_tenant_access(unassigned_officer, res_org) is False
            with pytest.raises(HTTPException) as exc:
                check_tenant_access(unassigned_officer, res_org, raise_exception=True)
            assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_officer_fails_closed_on_unassigned_or_legacy_resources(self):
        """Officers cannot access resources where resource.organization_id is empty or None."""
        _ensure_test_isolation()
        officer = {"username": "officer_kaul", "role": ROLE_ENFORCEMENT, "organization_id": "org_north"}

        for blank_org in ["", "   ", None]:
            legacy_res = {"id": "r_legacy", "organization_id": blank_org, "owner_user_id": "merchant_x"}
            assert check_tenant_access(officer, legacy_res) is False
            with pytest.raises(HTTPException) as exc:
                check_tenant_access(officer, legacy_res, raise_exception=True)
            assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_officer_org_whitespace_stripping_robustness(self):
        """Verify that organization_ids with leading/trailing whitespace match correctly after stripping."""
        _ensure_test_isolation()
        officer = {"username": "officer_kaul", "role": ROLE_ENFORCEMENT, "organization_id": "  org_north  "}
        res = {"id": "r1", "organization_id": "org_north", "owner_user_id": "merchant_x"}
        assert check_tenant_access(officer, res) is True

    # ── Role: MERCHANT_PUBLIC ──
    def test_merchant_requires_both_org_match_and_ownership(self):
        """Merchants must satisfy BOTH organization_id match AND owner_user_id ownership."""
        _ensure_test_isolation()
        merchant_alice = {
            "username": "alice",
            "role": ROLE_MERCHANT,
            "organization_id": "org_fmcg",
            "id": 101,
        }

        # Case 1: Matching org AND matching username owner -> ALLOWED
        res_owned_by_username = {"id": "p1", "organization_id": "org_fmcg", "owner_user_id": "alice"}
        assert check_tenant_access(merchant_alice, res_owned_by_username) is True

        # Case 2: Matching org AND matching user id owner -> ALLOWED
        res_owned_by_id = {"id": "p2", "organization_id": "org_fmcg", "owner_user_id": "101"}
        assert check_tenant_access(merchant_alice, res_owned_by_id) is True

        # Case 3: Matching org BUT owned by different merchant (intruder attack) -> DENIED
        res_other_merchant = {"id": "p3", "organization_id": "org_fmcg", "owner_user_id": "bob"}
        assert check_tenant_access(merchant_alice, res_other_merchant) is False
        with pytest.raises(HTTPException) as exc:
            check_tenant_access(merchant_alice, res_other_merchant, raise_exception=True)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

        # Case 4: Different org BUT matching owner (cross-tenant spoof) -> DENIED
        res_spoofed_org = {"id": "p4", "organization_id": "org_competitor", "owner_user_id": "alice"}
        assert check_tenant_access(merchant_alice, res_spoofed_org) is False
        with pytest.raises(HTTPException) as exc:
            check_tenant_access(merchant_alice, res_spoofed_org, raise_exception=True)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

        # Case 5: Matching org BUT empty owner -> DENIED
        res_no_owner = {"id": "p5", "organization_id": "org_fmcg", "owner_user_id": ""}
        assert check_tenant_access(merchant_alice, res_no_owner) is False

    def test_merchant_case_insensitive_ownership(self):
        """Merchant username comparison must be case-insensitive ('Alice' == 'alice')."""
        _ensure_test_isolation()
        merchant = {"username": "Alice_Packaging", "role": ROLE_MERCHANT, "organization_id": "org_dairy"}
        res = {"id": "p1", "organization_id": "org_dairy", "owner_user_id": "alice_packaging"}
        assert check_tenant_access(merchant, res) is True

    # ── Role: PUBLIC USER / NORMAL USER ──
    def test_public_user_strictly_scoped_by_personal_ownership(self):
        """Public users have access solely to resources where owner_user_id matches their username or ID."""
        _ensure_test_isolation()
        for role_variant in [ROLE_USER, "NORMAL_USER", "USER", "PUBLIC_USER"]:
            user = {"username": "consumer_sharma", "role": role_variant, "id": 555}

            # Owned by username -> Allowed
            res_owned = {"id": "c1", "organization_id": "", "owner_user_id": "consumer_sharma"}
            assert check_tenant_access(user, res_owned) is True

            # Owned by ID -> Allowed
            res_owned_id = {"id": "c2", "organization_id": "", "owner_user_id": "555"}
            assert check_tenant_access(user, res_owned_id) is True

            # Owned by another user -> Denied
            res_other = {"id": "c3", "organization_id": "", "owner_user_id": "consumer_verma"}
            assert check_tenant_access(user, res_other) is False
            with pytest.raises(HTTPException) as exc:
                check_tenant_access(user, res_other, raise_exception=True)
            assert exc.value.status_code == status.HTTP_403_FORBIDDEN

            # Unowned resource -> Denied
            res_unowned = {"id": "c4", "organization_id": "", "owner_user_id": ""}
            assert check_tenant_access(user, res_unowned) is False

    # ── Edge Cases: Missing / Unauthenticated / Null / Unknown Roles ──
    def test_unauthenticated_and_null_users(self):
        """Unauthenticated (None or empty) users must fail closed unless allow_public=True."""
        _ensure_test_isolation()
        res = {"id": "r1", "organization_id": "org_a", "owner_user_id": "user_a"}

        # None user without allow_public -> False or 401
        assert check_tenant_access(None, res) is False
        with pytest.raises(HTTPException) as exc1:
            check_tenant_access(None, res, raise_exception=True)
        assert exc1.value.status_code == status.HTTP_401_UNAUTHORIZED

        # Empty dict user -> False or 401
        assert check_tenant_access({}, res) is False
        with pytest.raises(HTTPException) as exc2:
            check_tenant_access({}, res, raise_exception=True)
        assert exc2.value.status_code == status.HTTP_401_UNAUTHORIZED

        # allow_public=True permits unauthenticated access
        assert check_tenant_access(None, res, allow_public=True) is True
        assert check_tenant_access({}, res, allow_public=True) is True

    def test_missing_resource_fails_closed(self):
        """Missing or None resource must return False or raise 404."""
        _ensure_test_isolation()
        admin = {"username": "admin", "role": ROLE_ADMIN}
        assert check_tenant_access(admin, None) is False
        with pytest.raises(HTTPException) as exc1:
            check_tenant_access(admin, None, raise_exception=True)
        assert exc1.value.status_code == status.HTTP_404_NOT_FOUND

        assert check_tenant_access(admin, {}) is False
        with pytest.raises(HTTPException) as exc2:
            check_tenant_access(admin, {}, raise_exception=True)
        assert exc2.value.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_or_malformed_roles_denied(self):
        """Unknown or arbitrary role strings must fail closed with 403 Forbidden."""
        _ensure_test_isolation()
        res = {"id": "r1", "organization_id": "org_a", "owner_user_id": "attacker"}
        for rogue_role in ["GUEST", "ANONYMOUS", "HACKER", "SYSTEM", ""]:
            user = {"username": "attacker", "role": rogue_role, "organization_id": "org_a"}
            assert check_tenant_access(user, res) is False
            with pytest.raises(HTTPException) as exc:
                check_tenant_access(user, res, raise_exception=True)
            assert exc.value.status_code == status.HTTP_403_FORBIDDEN


# ═════════════════════════════════════════════════════════════════════════════
# 2. ADVERSARIAL CLOUD SAFETY GUARD EVASION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialCloudSafetyGuards:
    """Stress tests for `_is_cloud_production_path` and `_check_safety_guard` evasion vectors."""

    def test_cloud_path_traversal_and_obfuscation(self):
        """Test variations of path traversal, dot segments, and casing targeting /data volume."""
        _ensure_test_isolation()
        blocked_variations = [
            "/data/metrcheck.db",
            "/data/../data/metrcheck.db",
            "/data/./metrcheck.db",
            "/data/subdir/../metrcheck.db",
            "/data",
            "/data/",
            "/data/uploads/metrcheck.db",
            "//data/metrcheck.db",
            "/DATA/METRCHECK.DB",
            "/DaTa/custom.sqlite",
            "C:/data/metrcheck.db",
            "c:\\data\\metrcheck.db",
            "c:/data/../data/metrcheck.db",
            "D:\\DATA\\METRCHECK.DB",
            "e:/data/sub/path/db.sqlite",
        ]
        for p in blocked_variations:
            assert _is_cloud_production_path(p) is True, f"Failed to identify cloud production path: {p}"

    def test_local_and_temporary_paths_are_not_falsely_flagged(self):
        """Ensure legitimate test paths are NOT flagged as cloud production paths."""
        _ensure_test_isolation()
        allowed_paths = [
            "/tmp/test_db.sqlite",
            "/var/tmp/pytest_run.db",
            "c:/Users/Avinash/AppData/Local/Temp/test_db.sqlite",
            "C:\\project\\backend\\tests\\test_isolated.db",
            "/home/user/metrcheck/data_test/test.db",
            "/app/database/test_runner.sqlite",
            "/app/metadata/test.db",  # Contains 'data' substring but not '/data/'
            "c:/database/test.db",
            "",
            None,
        ]
        for p in allowed_paths:
            assert _is_cloud_production_path(p) is False, f"Falsely flagged non-cloud path: {p}"

    def test_safety_guard_blocks_all_cloud_variations_with_runtime_error(self, monkeypatch):
        """`_check_safety_guard()` must raise RuntimeError on any target matching cloud volume."""
        _ensure_test_isolation()
        adversarial_targets = [
            "/data/metrcheck.db",
            "/data/nested/db.sqlite",
            "c:/data/metrcheck.db",
            "C:\\data\\metrcheck.db",
        ]
        for target in adversarial_targets:
            monkeypatch.setattr(settings, "DATABASE_PATH", target)
            monkeypatch.setattr(settings, "TEST_MODE", True)
            with pytest.raises(RuntimeError) as exc:
                _check_safety_guard()
            assert "SAFETY ERROR" in str(exc.value), f"Safety guard did not trigger for {target}"

    def test_safety_guard_blocks_production_environment_without_test_substring(self, monkeypatch):
        """In production environment, any database path not containing 'test' must be rejected."""
        _ensure_test_isolation()
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "DATABASE_PATH", "/srv/databases/app_production.sqlite")
        monkeypatch.setattr(settings, "TEST_MODE", True)

        with pytest.raises(RuntimeError) as exc:
            _check_safety_guard()
        assert "SAFETY ERROR" in str(exc.value)

    def test_safety_guard_allows_production_environment_with_isolated_test_db(self, monkeypatch):
        """If test uses a database file with 'test' in the filename, production flag does not trigger safety block."""
        _ensure_test_isolation()
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "DATABASE_PATH", "/tmp/isolated_test_db.sqlite")
        monkeypatch.setattr(settings, "TEST_MODE", True)

        # Should pass without raising
        _check_safety_guard()


# ═════════════════════════════════════════════════════════════════════════════
# 3. STORAGE PATH ALIGNMENT STATIC INVARIANT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestStorageAlignmentInvariants:
    """Empirically inspect and verify storage path alignment on /data across configuration files."""

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

    def test_dockerfile_storage_alignment(self):
        """Dockerfile must create and configure /data and /data/uploads with non-root permissions."""
        dockerfile = self.PROJECT_ROOT / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile missing at project root"
        content = dockerfile.read_text(encoding="utf-8")

        assert "mkdir -p /data/uploads" in content, "Dockerfile missing mkdir for /data/uploads"
        assert "chown -R 1000:1000 /home/user /data" in content, "Dockerfile missing chown for /data"
        assert "chmod -R 777 /data" in content, "Dockerfile missing chmod for /data"
        assert "UPLOAD_DIR=/data/uploads" in content, "Dockerfile missing UPLOAD_DIR=/data/uploads ENV"
        assert "DATABASE_PATH=/data/metrcheck.db" in content, "Dockerfile missing DATABASE_PATH=/data/metrcheck.db ENV"

    def test_docker_compose_storage_alignment(self):
        """docker-compose.yml must mount ./data:/data volume and configure paths to /data."""
        compose_file = self.PROJECT_ROOT / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml missing at project root"
        content = compose_file.read_text(encoding="utf-8")

        assert "./data:/data" in content, "docker-compose.yml missing volume mount ./data:/data"
        assert "/data/metrcheck.db" in content, "docker-compose.yml missing default /data/metrcheck.db"
        assert "/data/uploads" in content, "docker-compose.yml missing default /data/uploads"

    def test_env_production_example_alignment(self):
        """.env.production.example must declare DATABASE_PATH=/data/metrcheck.db and UPLOAD_DIR=/data/uploads."""
        env_file = self.PROJECT_ROOT / ".env.production.example"
        assert env_file.exists(), ".env.production.example missing at project root"
        content = env_file.read_text(encoding="utf-8")

        assert "DATABASE_PATH=/data/metrcheck.db" in content, (
            ".env.production.example missing DATABASE_PATH=/data/metrcheck.db"
        )
        assert "UPLOAD_DIR=/data/uploads" in content, (
            ".env.production.example missing UPLOAD_DIR=/data/uploads"
        )
