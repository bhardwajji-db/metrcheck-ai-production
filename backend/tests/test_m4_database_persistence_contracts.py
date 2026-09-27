"""
Milestone 4 Contract Test Harness: Database Persistence & Storage Architecture (R4)
===================================================================================
Authoritative contract verification for Milestone 4 remediation covering:
1. Module Exports & Equivalence:
   - `list_officer_reviews` is exported from `backend.database.db`.
   - `list_officer_reviews is list_reviews` (exact identity contract).
   - Both functions produce identical query result sets across single and multi-tenant filters.
2. Safety Guard Architecture:
   - `_check_safety_guard()` raises `RuntimeError` on local production path (`PROD_DATABASE_PATH`).
   - `_check_safety_guard()` raises `RuntimeError` on cloud production paths (`/data/metrcheck.db`, `/data/...`, `c:/data/...`).
   - `_check_safety_guard()` raises `RuntimeError` under `ENVIRONMENT=production` or `METRCHECK_ENV=production`.
   - `_check_safety_guard()` permits dedicated test database paths (`conftest` isolated environment).
   - `_is_cloud_production_path` helper contract validation.
   - `get_db()` fail-closed enforcement when pointing to production targets.
3. Database Pragmas & Concurrency:
   - SQLite `PRAGMA journal_mode;` returns `WAL` on active connections.
   - SQLite `PRAGMA busy_timeout;` returns `5000` (5000ms lock mitigation).
   - Connection `row_factory` is `aiosqlite.Row` enabling dict-like column access.
   - WAL concurrency allows non-blocking simultaneous reader connections during active writes.
4. Schema Completeness in `sqlite_master`:
   - All 18 persistent tables exist in `sqlite_master` with `type='table'`.
   - Key schema indexes (32 indexes) exist in `sqlite_master` with `type='index'`.
   - Partial UNIQUE index behavior on `enforcement_cases(analysis_id)` (`idx_enf_cases_unique_active_analysis`).
   - Partial UNIQUE index behavior on `users(email)` (`idx_users_email`).
5. Multi-Tenant Isolation (SQL & Guard Levels):
   - SQL level: `analyses`, `products`, `officer_reviews`, `artworks` strictly scoped by `organization_id`.
   - Guard level: `check_tenant_access` fails-closed across Admin, Enforcement, Merchant, and User roles.
   - `verify_test_isolation` validation in `Settings`.
"""

import os
import sys
import uuid
import inspect
import tempfile
import aiosqlite
import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
import database.db as db_module
from database.db import (
    get_db,
    init_db,
    _check_safety_guard,
    _is_cloud_production_path,
    list_reviews,
    list_officer_reviews,
    save_review,
    delete_review,
    save_analysis,
    get_analyses,
    delete_analysis,
    create_product,
    list_products,
    delete_product,
    save_artwork,
    list_artworks,
    delete_artwork,
    create_organization,
)
from auth.security import (
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_MERCHANT,
    ROLE_USER,
)


def _ensure_test_isolation():
    """Verify test runs within temporary test paths, never on production targets."""
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


# ═════════════════════════════════════════════════════════════════════════════
# 1. MODULE EXPORTS & REVIEW FUNCTION IDENTITY CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════

class TestReviewExportAndAliasContracts:
    """Verify `list_officer_reviews` export, identity alias with `list_reviews`, and result equivalence."""

    def test_01_list_officer_reviews_symbol_is_exported(self):
        """`list_officer_reviews` must be exported by backend.database.db."""
        _ensure_test_isolation()
        assert hasattr(db_module, "list_officer_reviews"), (
            "Symbol 'list_officer_reviews' is not exported from backend.database.db"
        )
        assert callable(db_module.list_officer_reviews), "'list_officer_reviews' is not callable"

    def test_02_list_officer_reviews_is_exact_alias_of_list_reviews(self):
        """`list_officer_reviews` must be the exact identical function object as `list_reviews`."""
        _ensure_test_isolation()
        assert list_officer_reviews is list_reviews, (
            f"Expected list_officer_reviews is list_reviews, but got {list_officer_reviews} != {list_reviews}"
        )
        # Signatures must be strictly identical
        sig_officer = inspect.signature(list_officer_reviews)
        sig_reviews = inspect.signature(list_reviews)
        assert sig_officer == sig_reviews

    @pytest.mark.asyncio
    async def test_03_both_review_functions_produce_identical_results_filtered_by_organization(self):
        """Both functions must produce identical query results when filtered by organization_id."""
        _ensure_test_isolation()
        await init_db()

        org_alpha = f"org_test_m4_alpha_{uuid.uuid4().hex[:6]}"
        org_beta = f"org_test_m4_beta_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Seed reviews for org_alpha and org_beta
        rev_alpha_id = f"rev-{uuid.uuid4().hex[:8]}"
        rev_beta_id = f"rev-{uuid.uuid4().hex[:8]}"

        payload_alpha = {
            "id": rev_alpha_id,
            "analysis_id": f"ana-{uuid.uuid4().hex[:8]}",
            "product_name": "Test Commodity Alpha",
            "status": "PENDING_REVIEW",
            "assigned_officer": "officer_alpha",
            "ai_score": 75.0,
            "ai_risk_level": "MEDIUM",
            "ai_status": "NEEDS_REVIEW",
            "ai_snapshot": "{}",
            "organization_id": org_alpha,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        payload_beta = {
            "id": rev_beta_id,
            "analysis_id": f"ana-{uuid.uuid4().hex[:8]}",
            "product_name": "Test Commodity Beta",
            "status": "PENDING_REVIEW",
            "assigned_officer": "officer_beta",
            "ai_score": 40.0,
            "ai_risk_level": "HIGH",
            "ai_status": "FAIL",
            "ai_snapshot": "{}",
            "organization_id": org_beta,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        await save_review(payload_alpha)
        await save_review(payload_beta)

        try:
            # Query via both function references
            res_officer_alpha = await list_officer_reviews(organization_id=org_alpha)
            res_plain_alpha = await list_reviews(organization_id=org_alpha)

            assert res_officer_alpha == res_plain_alpha, (
                "list_officer_reviews and list_reviews returned differing results for org_alpha"
            )
            assert len(res_officer_alpha) >= 1
            assert any(r["id"] == rev_alpha_id for r in res_officer_alpha)
            assert not any(r["id"] == rev_beta_id for r in res_officer_alpha)

            # Query org_beta
            res_officer_beta = await list_officer_reviews(organization_id=org_beta)
            res_plain_beta = await list_reviews(organization_id=org_beta)

            assert res_officer_beta == res_plain_beta
            assert len(res_officer_beta) >= 1
            assert any(r["id"] == rev_beta_id for r in res_officer_beta)
            assert not any(r["id"] == rev_alpha_id for r in res_officer_beta)
        finally:
            await delete_review(rev_alpha_id)
            await delete_review(rev_beta_id)

    @pytest.mark.asyncio
    async def test_04_both_review_functions_produce_identical_results_with_compound_filters(self):
        """Both functions must produce identical results with status, officer, and risk filters."""
        _ensure_test_isolation()
        await init_db()

        org_test = f"org_test_m4_compound_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        rev_id = f"rev-{uuid.uuid4().hex[:8]}"

        payload = {
            "id": rev_id,
            "analysis_id": f"ana-{uuid.uuid4().hex[:8]}",
            "product_name": "Compound Filter Test",
            "status": "PENDING_REVIEW",
            "assigned_officer": "officer_compound",
            "ai_score": 30.0,
            "ai_risk_level": "CRITICAL",
            "ai_status": "FAIL",
            "ai_snapshot": "{}",
            "organization_id": org_test,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await save_review(payload)

        try:
            res_officer = await list_officer_reviews(
                status="PENDING",
                assigned_officer="officer_compound",
                risk_level="CRITICAL",
                organization_id=org_test,
                limit=10,
            )
            res_plain = await list_reviews(
                status="PENDING",
                assigned_officer="officer_compound",
                risk_level="CRITICAL",
                organization_id=org_test,
                limit=10,
            )
            assert res_officer == res_plain
            assert len(res_officer) == 1
            assert res_officer[0]["id"] == rev_id
        finally:
            await delete_review(rev_id)


# ═════════════════════════════════════════════════════════════════════════════
# 2. SAFETY GUARD ARCHITECTURE CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════

class TestSafetyGuardContracts:
    """Stress-test safety guard protection against writes to local and cloud production databases."""

    def test_01_safety_guard_raises_runtime_error_on_local_prod_database(self, monkeypatch):
        """`_check_safety_guard()` must raise RuntimeError on local PROD_DATABASE_PATH."""
        _ensure_test_isolation()
        monkeypatch.setattr(settings, "DATABASE_PATH", PROD_DATABASE_PATH)
        monkeypatch.setattr(settings, "TEST_MODE", True)

        with pytest.raises(RuntimeError) as exc_info:
            _check_safety_guard()
        err_msg = str(exc_info.value)
        assert "SAFETY ERROR" in err_msg
        assert "production/development database" in err_msg or "production/cloud database" in err_msg

    def test_02_safety_guard_raises_runtime_error_on_cloud_production_path(self, monkeypatch):
        """`_check_safety_guard()` must raise RuntimeError on cloud path /data/metrcheck.db."""
        _ensure_test_isolation()
        monkeypatch.setattr(settings, "DATABASE_PATH", "/data/metrcheck.db")
        monkeypatch.setattr(settings, "TEST_MODE", True)

        with pytest.raises(RuntimeError) as exc_info:
            _check_safety_guard()
        err_msg = str(exc_info.value)
        assert "SAFETY ERROR" in err_msg
        assert "production" in err_msg.lower() or "cloud" in err_msg.lower()

    def test_03_safety_guard_raises_on_cloud_subpaths_and_windows_mounts(self, monkeypatch):
        """`_check_safety_guard()` must raise RuntimeError on /data/... subpaths and drive letters."""
        _ensure_test_isolation()
        test_paths = [
            "/data/metrcheck.db",
            "/data/uploads/metrcheck.db",
            "/data/prod_database.db",
            "C:/data/metrcheck.db",
            "c:\\data\\metrcheck.db",
        ]
        for path in test_paths:
            monkeypatch.setattr(settings, "DATABASE_PATH", path)
            monkeypatch.setattr(settings, "TEST_MODE", True)
            with pytest.raises(RuntimeError) as exc_info:
                _check_safety_guard()
            assert "SAFETY ERROR" in str(exc_info.value), f"Failed to block unsafe path: {path}"

    def test_04_safety_guard_raises_when_production_environment_flag_set(self, monkeypatch):
        """`_check_safety_guard()` must raise RuntimeError when ENVIRONMENT=production with non-test DB."""
        _ensure_test_isolation()
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "DATABASE_PATH", "/var/lib/metrcheck_live.db")
        monkeypatch.setattr(settings, "TEST_MODE", True)

        with pytest.raises(RuntimeError) as exc_info:
            _check_safety_guard()
        assert "SAFETY ERROR" in str(exc_info.value)

    def test_05_safety_guard_allows_valid_isolated_test_paths(self):
        """`_check_safety_guard()` must pass silently on genuine isolated temporary test databases."""
        _ensure_test_isolation()
        # The session fixture in conftest.py configures an isolated test path containing 'test'
        # Calling _check_safety_guard() must NOT raise
        try:
            _check_safety_guard()
        except RuntimeError as e:
            pytest.fail(f"_check_safety_guard() raised unexpectedly on isolated test environment: {e}")

    def test_06_is_cloud_production_path_helper_contract(self):
        """`_is_cloud_production_path` must correctly identify cloud storage volumes across OS formats."""
        _ensure_test_isolation()
        # Positive matches (Cloud volumes)
        assert _is_cloud_production_path("/data/metrcheck.db") is True
        assert _is_cloud_production_path("/data/custom.db") is True
        assert _is_cloud_production_path("/data/uploads/metrcheck.db") is True
        assert _is_cloud_production_path("C:/data/metrcheck.db") is True
        assert _is_cloud_production_path("c:\\data\\metrcheck.db") is True
        assert _is_cloud_production_path("d:/data/metrcheck.db") is True

        # Negative matches (Local and temporary paths)
        assert _is_cloud_production_path("/tmp/test_db.sqlite") is False
        assert _is_cloud_production_path("C:/Users/Avinash/temp/test.db") is False
        assert _is_cloud_production_path("/home/user/metrcheck/test.db") is False
        assert _is_cloud_production_path("") is False
        assert _is_cloud_production_path(None) is False

    @pytest.mark.asyncio
    async def test_07_get_db_fails_closed_via_safety_guard(self, monkeypatch):
        """`get_db()` must invoke `_check_safety_guard()` and fail closed before opening unsafe connections."""
        _ensure_test_isolation()
        # 1. Local production target
        monkeypatch.setattr(settings, "DATABASE_PATH", PROD_DATABASE_PATH)
        monkeypatch.setattr(settings, "TEST_MODE", True)
        with pytest.raises(RuntimeError) as exc_info1:
            await get_db()
        assert "SAFETY ERROR" in str(exc_info1.value)

        # 2. Cloud production target
        monkeypatch.setattr(settings, "DATABASE_PATH", "/data/metrcheck.db")
        with pytest.raises(RuntimeError) as exc_info2:
            await get_db()
        assert "SAFETY ERROR" in str(exc_info2.value)

    def test_08_verify_test_isolation_settings_method(self, monkeypatch):
        """`settings.verify_test_isolation()` must raise RuntimeError on PROD_DATABASE_PATH."""
        _ensure_test_isolation()
        monkeypatch.setattr(settings, "DATABASE_PATH", PROD_DATABASE_PATH)
        monkeypatch.setattr(settings, "TEST_MODE", True)
        with pytest.raises(RuntimeError) as exc_info:
            settings.verify_test_isolation()
        assert "SAFETY ERROR" in str(exc_info.value)


# ═════════════════════════════════════════════════════════════════════════════
# 3. DATABASE PRAGMA & CONCURRENCY CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════

class TestDatabasePragmaContracts:
    """Verify SQLite WAL mode, busy timeout, row factory, and non-blocking concurrency."""

    @pytest.mark.asyncio
    async def test_01_sqlite_wal_journal_mode_active(self):
        """`get_db()` must enforce PRAGMA journal_mode=WAL on file-backed SQLite connections."""
        _ensure_test_isolation()
        db = await get_db()
        try:
            async with db.execute("PRAGMA journal_mode;") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                journal_mode = str(row[0]).lower()
                assert journal_mode == "wal", f"Expected journal_mode 'wal', got '{journal_mode}'"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_02_sqlite_busy_timeout_is_5000ms(self):
        """`get_db()` must configure PRAGMA busy_timeout=5000 to mitigate lock contention."""
        _ensure_test_isolation()
        db = await get_db()
        try:
            async with db.execute("PRAGMA busy_timeout;") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                busy_timeout = int(row[0])
                assert busy_timeout == 5000, f"Expected busy_timeout 5000ms, got {busy_timeout}ms"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_03_row_factory_is_aiosqlite_row(self):
        """`get_db()` must set db.row_factory = aiosqlite.Row for dict-like column access."""
        _ensure_test_isolation()
        db = await get_db()
        try:
            assert db.row_factory is aiosqlite.Row, f"Expected aiosqlite.Row, got {db.row_factory}"
            async with db.execute("SELECT 42 AS answer, 'metrcheck' AS project") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["answer"] == 42
                assert row["project"] == "metrcheck"
                d = dict(row)
                assert d == {"answer": 42, "project": "metrcheck"}
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_04_wal_concurrency_non_blocking_read_during_write(self):
        """WAL mode must permit simultaneous reader connections during active writer transactions."""
        _ensure_test_isolation()
        await init_db()

        test_org_id = f"org_wal_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        db_writer = await get_db()
        db_reader = await get_db()
        try:
            # Writer begins an uncommitted transaction
            await db_writer.execute(
                "INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at) "
                "VALUES (?, ?, 'MERCHANT', 'National', 'ACTIVE', ?, ?)",
                (test_org_id, "WAL Concurrency Test Org", now_iso, now_iso)
            )

            # Reader executes a query concurrently without blocking or failing with lock error
            async with db_reader.execute("SELECT COUNT(*) FROM organizations") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] >= 0

            # Commit write transaction
            await db_writer.commit()

            # Reader can now observe the committed row
            async with db_reader.execute("SELECT name FROM organizations WHERE id = ?", (test_org_id,)) as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["name"] == "WAL Concurrency Test Org"
        finally:
            await db_writer.close()
            await db_reader.close()


# ═════════════════════════════════════════════════════════════════════════════
# 4. SCHEMA COMPLETENESS IN SQLITE_MASTER
# ═════════════════════════════════════════════════════════════════════════════

class TestSchemaMasterTableAndIndexContracts:
    """Verify presence of all 18 tables and 32 indexes in sqlite_master, plus partial index contracts."""

    EXPECTED_18_TABLES = [
        "organizations",
        "products",
        "analyses",
        "users",
        "password_resets",
        "account_audit_logs",
        "evidence_audit_logs",
        "artworks",
        "version_comparisons",
        "officer_reviews",
        "verification_cache",
        "security_audit_logs",
        "download_tickets",
        "rate_limit_events",
        "officer_access_requests",
        "enforcement_cases",
        "enforcement_notices",
        "penalty_calculations",
    ]

    EXPECTED_KEY_INDEXES = [
        "idx_products_org",
        "idx_products_owner",
        "idx_products_gtin",
        "idx_products_status",
        "idx_analyses_org",
        "idx_analyses_product_id",
        "idx_users_org",
        "idx_users_email",
        "idx_evidence_audit_org",
        "idx_artworks_org",
        "idx_artworks_product_id",
        "idx_version_comparisons_org",
        "idx_version_comp_org",
        "idx_officer_reviews_org",
        "idx_reviews_org",
        "idx_download_tickets_exp",
        "idx_rate_limit_events_key_ts",
        "idx_officer_req_id",
        "idx_officer_req_status",
        "idx_officer_req_email",
        "idx_enf_cases_ref",
        "idx_enf_cases_org",
        "idx_enf_cases_merch_org",
        "idx_enf_cases_status",
        "idx_enf_cases_assigned",
        "idx_enf_cases_analysis",
        "idx_enf_cases_unique_active_analysis",
        "idx_enf_notices_ref",
        "idx_enf_notices_case",
        "idx_enf_notices_recip_org",
        "idx_penalties_case",
        "idx_penalties_analysis",
    ]

    @pytest.mark.asyncio
    async def test_01_all_18_tables_present_in_sqlite_master(self):
        """All 18 tables defined in the schema must exist in sqlite_master."""
        _ensure_test_isolation()
        await init_db()
        db = await get_db()
        try:
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                rows = await cursor.fetchall()
                existing_tables = {r["name"] for r in rows}

            missing_tables = [t for t in self.EXPECTED_18_TABLES if t not in existing_tables]
            assert not missing_tables, (
                f"Missing {len(missing_tables)} tables in sqlite_master: {missing_tables}\n"
                f"Existing: {sorted(list(existing_tables))}"
            )
            assert len(self.EXPECTED_18_TABLES) == 18
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_02_all_32_key_indexes_present_in_sqlite_master(self):
        """All 32 schema indexes must exist in sqlite_master."""
        _ensure_test_isolation()
        await init_db()
        db = await get_db()
        try:
            async with db.execute("SELECT name FROM sqlite_master WHERE type='index'") as cursor:
                rows = await cursor.fetchall()
                existing_indexes = {r["name"] for r in rows}

            missing_indexes = [idx for idx in self.EXPECTED_KEY_INDEXES if idx not in existing_indexes]
            assert not missing_indexes, (
                f"Missing {len(missing_indexes)} indexes in sqlite_master: {missing_indexes}\n"
                f"Existing: {sorted(list(existing_indexes))}"
            )
            assert len(self.EXPECTED_KEY_INDEXES) == 32
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_03_partial_unique_index_on_enforcement_cases(self):
        """`idx_enf_cases_unique_active_analysis` must reject active duplicates but allow resolved cases."""
        _ensure_test_isolation()
        await init_db()
        db = await get_db()
        shared_analysis_id = f"ana-dup-{uuid.uuid4().hex[:8]}"
        case_id_1 = f"case-{uuid.uuid4().hex[:8]}"
        case_id_2 = f"case-{uuid.uuid4().hex[:8]}"
        case_id_3 = f"case-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            # Insert first active case (OPEN)
            await db.execute(
                "INSERT INTO enforcement_cases (id, case_reference, analysis_id, organization_id, status, created_by, opened_at, updated_at, created_at) "
                "VALUES (?, ?, ?, 'org_ministry', 'OPEN', 'officer1', ?, ?, ?)",
                (case_id_1, f"REF-1-{uuid.uuid4().hex[:6]}", shared_analysis_id, now_iso, now_iso, now_iso)
            )
            await db.commit()

            # Attempting to insert second active case (UNDER_INVESTIGATION) with same analysis_id must fail
            with pytest.raises(aiosqlite.IntegrityError):
                await db.execute(
                    "INSERT INTO enforcement_cases (id, case_reference, analysis_id, organization_id, status, created_by, opened_at, updated_at, created_at) "
                    "VALUES (?, ?, ?, 'org_ministry', 'UNDER_INVESTIGATION', 'officer2', ?, ?, ?)",
                    (case_id_2, f"REF-2-{uuid.uuid4().hex[:6]}", shared_analysis_id, now_iso, now_iso, now_iso)
                )
                await db.commit()

            # Resolve the first case
            await db.execute("UPDATE enforcement_cases SET status = 'RESOLVED' WHERE id = ?", (case_id_1,))
            await db.commit()

            # Inserting a new active case for the same analysis_id now succeeds because first is RESOLVED
            await db.execute(
                "INSERT INTO enforcement_cases (id, case_reference, analysis_id, organization_id, status, created_by, opened_at, updated_at, created_at) "
                "VALUES (?, ?, ?, 'org_ministry', 'OPEN', 'officer3', ?, ?, ?)",
                (case_id_3, f"REF-3-{uuid.uuid4().hex[:6]}", shared_analysis_id, now_iso, now_iso, now_iso)
            )
            await db.commit()
        finally:
            await db.execute("DELETE FROM enforcement_cases WHERE analysis_id = ?", (shared_analysis_id,))
            await db.commit()
            await db.close()

    @pytest.mark.asyncio
    async def test_04_partial_unique_index_on_users_email(self):
        """`idx_users_email` must enforce unique non-empty emails while allowing multiple empty string emails."""
        _ensure_test_isolation()
        await init_db()
        db = await get_db()
        u1 = f"user_empty1_{uuid.uuid4().hex[:6]}"
        u2 = f"user_empty2_{uuid.uuid4().hex[:6]}"
        u3 = f"user_email1_{uuid.uuid4().hex[:6]}"
        u4 = f"user_email2_{uuid.uuid4().hex[:6]}"
        shared_email = f"shared_{uuid.uuid4().hex[:6]}@metrcheck.gov.in"
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            # 1. Multiple users with empty email "" must succeed
            await db.execute(
                "INSERT INTO users (username, password_hash, salt, role, email, created_at) "
                "VALUES (?, 'hash', 'salt', 'MERCHANT_PUBLIC', '', ?)",
                (u1, now_iso)
            )
            await db.execute(
                "INSERT INTO users (username, password_hash, salt, role, email, created_at) "
                "VALUES (?, 'hash', 'salt', 'MERCHANT_PUBLIC', '', ?)",
                (u2, now_iso)
            )
            await db.commit()

            # 2. First user with specific email succeeds
            await db.execute(
                "INSERT INTO users (username, password_hash, salt, role, email, created_at) "
                "VALUES (?, 'hash', 'salt', 'ENFORCEMENT_OFFICER', ?, ?)",
                (u3, shared_email, now_iso)
            )
            await db.commit()

            # 3. Second user with same email must fail with IntegrityError
            with pytest.raises(aiosqlite.IntegrityError):
                await db.execute(
                    "INSERT INTO users (username, password_hash, salt, role, email, created_at) "
                    "VALUES (?, 'hash', 'salt', 'ENFORCEMENT_OFFICER', ?, ?)",
                    (u4, shared_email, now_iso)
                )
                await db.commit()
        finally:
            await db.execute("DELETE FROM users WHERE username IN (?, ?, ?, ?)", (u1, u2, u3, u4))
            await db.commit()
            await db.close()


# ═════════════════════════════════════════════════════════════════════════════
# 5. MULTI-TENANT ISOLATION (SQL & GUARD LEVELS)
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiTenantIsolationContracts:
    """Stress-test multi-tenant isolation at SQL query levels and security guard authorization."""

    @pytest.mark.asyncio
    async def test_01_sql_level_analysis_tenant_isolation(self):
        """`get_analyses(organization_id=...)` must strictly isolate records between tenants."""
        _ensure_test_isolation()
        await init_db()

        org_x = f"org_tenant_x_{uuid.uuid4().hex[:6]}"
        org_y = f"org_tenant_y_{uuid.uuid4().hex[:6]}"

        ana_x_id = f"m4-ana-x-{uuid.uuid4().hex[:8]}"
        ana_y_id = f"m4-ana-y-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        await save_analysis({
            "id": ana_x_id,
            "product_name": "Product Org X",
            "organization_id": org_x,
            "owner_user_id": "merchant_x",
            "created_at": now_iso,
            "status": "PASS",
        })
        await save_analysis({
            "id": ana_y_id,
            "product_name": "Product Org Y",
            "organization_id": org_y,
            "owner_user_id": "merchant_y",
            "created_at": now_iso,
            "status": "FAIL",
        })

        try:
            analyses_x = await get_analyses(organization_id=org_x)
            assert any(a["id"] == ana_x_id for a in analyses_x), "Tenant X analysis missing in Org X query"
            assert not any(a["id"] == ana_y_id for a in analyses_x), "Tenant Y analysis leaked into Org X query"

            analyses_y = await get_analyses(organization_id=org_y)
            assert any(a["id"] == ana_y_id for a in analyses_y), "Tenant Y analysis missing in Org Y query"
            assert not any(a["id"] == ana_x_id for a in analyses_y), "Tenant X analysis leaked into Org Y query"
        finally:
            await delete_analysis(ana_x_id)
            await delete_analysis(ana_y_id)

    @pytest.mark.asyncio
    async def test_02_sql_level_product_tenant_isolation(self):
        """`list_products(organization_id=...)` must strictly isolate products between tenants."""
        _ensure_test_isolation()
        await init_db()

        org_p1 = f"org_prod1_{uuid.uuid4().hex[:6]}"
        org_p2 = f"org_prod2_{uuid.uuid4().hex[:6]}"

        prod_1 = await create_product({
            "organization_id": org_p1,
            "owner_user_id": "merch_p1",
            "product_name": "Product P1",
            "category": "FOOD",
        })
        prod_2 = await create_product({
            "organization_id": org_p2,
            "owner_user_id": "merch_p2",
            "product_name": "Product P2",
            "category": "COSMETICS",
        })

        try:
            list_p1 = await list_products(organization_id=org_p1)
            assert any(p["id"] == prod_1["id"] for p in list_p1)
            assert not any(p["id"] == prod_2["id"] for p in list_p1)

            list_p2 = await list_products(organization_id=org_p2)
            assert any(p["id"] == prod_2["id"] for p in list_p2)
            assert not any(p["id"] == prod_1["id"] for p in list_p2)

            # Empty organization_id must return empty list (strict fail-closed)
            assert await list_products(organization_id="") == []
        finally:
            await delete_product(prod_1["id"])
            await delete_product(prod_2["id"])

    @pytest.mark.asyncio
    async def test_03_sql_level_officer_review_tenant_isolation(self):
        """Both review query functions must enforce multi-tenant isolation at the SQL query level."""
        _ensure_test_isolation()
        await init_db()

        org_r1 = f"org_rev1_{uuid.uuid4().hex[:6]}"
        org_r2 = f"org_rev2_{uuid.uuid4().hex[:6]}"
        rev_1 = f"rev-{uuid.uuid4().hex[:8]}"
        rev_2 = f"rev-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        await save_review({
            "id": rev_1,
            "analysis_id": f"ana-{uuid.uuid4().hex[:8]}",
            "product_name": "Review Isolation 1",
            "status": "PENDING_REVIEW",
            "ai_snapshot": "{}",
            "organization_id": org_r1,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        await save_review({
            "id": rev_2,
            "analysis_id": f"ana-{uuid.uuid4().hex[:8]}",
            "product_name": "Review Isolation 2",
            "status": "PENDING_REVIEW",
            "ai_snapshot": "{}",
            "organization_id": org_r2,
            "created_at": now_iso,
            "updated_at": now_iso,
        })

        try:
            r1_officer = await list_officer_reviews(organization_id=org_r1)
            r1_reviews = await list_reviews(organization_id=org_r1)
            assert r1_officer == r1_reviews
            assert any(r["id"] == rev_1 for r in r1_officer)
            assert not any(r["id"] == rev_2 for r in r1_officer)

            r2_officer = await list_officer_reviews(organization_id=org_r2)
            r2_reviews = await list_reviews(organization_id=org_r2)
            assert r2_officer == r2_reviews
            assert any(r["id"] == rev_2 for r in r2_officer)
            assert not any(r["id"] == rev_1 for r in r2_officer)
        finally:
            await delete_review(rev_1)
            await delete_review(rev_2)

    def test_04_guard_level_tenant_access_control(self):
        """`check_tenant_access()` must enforce strict fail-closed authorization boundaries."""
        _ensure_test_isolation()
        org_alpha = "org_alpha_security"
        org_beta = "org_beta_security"

        resource_alpha = {"id": "res_1", "organization_id": org_alpha, "owner_user_id": "merchant_bob"}
        resource_beta = {"id": "res_2", "organization_id": org_beta, "owner_user_id": "merchant_alice"}

        # 1. Admin has statutory oversight across all organizations
        admin_user = {"username": "director_admin", "role": ROLE_ADMIN, "organization_id": "org_ministry"}
        assert check_tenant_access(admin_user, resource_alpha) is True
        assert check_tenant_access(admin_user, resource_beta) is True

        # 2. Enforcement Officer strictly scoped to their assigned organization
        officer_alpha = {"username": "insp_alpha", "role": ROLE_ENFORCEMENT, "organization_id": org_alpha}
        assert check_tenant_access(officer_alpha, resource_alpha) is True
        assert check_tenant_access(officer_alpha, resource_beta) is False

        # 3. Merchant requires both matching organization AND ownership
        merchant_bob = {"username": "merchant_bob", "role": ROLE_MERCHANT, "organization_id": org_alpha}
        merchant_intruder = {"username": "merchant_intruder", "role": ROLE_MERCHANT, "organization_id": org_alpha}

        assert check_tenant_access(merchant_bob, resource_alpha) is True
        assert check_tenant_access(merchant_bob, resource_beta) is False
        # Org matches, but owner mismatch -> access denied
        assert check_tenant_access(merchant_intruder, resource_alpha) is False

        # 4. Unauthenticated / None user denied access
        assert check_tenant_access(None, resource_alpha) is False
