import os
import sys
import hashlib
import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from config import settings, PROD_DATABASE_PATH


def _is_cloud_production_path(path: str) -> bool:
    """
    Determine whether a given filesystem path corresponds to a production
    cloud volume storage location (e.g. Hugging Face Spaces / Docker /data mount).
    """
    if not path:
        return False
    norm = os.path.normpath(str(path)).replace("\\", "/")
    while norm.startswith("//"):
        norm = norm[1:]
    norm_lower = norm.lower()
    # Strip Windows drive letter if present (e.g. 'c:/data/...' -> '/data/...')
    if len(norm_lower) >= 2 and norm_lower[1] == ":" and norm_lower[0].isalpha():
        norm_lower = norm_lower[2:]
    return norm_lower == "/data" or norm_lower.startswith("/data/")


def _check_safety_guard(db_path: Optional[str] = None):
    """
    Safety guard preventing automated tests from running against or mutating
    the production/development database, cloud volume databases (/data/metrcheck.db),
    or databases in active production environments.
    """
    is_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    if settings.TEST_MODE or os.environ.get("TEST_MODE") == "1" or is_pytest:
        target_path = db_path if db_path is not None else settings.DATABASE_PATH
        resolved_db = os.path.abspath(target_path)
        is_cloud_prod = _is_cloud_production_path(target_path) or _is_cloud_production_path(resolved_db)
        is_prod_env = (
            os.environ.get("ENVIRONMENT") == "production"
            or os.environ.get("METRCHECK_ENV") == "production"
            or getattr(settings, "ENVIRONMENT", "").lower() == "production"
        )
        if resolved_db == PROD_DATABASE_PATH or is_cloud_prod or (is_prod_env and "test" not in os.path.basename(resolved_db).lower()):
            raise RuntimeError(
                f"SAFETY ERROR: Automated tests cannot run against the production/cloud database ({resolved_db})!\n"
                f"Please ensure tests use isolated_test_env() or conftest with a dedicated temporary database."
            )


async def get_db():
    _check_safety_guard()
    db = await aiosqlite.connect(settings.DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA busy_timeout=5000;")
    return db



async def init_db():
    db = await get_db()
    try:
        # ── Organizations table (Tenant Isolation) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                org_type TEXT NOT NULL DEFAULT 'MERCHANT',
                jurisdiction TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        for col, typedef in [
            ("org_type", "TEXT NOT NULL DEFAULT 'MERCHANT'"),
            ("jurisdiction", "TEXT DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'ACTIVE'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE organizations ADD COLUMN {col} {typedef}")
                await db.commit()
            except Exception:
                pass

        # Pre-seed canonical root organizations if not present
        now_seed_iso = datetime.now(timezone.utc).isoformat()
        try:
            await db.execute('''
                INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET org_type=excluded.org_type, name=excluded.name, jurisdiction=excluded.jurisdiction
            ''', ("org_ministry", "Ministry of Consumer Affairs & Legal Metrology Directorate", "REGULATOR", "National", "ACTIVE", now_seed_iso, now_seed_iso))
            await db.execute('''
                INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET org_type=excluded.org_type, name=excluded.name, jurisdiction=excluded.jurisdiction
            ''', ("org_merchant_demo", "Demo Merchant Brand Packaging Corp", "MERCHANT", "National", "ACTIVE", now_seed_iso, now_seed_iso))
            await db.commit()
        except Exception:
            pass

        # ── Products table (Merchant Product Catalog Master Record) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                brand_name TEXT DEFAULT '',
                category TEXT DEFAULT 'GENERAL',
                gtin_barcode TEXT DEFAULT '',
                fssai_license TEXT DEFAULT '',
                legal_metrology_license TEXT DEFAULT '',
                net_quantity_declared TEXT DEFAULT '',
                mrp_declared REAL DEFAULT 0.0,
                unit_sale_price_declared TEXT DEFAULT '',
                manufacturer_name TEXT DEFAULT '',
                country_of_origin TEXT DEFAULT 'India',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        for col, typedef in [
            ("brand_name", "TEXT DEFAULT ''"),
            ("category", "TEXT DEFAULT 'GENERAL'"),
            ("gtin_barcode", "TEXT DEFAULT ''"),
            ("fssai_license", "TEXT DEFAULT ''"),
            ("legal_metrology_license", "TEXT DEFAULT ''"),
            ("net_quantity_declared", "TEXT DEFAULT ''"),
            ("mrp_declared", "REAL DEFAULT 0.0"),
            ("unit_sale_price_declared", "TEXT DEFAULT ''"),
            ("manufacturer_name", "TEXT DEFAULT ''"),
            ("country_of_origin", "TEXT DEFAULT 'India'"),
            ("status", "TEXT NOT NULL DEFAULT 'ACTIVE'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE products ADD COLUMN {col} {typedef}")
                await db.commit()
            except Exception:
                pass
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_products_org ON products(organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_products_owner ON products(owner_user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_products_gtin ON products(gtin_barcode)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)")
            await db.commit()
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                product_name TEXT,
                image_filename TEXT,
                ocr_text TEXT,
                extracted_data TEXT,
                compliance_result TEXT,
                score REAL,
                status TEXT,
                created_at TEXT,
                images TEXT,
                owner_user_id TEXT DEFAULT '',
                organization_id TEXT DEFAULT '',
                product_id TEXT DEFAULT ''
            )
        ''')
        await db.commit()
        # Ensure columns exist if table was created previously
        for col, typedef in [
            ("images", "TEXT"),
            ("owner_user_id", "TEXT DEFAULT ''"),
            ("organization_id", "TEXT DEFAULT ''"),
            ("product_id", "TEXT DEFAULT ''"),
            ("integrity_hash", "TEXT DEFAULT ''"),
            ("system_version", "TEXT DEFAULT ''"),
            ("ocr_engine_version", "TEXT DEFAULT ''"),
            ("ruleset_version", "TEXT DEFAULT ''"),
        ]:
            try:
                await db.execute(f"ALTER TABLE analyses ADD COLUMN {col} {typedef}")
                await db.commit()
            except Exception:
                pass
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_analyses_org ON analyses(organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_analyses_product_id ON analyses(product_id)")
            await db.commit()
        except Exception:
            pass

        # ── Users table (role-based access & organization scoping) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'MERCHANT_PUBLIC',
                full_name TEXT DEFAULT '',
                jurisdiction TEXT DEFAULT '',
                email TEXT DEFAULT '',
                organization_id TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                invitation_token_hash TEXT DEFAULT '',
                invitation_expires_at TEXT DEFAULT '',
                invited_at TEXT DEFAULT '',
                activated_at TEXT DEFAULT '',
                token_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # Idempotently ensure email, organization_id and provisioning columns exist
        for col, typedef in [
            ("email", "TEXT DEFAULT ''"),
            ("organization_id", "TEXT DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'ACTIVE'"),
            ("invitation_token_hash", "TEXT DEFAULT ''"),
            ("invitation_expires_at", "TEXT DEFAULT ''"),
            ("invited_at", "TEXT DEFAULT ''"),
            ("activated_at", "TEXT DEFAULT ''"),
            ("token_version", "INTEGER NOT NULL DEFAULT 1"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
                await db.commit()
            except Exception:
                pass

        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id)")
            await db.commit()
        except Exception:
            pass

        # Ensure existing user records have status and token_version populated
        try:
            await db.execute("UPDATE users SET status = 'ACTIVE' WHERE status IS NULL OR status = ''")
            await db.execute("UPDATE users SET token_version = 1 WHERE token_version IS NULL OR token_version < 1")
            await db.commit()
        except Exception:
            pass

        # Ensure canonical root organizations exist
        try:
            await db.execute('''
                INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET org_type=excluded.org_type, name=excluded.name, jurisdiction=excluded.jurisdiction
            ''', ("org_ministry", "Ministry of Consumer Affairs & Legal Metrology Directorate", "REGULATOR", "National", "ACTIVE", now_seed_iso, now_seed_iso))
            await db.execute('''
                INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET org_type=excluded.org_type, name=excluded.name, jurisdiction=excluded.jurisdiction
            ''', ("org_merchant_demo", "Demo Merchant Brand Packaging Corp", "MERCHANT", "National", "ACTIVE", now_seed_iso, now_seed_iso))
            await db.execute('''
                INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET org_type=excluded.org_type, name=excluded.name, jurisdiction=excluded.jurisdiction
            ''', ("org_user_demo", "Personal User Space", "USER", "National", "ACTIVE", now_seed_iso, now_seed_iso))
            await db.commit()
        except Exception:
            pass

        # Automated idempotent backfill for users with missing or empty organization_id
        try:
            async with db.execute("SELECT id, username, role FROM users WHERE organization_id IS NULL OR organization_id = ''") as cursor:
                unassigned_users = await cursor.fetchall()
            for u_row in unassigned_users:
                u_id, u_name, u_role = u_row[0], u_row[1], u_row[2]
                org_id, org_name, org_type = resolve_default_organization_for_user(u_name, u_role)
                if org_id:
                    await db.execute('''
                        INSERT INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO NOTHING
                    ''', (org_id, org_name, org_type, "National", "ACTIVE", now_seed_iso, now_seed_iso))
                    await db.execute("UPDATE users SET organization_id = ? WHERE id = ?", (org_id, u_id))
            await db.commit()
        except Exception:
            pass

        # Idempotently create unique index for non-empty email
        try:
            await db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL AND email != ''"
            )
            await db.commit()
        except Exception:
            pass

        # ── Password Resets table ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # ── Account Security Audit Logs table ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS account_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_username TEXT,
                target_username TEXT,
                event_type TEXT NOT NULL,
                details TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # ── Evidence Audit & Correction Logs table (Section 5) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS evidence_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                actor_username TEXT NOT NULL,
                action_type TEXT NOT NULL,
                previous_value TEXT,
                new_value TEXT,
                comments TEXT,
                organization_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("ALTER TABLE evidence_audit_logs ADD COLUMN organization_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_evidence_audit_org ON evidence_audit_logs(organization_id)")
            await db.commit()
        except Exception:
            pass

        # ── Pre-Print Packaging Artworks table (Section 8) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS artworks (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 1,
                dimensions TEXT NOT NULL DEFAULT '{}',
                dpi REAL NOT NULL DEFAULT 72.0,
                source_identity TEXT NOT NULL DEFAULT 'PRE-PRINT ARTWORK',
                compliance_ruleset TEXT NOT NULL DEFAULT 'Legal Metrology (Packaged Commodities) Rules, 2011',
                parent_artwork_id TEXT,
                iteration_number INTEGER NOT NULL DEFAULT 1,
                workflow_status TEXT NOT NULL DEFAULT 'DRAFT',
                approval_status TEXT NOT NULL DEFAULT 'PENDING',
                approval_record TEXT,
                analysis_result TEXT,
                pages_data TEXT,
                owner_user_id TEXT DEFAULT '',
                organization_id TEXT DEFAULT '',
                product_id TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("ALTER TABLE artworks ADD COLUMN organization_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE artworks ADD COLUMN product_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_artworks_org ON artworks(organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_artworks_product_id ON artworks(product_id)")
            await db.commit()
        except Exception:
            pass

        # ── Version Comparisons table (Section 9) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS version_comparisons (
                id TEXT PRIMARY KEY,
                version_a_id TEXT NOT NULL,
                version_b_id TEXT NOT NULL,
                version_type_a TEXT NOT NULL DEFAULT 'ANALYSIS',
                version_type_b TEXT NOT NULL DEFAULT 'ANALYSIS',
                product_name TEXT DEFAULT '',
                score_a REAL DEFAULT 0.0,
                score_b REAL DEFAULT 0.0,
                score_delta REAL DEFAULT 0.0,
                risk_shift TEXT DEFAULT 'UNCHANGED',
                comparison_result TEXT NOT NULL,
                owner_user_id TEXT DEFAULT '',
                organization_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("ALTER TABLE version_comparisons ADD COLUMN organization_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_version_comparisons_org ON version_comparisons(organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_version_comp_org ON version_comparisons(organization_id)")
            await db.commit()
        except Exception:
            pass

        # ── Officer Reviews table (Section 10) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS officer_reviews (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'ANALYSIS',
                product_name TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                assigned_officer TEXT DEFAULT '',
                assigned_by TEXT DEFAULT '',
                assigned_at TEXT,
                verified_by TEXT DEFAULT '',
                verified_at TEXT,
                final_human_status TEXT DEFAULT '',
                ai_score REAL DEFAULT 0.0,
                ai_risk_level TEXT DEFAULT 'LOW',
                ai_status TEXT DEFAULT 'PASS',
                ai_snapshot TEXT NOT NULL,
                human_verified_result TEXT,
                field_corrections TEXT DEFAULT '[]',
                evidence_modifications TEXT DEFAULT '[]',
                comments TEXT DEFAULT '[]',
                history TEXT DEFAULT '[]',
                organization_id TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("ALTER TABLE officer_reviews ADD COLUMN organization_id TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_officer_reviews_org ON officer_reviews(organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_reviews_org ON officer_reviews(organization_id)")
            await db.commit()
        except Exception:
            pass

        # ── Verification Cache table (Section 13) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS verification_cache (
                identifier_type TEXT NOT NULL,
                identifier_value TEXT NOT NULL,
                record_json TEXT NOT NULL,
                source TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (identifier_type, identifier_value)
            )
        ''')
        await db.commit()

        # ── Security Audit Logs table with cryptographic hash chain (Section 15) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS security_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                actor_username TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                resource_id TEXT DEFAULT '',
                details TEXT DEFAULT '',
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()

        # ── Download Tickets table (SEC-AUD-11: Short-Lived Single-Use Download Tickets) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS download_tickets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT 'download',
                expires_at REAL NOT NULL,
                redeemed_at REAL DEFAULT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_download_tickets_exp ON download_tickets(expires_at)")
            await db.commit()
        except Exception:
            pass

        # ── Rate Limit Events table (SEC-AUD-12: Multi-Worker Distributed Rate Limiting) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS rate_limit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_ts ON rate_limit_events(key, timestamp)")
            await db.commit()
        except Exception:
            pass

        # ── Officer Access Requests table (Phase 1.5) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS officer_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE NOT NULL,
                requested_role TEXT NOT NULL,
                full_name TEXT NOT NULL,
                official_email TEXT NOT NULL,
                mobile_number TEXT NOT NULL,
                employee_officer_id TEXT NOT NULL,
                designation TEXT NOT NULL,
                department_organization TEXT NOT NULL,
                state TEXT NOT NULL,
                district_jurisdiction TEXT NOT NULL,
                office_address TEXT DEFAULT '',
                reason TEXT NOT NULL,
                additional_information TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING',
                submitted_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by TEXT DEFAULT '',
                rejection_reason TEXT DEFAULT '',
                created_user_id TEXT DEFAULT ''
            )
        ''')
        await db.commit()
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_officer_req_id ON officer_access_requests(request_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_officer_req_status ON officer_access_requests(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_officer_req_email ON officer_access_requests(official_email)")
            await db.commit()
        except Exception:
            pass

        # ── Enforcement Cases table (Phase 4B) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS enforcement_cases (
                id TEXT PRIMARY KEY,
                case_reference TEXT UNIQUE NOT NULL,
                analysis_id TEXT NOT NULL,
                review_id TEXT DEFAULT '',
                product_id TEXT DEFAULT '',
                organization_id TEXT NOT NULL,
                merchant_organization_id TEXT DEFAULT '',
                product_name TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'OPEN',
                severity TEXT NOT NULL DEFAULT 'HIGH',
                jurisdiction_state TEXT DEFAULT '',
                jurisdiction_district TEXT DEFAULT '',
                violation_summary TEXT DEFAULT '',
                created_by TEXT NOT NULL,
                assigned_officer TEXT DEFAULT '',
                opened_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT,
                closure_reason TEXT DEFAULT '',
                resolution_type TEXT DEFAULT '',
                timeline TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_cases_ref ON enforcement_cases(case_reference)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_cases_org ON enforcement_cases(organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_cases_merch_org ON enforcement_cases(merchant_organization_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_cases_status ON enforcement_cases(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_cases_assigned ON enforcement_cases(assigned_officer)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_cases_analysis ON enforcement_cases(analysis_id)")
            # Phase 4C.1: DB-level duplicate-active-case prevention.
            # Ensures no two rows share the same analysis_id while both are in an active
            # (non-terminal) state.  RESOLVED and CLOSED are excluded because:
            #  1. Closed cases are legitimate historical records.
            #  2. Reopening (CLOSED→OPEN) updates the SAME row (same id), so the updated
            #     row's analysis_id will be unique within the active set once committed.
            # SQLite supports partial indexes natively (WHERE clause on CREATE INDEX).
            await db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_enf_cases_unique_active_analysis "
                "ON enforcement_cases(analysis_id) "
                "WHERE status NOT IN ('RESOLVED', 'CLOSED')"
            )
            await db.commit()
        except Exception:
            pass

        # ── Enforcement Notices table (Phase 4B) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS enforcement_notices (
                id TEXT PRIMARY KEY,
                notice_reference TEXT UNIQUE NOT NULL,
                case_id TEXT NOT NULL,
                notice_type TEXT NOT NULL DEFAULT 'SHOW_CAUSE',
                status TEXT NOT NULL DEFAULT 'ISSUED',
                issued_by TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                recipient_organization_id TEXT DEFAULT '',
                recipient_name TEXT DEFAULT '',
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                deadline_days INTEGER NOT NULL DEFAULT 15,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_notices_ref ON enforcement_notices(notice_reference)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_notices_case ON enforcement_notices(case_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_enf_notices_recip_org ON enforcement_notices(recipient_organization_id)")
            await db.commit()
        except Exception:
            pass

        # ── Penalty Calculations History table (Phase 4B) ──
        await db.execute('''
            CREATE TABLE IF NOT EXISTS penalty_calculations (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                analysis_id TEXT NOT NULL,
                applicable INTEGER NOT NULL DEFAULT 1,
                estimated_fine_inr REAL NOT NULL DEFAULT 0.0,
                fine_range_min_inr REAL NOT NULL DEFAULT 0.0,
                fine_range_max_inr REAL NOT NULL DEFAULT 0.0,
                basis TEXT NOT NULL,
                sections TEXT NOT NULL DEFAULT '[]',
                repeat_offence INTEGER NOT NULL DEFAULT 0,
                prior_notices INTEGER NOT NULL DEFAULT 0,
                violation_count INTEGER NOT NULL DEFAULT 0,
                calculated_by TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                reason TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        await db.commit()
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_penalties_case ON penalty_calculations(case_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_penalties_analysis ON penalty_calculations(analysis_id)")
            await db.commit()
        except Exception:
            pass

        await db.execute("DELETE FROM analyses WHERE id LIKE 'demo-%' OR id LIKE 'test-%' OR id IN ('1', '2', '3')")
        await db.commit()

        # Seed default accounts for demo/presentation (idempotent)
        await seed_default_users()

        # Phase A-01.3: Automated Idempotent Backfill for Qualifying Historical Analyses into Officer Reviews
        try:
            async with db.execute("""
                SELECT a.id FROM analyses a
                LEFT JOIN officer_reviews r ON r.analysis_id = a.id
                WHERE r.id IS NULL
                AND a.organization_id IS NOT NULL
                AND a.organization_id != ''
                AND UPPER(a.status) IN ('REVIEW REQUIRED', 'POTENTIAL NON-COMPLIANCE', 'FAIL', 'NON_COMPLIANT', 'NEEDS_REVIEW')
            """) as cursor:
                missing_rows = await cursor.fetchall()
            
            if missing_rows:
                from services.review_service import get_or_create_review
                for row in missing_rows:
                    ana_id = row[0]
                    await get_or_create_review(ana_id)
        except Exception:
            pass
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# ORGANIZATIONS (Multi-Tenant Isolation)
# ═══════════════════════════════════════════════════════════════════════

def resolve_default_organization_for_user(username: str, role: str) -> tuple[str, str, str]:
    """
    Authoritative server-side determination of organization ID, Name, and Org Type
    for a user based on their role and username.
    """
    clean_user = (username or "").strip().lower()
    clean_role = (role or "").strip().upper()

    if clean_role in ("ADMIN", "ROLE_ADMIN", "REGULATOR"):
        return "org_ministry", "Ministry of Consumer Affairs & Legal Metrology Directorate", "REGULATOR"
    
    if clean_role in ("ENFORCEMENT_OFFICER", "ROLE_ENFORCEMENT", "AUDIT_OFFICER", "ROLE_AUDIT", "OFFICER"):
        if clean_user in ("officer", "audit"):
            return "org_ministry", "Ministry of Consumer Affairs & Legal Metrology Directorate", "REGULATOR"
        # Unassigned officers remain unassigned until explicitly assigned by Administrator
        return "", "", "REGULATOR"
    
    if clean_role in ("MERCHANT_PUBLIC", "ROLE_MERCHANT", "MERCHANT"):
        if clean_user == "merchant":
            return "org_merchant_demo", "Demo Merchant Brand Packaging Corp", "MERCHANT"
        return f"org_{clean_user}", f"{username.strip()} Enterprise", "MERCHANT"
    
    if clean_role in ("PUBLIC_USER", "NORMAL_USER", "ROLE_USER", "USER"):
        if clean_user == "user":
            return "org_user_demo", "Personal User Space", "USER"
        return f"org_user_{clean_user}", f"{username.strip()} Workspace", "USER"

    # Default fallback
    if clean_user:
        return f"org_{clean_user}", f"{username.strip()} Workspace", "MERCHANT"
    return "org_merchant_demo", "Demo Merchant Brand Packaging Corp", "MERCHANT"


async def _ensure_user_organization(user_dict: Optional[dict]) -> Optional[dict]:
    """
    Ensures that a retrieved user dictionary has a non-empty organization_id,
    and that the corresponding organization row exists in the database.
    If organization_id was missing/empty, it backfills the user row in the database.
    """
    if not user_dict or not isinstance(user_dict, dict):
        return user_dict
    
    user_org = (user_dict.get("organization_id") or "").strip()
    username = (user_dict.get("username") or "").strip()
    role = (user_dict.get("role") or "").strip()
    
    if not user_org and username:
        org_id, org_name, org_type = resolve_default_organization_for_user(username, role)
        if org_id:
            await create_organization(id_or_data=org_id, name=org_name, org_type=org_type, jurisdiction="National", status="ACTIVE")
            db = await get_db()
            try:
                await db.execute("UPDATE users SET organization_id = ? WHERE username = ?", (org_id, username))
                await db.commit()
            finally:
                await db.close()
            user_dict["organization_id"] = org_id
    elif user_org:
        # Ensure the organization record exists
        org = await get_organization(user_org)
        if not org:
            org_id, org_name, org_type = resolve_default_organization_for_user(username, role)
            if org_id:
                await create_organization(id_or_data=user_org, name=org_name or f"{user_org} Organization", org_type=org_type, jurisdiction="National", status="ACTIVE")

    return user_dict


async def create_organization(id_or_data=None, name: str = "", org_type: str = "MERCHANT", jurisdiction: str = "", status: str = "ACTIVE", **kwargs) -> Dict[str, Any]:
    """Create or update an organization. Accepts dict, positional, or keyword arguments."""
    if isinstance(id_or_data, dict):
        d = dict(id_or_data)
        d.update(kwargs)
    elif id_or_data is not None:
        d = {"id": str(id_or_data), "name": name, "org_type": org_type, "jurisdiction": jurisdiction, "status": status}
        d.update(kwargs)
    else:
        d = dict(kwargs)
        if name:
            d.setdefault("name", name)
        if org_type:
            d.setdefault("org_type", org_type)
        if jurisdiction:
            d.setdefault("jurisdiction", jurisdiction)
        if status:
            d.setdefault("status", status)

    org_id = str(d.get("id") or d.get("org_id") or "").strip()
    org_name = str(d.get("name") or "").strip()
    org_t = str(d.get("org_type") or "MERCHANT").strip()
    org_j = str(d.get("jurisdiction") or "").strip()
    org_s = str(d.get("status") or "ACTIVE").strip()

    now_iso = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute('''
            INSERT OR REPLACE INTO organizations (id, name, org_type, jurisdiction, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (org_id, org_name, org_t, org_j, org_s, now_iso, now_iso))
        await db.commit()
        return {
            "id": org_id,
            "name": org_name,
            "org_type": org_t,
            "jurisdiction": org_j,
            "status": org_s,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
    finally:
        await db.close()


async def get_organization(org_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve organization record by ID."""
    if not org_id:
        return None
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM organizations WHERE id = ?', (org_id.strip(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def list_organizations() -> List[Dict[str, Any]]:
    """List all organizations."""
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM organizations ORDER BY name ASC') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


async def save_analysis(data_or_id=None, **kwargs):
    """Save an analysis record. Accepts a dict, an ID string, or keyword arguments."""
    if isinstance(data_or_id, dict):
        data = dict(data_or_id)
        data.update(kwargs)
    elif isinstance(data_or_id, str):
        data = {"id": data_or_id}
        data.update(kwargs)
    else:
        data = dict(kwargs)

    if "analysis_id" in data and "id" not in data:
        data["id"] = data["analysis_id"]

    db = await get_db()
    try:
        ext_data = data.get('extracted_data', {})
        if not isinstance(ext_data, str):
            ext_data = json.dumps(ext_data)
        comp_res = data.get('compliance_result', {})
        if not isinstance(comp_res, str):
            comp_res = json.dumps(comp_res)
        images_val = data.get('images') if data.get('images') is not None else data.get('images_data', [])
        if not isinstance(images_val, str):
            images_val = json.dumps(images_val)
        created_at_val = data.get('created_at') or datetime.now(timezone.utc).isoformat()

        org_id = (data.get('organization_id', '') or '').strip()
        owner_id = (data.get('owner_user_id', '') or '').strip()
        if not org_id and owner_id:
            try:
                user = await get_user_by_username(owner_id)
                if user and user.get('organization_id'):
                    org_id = user['organization_id']
                else:
                    org_id = f"org_{owner_id.lower()}"
                    existing_org = await get_organization(org_id)
                    if not existing_org:
                        await create_organization({"id": org_id, "name": f"{owner_id} Org", "status": "ACTIVE"})
            except Exception:
                pass

        await db.execute('''
            INSERT OR REPLACE INTO analyses (
                id, product_name, image_filename, ocr_text, extracted_data,
                compliance_result, score, status, created_at, images,
                owner_user_id, organization_id, product_id, integrity_hash, system_version, ocr_engine_version, ruleset_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('id', ''),
            data.get('product_name', ''),
            data.get('image_filename', ''),
            data.get('ocr_text', ''),
            ext_data,
            comp_res,
            data.get('score', 0),
            data.get('status', 'PENDING'),
            created_at_val,
            images_val,
            data.get('owner_user_id', '') or '',
            org_id,
            data.get('product_id', '') or '',
            data.get('integrity_hash', '') or '',
            data.get('system_version', '') or '',
            data.get('ocr_engine_version', '') or '',
            data.get('ruleset_version', '') or ''
        ))
        await db.commit()
    finally:
        await db.close()


async def get_analyses(organization_id: Optional[str] = None):
    """Retrieve user screening analyses, optionally filtered by organization_id."""
    db = await get_db()
    try:
        if organization_id:
            async with db.execute(
                "SELECT * FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1', '2', '3') AND organization_id = ? ORDER BY created_at DESC",
                (organization_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        else:
            async with db.execute(
                "SELECT * FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1', '2', '3') ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_analysis(id: str):
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM analyses WHERE id = ?', (id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


def classify_analysis_outcome(analysis: dict) -> str:
    """
    Classify analysis outcome into 'FAILURE', 'NEEDS_REVIEW', or 'COMPLIANT'.
    Authoritative rule outcomes precedence: FAILED > REVIEW > COMPLIANT.
    Score is NEVER used to determine bucket classification.
    """
    cr = analysis.get('compliance_result')
    if isinstance(cr, str):
        try:
            cr = json.loads(cr)
        except Exception:
            cr = None

    if isinstance(cr, dict):
        checks = cr.get('checks')
        if isinstance(checks, list) and len(checks) > 0:
            has_fail = False
            has_review = False
            has_pass = False

            for c in checks:
                st = (c.get('status') if isinstance(c, dict) else getattr(c, 'status', '')) or ''
                st = str(st).upper()
                if st in ('FAIL', 'NON_COMPLIANT', 'FAILED'):
                    has_fail = True
                elif st in ('NEEDS_REVIEW', 'WARNING', 'REVIEW_REQUIRED', 'REVIEW'):
                    has_review = True
                elif st in ('PASS', 'COMPLIANT', 'PASSED'):
                    has_pass = True

            if has_fail:
                return 'FAILURE'
            if has_review:
                return 'NEEDS_REVIEW'
            if has_pass:
                return 'COMPLIANT'
        else:
            failed_count = cr.get('failed_rules')
            if failed_count is not None and failed_count > 0:
                return 'FAILURE'

            needs_review_count = (cr.get('needs_review_rules', 0) or 0) + (cr.get('warning_rules', 0) or 0)
            if needs_review_count > 0:
                return 'NEEDS_REVIEW'

            passed_count = cr.get('passed_rules', 0) or 0
            if passed_count > 0 or str(cr.get('status', '')).upper() == 'COMPLIANT':
                return 'COMPLIANT'

    status_str = str(analysis.get('status') or '').upper()
    if 'FAIL' in status_str or 'NON_COMPLIANCE' in status_str or 'NON-COMPLIANCE' in status_str:
        return 'FAILURE'
    if 'REVIEW' in status_str or 'WARNING' in status_str:
        return 'NEEDS_REVIEW'
    if 'COMPLIANT' in status_str or 'PASS' in status_str:
        return 'COMPLIANT'

    return 'NEEDS_REVIEW'


async def get_stats(user: Optional[dict] = None):
    org_id = user.get("organization_id") if user else None
    role = user.get("role") if user else None

    if role == "ADMIN":
        analyses = await get_analyses()
    elif role in ("ENFORCEMENT_OFFICER", "AUDIT_OFFICER"):
        analyses = await get_analyses(organization_id=org_id)
    elif role == "MERCHANT_PUBLIC":
        analyses = await get_analyses(organization_id=org_id)
        username = (user.get("username") or "").lower()
        user_id_str = str(user.get("id", "")) if user.get("id") is not None else ""
        analyses = [
            a for a in analyses
            if a.get("owner_user_id") and (
                a.get("owner_user_id", "").lower() == username or
                (user_id_str and str(a.get("owner_user_id", "")) == user_id_str)
            )
        ]
    elif role in ("PUBLIC_USER", "NORMAL_USER"):
        all_user_analyses = await get_analyses(organization_id=org_id) if org_id else await get_analyses()
        username = (user.get("username") or "").lower()
        user_id_str = str(user.get("id", "")) if user.get("id") is not None else ""
        analyses = [
            a for a in all_user_analyses
            if a.get("owner_user_id") and (
                a.get("owner_user_id", "").lower() == username or
                (user_id_str and str(a.get("owner_user_id", "")) == user_id_str)
            )
        ]
    elif org_id:
        analyses = await get_analyses(organization_id=org_id)
    else:
        analyses = await get_analyses()

    packages_screened = len(analyses)
    compliant_packages = 0
    review_findings = 0
    failed_findings = 0

    for a in analyses:
        # 1. Package-level verdict
        outcome = classify_analysis_outcome(a)
        if outcome == 'COMPLIANT':
            compliant_packages += 1

        # 2. Finding-level counts (individual compliance requirements)
        cr = a.get('compliance_result')
        if isinstance(cr, str):
            try:
                cr = json.loads(cr)
            except Exception:
                cr = None

        if isinstance(cr, dict):
            checks = cr.get('checks')
            if isinstance(checks, list) and len(checks) > 0:
                for c in checks:
                    st = (c.get('status') if isinstance(c, dict) else getattr(c, 'status', '')) or ''
                    st = str(st).upper()
                    if st in ('FAIL', 'NON_COMPLIANT', 'FAILED'):
                        failed_findings += 1
                    elif st in ('NEEDS_REVIEW', 'WARNING', 'REVIEW_REQUIRED', 'REVIEW'):
                        review_findings += 1
            else:
                failed_findings += int(cr.get('failed_rules', 0) or 0)
                review_findings += int((cr.get('needs_review_rules', 0) or 0) + (cr.get('warning_rules', 0) or 0))

    avg_score = sum(a['score'] for a in analyses) / packages_screened if packages_screened > 0 else 0.0
    return {
        'total_analyzed': packages_screened,
        'packages_screened': packages_screened,
        'compliant': compliant_packages,
        'compliant_packages': compliant_packages,
        'needs_review': review_findings,
        'review_findings': review_findings,
        'failures': failed_findings,
        'failed_findings': failed_findings,
        'violations': failed_findings,
        'average_score': avg_score,
        'recent': analyses[:5]
    }


async def delete_analysis(id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute('DELETE FROM analyses WHERE id = ?', (id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_all_user_analyses() -> int:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1', '2', '3')")
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# USER AUTHENTICATION (role-based access)
# ═══════════════════════════════════════════════════════════════════════

async def create_user(username: str, password_hash: str, salt: str, role: str,
                      full_name: str = "", jurisdiction: str = "", email: str = "",
                      organization_id: str = "") -> bool:
    """Insert a user. Returns False if username or email already exists."""
    import datetime
    resolved_org = organization_id.strip() if organization_id else ""
    if not resolved_org:
        resolved_org, org_name, org_type = resolve_default_organization_for_user(username, role)
    else:
        _, org_name, org_type = resolve_default_organization_for_user(username, role)

    if resolved_org:
        try:
            existing_org = await get_organization(resolved_org)
            if not existing_org:
                await create_organization(
                    id_or_data=resolved_org,
                    name=org_name or f"{resolved_org} Organization",
                    org_type=org_type,
                    jurisdiction=jurisdiction or "National",
                    status="ACTIVE"
                )
        except Exception:
            pass

    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO users (username, password_hash, salt, role, full_name, jurisdiction, email, organization_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, salt, role, full_name, jurisdiction, email.strip().lower() if email else "",
              resolved_org,
              datetime.datetime.now().isoformat(timespec="seconds")))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_user_by_username(username: str):
    db = await get_db()
    row = None
    try:
        async with db.execute('SELECT * FROM users WHERE username = ?', (username,)) as cursor:
            row = await cursor.fetchone()
    finally:
        await db.close()
    if row:
        return await _ensure_user_organization(dict(row))
    return None


async def get_user_by_email(email: str):
    """Lookup user by normalized lowercase email."""
    if not email or not email.strip():
        return None
    normalized = email.strip().lower()
    db = await get_db()
    row = None
    try:
        async with db.execute('SELECT * FROM users WHERE LOWER(email) = ? AND email != ""', (normalized,)) as cursor:
            row = await cursor.fetchone()
    finally:
        await db.close()
    if row:
        return await _ensure_user_organization(dict(row))
    return None


async def get_user_by_identifier(identifier: str):
    """Lookup user by username OR recovery email."""
    if not identifier or not identifier.strip():
        return None
    raw = identifier.strip()
    normalized = raw.lower()
    db = await get_db()
    row = None
    try:
        # First check username exact/case-insensitive
        async with db.execute('SELECT * FROM users WHERE LOWER(username) = ?', (normalized,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            # Then check email
            async with db.execute('SELECT * FROM users WHERE LOWER(email) = ? AND email != ""', (normalized,)) as cursor:
                row = await cursor.fetchone()
    finally:
        await db.close()
    if row:
        return await _ensure_user_organization(dict(row))
    return None


async def list_users(role: str | None = None):
    db = await get_db()
    try:
        if role:
            async with db.execute('SELECT * FROM users WHERE role = ? ORDER BY id', (role,)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute('SELECT * FROM users ORDER BY id') as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()

get_all_users = list_users

async def update_user(username: str, full_name: str = None, jurisdiction: str = None,
                      role: str = None, password_hash: str = None, salt: str = None,
                      email: str = None, organization_id: str = None) -> bool:
    """Update user by username. Only set columns that are not None. Returns True if affected."""
    fields = []
    params = []
    if full_name is not None:
        fields.append("full_name = ?")
        params.append(full_name)
    if jurisdiction is not None:
        fields.append("jurisdiction = ?")
        params.append(jurisdiction)
    if role is not None:
        fields.append("role = ?")
        params.append(role)
    if password_hash is not None:
        fields.append("password_hash = ?")
        params.append(password_hash)
    if salt is not None:
        fields.append("salt = ?")
        params.append(salt)
    if email is not None:
        fields.append("email = ?")
        params.append(email.strip().lower() if email else "")
    if organization_id is not None:
        fields.append("organization_id = ?")
        params.append(organization_id.strip() if organization_id else "")

    if not fields:
        return False

    params.append(username)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE username = ?",
            params
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def create_invited_user(username: str, email: str, role: str, full_name: str = "",
                              jurisdiction: str = "", token_hash: str = "", expires_at: str = "",
                              organization_id: str = "") -> bool:
    """Insert a provisioned user in INVITED status."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO users (
                username, password_hash, salt, role, full_name, jurisdiction, email,
                organization_id, status, invitation_token_hash, invitation_expires_at, invited_at, token_version, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username.strip(),
            "",  # Unset password until activation
            "",
            role,
            full_name.strip(),
            jurisdiction.strip(),
            email.strip().lower() if email else "",
            organization_id.strip() if organization_id else "",
            "INVITED",
            token_hash,
            expires_at,
            now_iso,
            1,
            now_iso
        ))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_valid_invitation(token_hash: str):
    """Lookup user by invitation token hash if status is INVITED and token is unexpired."""
    import datetime
    if not token_hash:
        return None
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM users WHERE invitation_token_hash = ? AND status = 'INVITED' AND invitation_expires_at > ?",
            (token_hash, now_iso)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def activate_user_account(username: str, password_hash: str, salt: str) -> bool:
    """Activate user account: set password, status=ACTIVE, clear token hash, increment token_version."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET password_hash = ?, salt = ?, status = 'ACTIVE', activated_at = ?,
                invitation_token_hash = '', invitation_expires_at = '',
                token_version = token_version + 1
            WHERE username = ? AND status = 'INVITED'
        ''', (password_hash, salt, now_iso, username))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def resend_invitation_record(username: str, token_hash: str, expires_at: str) -> bool:
    """Update invitation token hash and expiration for an INVITED account."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET invitation_token_hash = ?, invitation_expires_at = ?, invited_at = ?
            WHERE username = ? AND status = 'INVITED'
        ''', (token_hash, expires_at, now_iso, username))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def suspend_user(username: str) -> bool:
    """Suspend user account and increment token_version to invalidate active sessions."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET status = 'SUSPENDED', token_version = token_version + 1
            WHERE username = ?
        ''', (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def reactivate_user(username: str) -> bool:
    """Reactivate suspended account."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET status = 'ACTIVE', token_version = token_version + 1
            WHERE username = ? AND status = 'SUSPENDED'
        ''', (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def change_user_role(username: str, new_role: str) -> bool:
    """Change user role and increment token_version to immediately revoke stale permissions."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE users
            SET role = ?, token_version = token_version + 1
            WHERE username = ?
        ''', (new_role, username))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def revoke_invitation(username: str) -> bool:
    """Revoke/delete an account that is currently in INVITED status."""
    db = await get_db()
    try:
        cursor = await db.execute('''
            DELETE FROM users
            WHERE username = ? AND status = 'INVITED'
        ''', (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def log_account_audit_event(actor_username: str, target_username: str, event_type: str,
                                 details: str = "", ip_address: str = "") -> bool:
    """Record security-sensitive account provisioning or lifecycle event."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO account_audit_logs (actor_username, target_username, event_type, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (actor_username, target_username, event_type, details, ip_address, now_iso))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_account_audit_logs(limit: int = 50):
    """Retrieve newest account security audit logs."""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM account_audit_logs ORDER BY id DESC LIMIT ?",
            (int(limit),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# OFFICER ACCESS REQUESTS (Controlled Onboarding & Provisioning)
# ═══════════════════════════════════════════════════════════════════════

async def create_officer_access_request(data: dict) -> dict:
    """Insert a new officer access request with PENDING status."""
    import secrets
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    req_id = data.get("request_id")
    if not req_id:
        req_id = f"OFF-REQ-{secrets.token_hex(3).upper()}"

    db = await get_db()
    try:
        await db.execute('''
            INSERT INTO officer_access_requests (
                request_id, requested_role, full_name, official_email, mobile_number,
                employee_officer_id, designation, department_organization, state,
                district_jurisdiction, office_address, reason, additional_information,
                status, submitted_at, reviewed_at, reviewed_by, rejection_reason, created_user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, NULL, '', '', '')
        ''', (
            req_id,
            data.get("requested_role", "AUDIT_OFFICER"),
            data.get("full_name", "").strip(),
            data.get("official_email", "").strip().lower(),
            data.get("mobile_number", "").strip(),
            data.get("employee_officer_id", "").strip(),
            data.get("designation", "").strip(),
            data.get("department_organization", "").strip(),
            data.get("state", "").strip(),
            data.get("district_jurisdiction", "").strip(),
            data.get("office_address", "").strip() if data.get("office_address") else "",
            data.get("reason", "").strip(),
            data.get("additional_information", "").strip() if data.get("additional_information") else "",
            now_iso
        ))
        await db.commit()
        return await get_officer_access_request_by_id(req_id)
    finally:
        await db.close()


async def get_officer_access_request_by_id(request_id: str) -> Optional[dict]:
    """Lookup officer access request by unique request_id."""
    if not request_id:
        return None
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM officer_access_requests WHERE request_id = ?', (request_id.strip(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def get_pending_officer_request_by_email_and_role(official_email: str, requested_role: str) -> Optional[dict]:
    """Check for existing pending request with same email and requested role."""
    if not official_email or not requested_role:
        return None
    norm_email = official_email.strip().lower()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM officer_access_requests WHERE LOWER(official_email) = ? AND requested_role = ? AND status = 'PENDING'",
            (norm_email, requested_role.strip())
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def list_officer_access_requests(status_filter: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
    """List officer access requests with optional status filtering and search query."""
    query = "SELECT * FROM officer_access_requests WHERE 1=1"
    params = []
    
    if status_filter and status_filter.upper() != "ALL":
        query += " AND status = ?"
        params.append(status_filter.strip().upper())
        
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query += """ AND (
            LOWER(request_id) LIKE ? OR
            LOWER(full_name) LIKE ? OR
            LOWER(official_email) LIKE ? OR
            LOWER(employee_officer_id) LIKE ? OR
            LOWER(department_organization) LIKE ? OR
            LOWER(designation) LIKE ? OR
            LOWER(district_jurisdiction) LIKE ?
        )"""
        params.extend([term] * 7)
        
    query += " ORDER BY id DESC"
    
    db = await get_db()
    try:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


async def approve_officer_access_request(request_id: str, admin_username: str, created_user_id: str) -> bool:
    """Transition officer access request to APPROVED and link provisioned username."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE officer_access_requests
            SET status = 'APPROVED', reviewed_at = ?, reviewed_by = ?, created_user_id = ?
            WHERE request_id = ? AND status = 'PENDING'
        ''', (now_iso, admin_username, created_user_id, request_id.strip()))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def reject_officer_access_request(request_id: str, admin_username: str, rejection_reason: str) -> bool:
    """Transition officer access request to REJECTED with mandatory reason."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute('''
            UPDATE officer_access_requests
            SET status = 'REJECTED', reviewed_at = ?, reviewed_by = ?, rejection_reason = ?
            WHERE request_id = ? AND status = 'PENDING'
        ''', (now_iso, admin_username, rejection_reason.strip(), request_id.strip()))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_user(username: str) -> bool:
    """Delete user by username. Returns True if a row was affected."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM users WHERE username = ?", (username,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def seed_default_users():
    """Create operational demo accounts on first run (idempotent, demo mode only):
       officer / officer123 (ENFORCEMENT_OFFICER, org_ministry)
       audit / audit123   (AUDIT_OFFICER, org_ministry)
       merchant / merchant123 (MERCHANT_PUBLIC, org_merchant_demo)

       NOTE: Admin accounts are NEVER seeded automatically. System administrators
       must be provisioned explicitly via CLI bootstrap (bootstrap_admin.py).
    """
    is_prod = (
        os.environ.get("METRCHECK_ENV") == "production" 
        or os.environ.get("ENVIRONMENT") == "production"
        or getattr(settings, "ENVIRONMENT", "") == "production"
    )
    is_demo_explicit = (
        getattr(settings, "METRCHECK_DEMO_MODE", False) is True
        and os.environ.get("METRCHECK_DEMO_MODE", "true").lower() in ("true", "1")
    )
    if is_prod or not is_demo_explicit:
        return

    from auth.security import hash_password, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT, ROLE_USER

    # Ensure default organizations exist
    await create_organization("org_ministry", "Ministry of Consumer Affairs & Legal Metrology Directorate", org_type="REGULATOR", jurisdiction="National")
    await create_organization("org_merchant_demo", "Demo Merchant Brand Packaging Corp", org_type="MERCHANT", jurisdiction="National")
    await create_organization("org_user_demo", "Personal User Space", org_type="USER", jurisdiction="National")

    defaults = [
        ("officer", "officer123", ROLE_ENFORCEMENT, "Demo Enforcement Officer", "Consumer Affairs & Legal Metrology Directorate", "org_ministry"),
        ("audit", "audit123", ROLE_AUDIT, "Demo Audit Inspector", "Quality & Compliance Verification Directorate", "org_ministry"),
        ("merchant", "merchant123", ROLE_MERCHANT, "Demo Merchant Brand", "Commercial Packager", "org_merchant_demo"),
        ("user", "user123", ROLE_USER, "Demo Consumer User", "Personal Consumer", "org_user_demo"),
    ]
    for username, password, role, full_name, jurisdiction, org_id in defaults:
        existing = await get_user_by_username(username)
        if existing:
            if not (existing.get("organization_id") or "").strip():
                await update_user(username, organization_id=org_id)
            continue
        pw_hash, salt = hash_password(password)
        await create_user(username, pw_hash, salt, role, full_name, jurisdiction, organization_id=org_id)


# ═══════════════════════════════════════════════════════════════════════
# PASSWORD RESETS
# ═══════════════════════════════════════════════════════════════════════

async def create_password_reset_record(username: str, token_hash: str, expires_at: str) -> bool:
    """Store a new password reset token hash and invalidate previous unused tokens for the user."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        # Invalidate existing unused tokens for this user
        await db.execute(
            "UPDATE password_resets SET used_at = ? WHERE username = ? AND used_at IS NULL",
            (now_iso, username)
        )
        # Insert new reset token
        await db.execute('''
            INSERT INTO password_resets (username, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (username, token_hash, expires_at, now_iso))
        await db.commit()
        return True
    except Exception:
        return False
    finally:
        await db.close()


async def get_valid_password_reset(token_hash: str):
    """Retrieve password reset record if it exists, is unused, and not expired."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
            (token_hash, now_iso)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def apply_password_reset(username: str, reset_id: int, new_pw_hash: str, new_salt: str) -> bool:
    """Atomically update user password hash/salt and mark the reset token as used."""
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db = await get_db()
    try:
        # Update user password
        cursor = await db.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (new_pw_hash, new_salt, username)
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return False

        # Mark reset token used
        await db.execute(
            "UPDATE password_resets SET used_at = ? WHERE id = ?",
            (now_iso, reset_id)
        )
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        return False
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# SEARCH + TRENDS (for retrieval facility & dashboard)
# ═══════════════════════════════════════════════════════════════════════

async def search_analyses(query: str = "", status: str = "", organization_id: Optional[str] = None, limit: int = 50):
    """Case-insensitive search over product name / product id / extracted data.
    Returns newest-first, excluding synthetic demo fixtures."""
    db = await get_db()
    try:
        sql = "SELECT * FROM analyses WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1','2','3')"
        params: list = []
        if organization_id:
            sql += " AND organization_id = ?"
            params.append(organization_id)
        q = (query or "").strip()
        if q:
            sql += " AND (LOWER(product_name) LIKE ? OR LOWER(id) LIKE ? OR LOWER(extracted_data) LIKE ?)"
            like = f"%{q.lower()}%"
            params += [like, like, like]
        if status and status.upper() != "ALL":
            sql += " AND UPPER(status) LIKE ?"
            params.append(f"%{status.upper()}%")
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_trend_stats(
    days: int = 14,
    organization_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    user_role: Optional[str] = None
):
    """Daily counts (total / compliant / violations) over the last N days with tenant scoping."""
    import datetime
    db = await get_db()
    try:
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        sql = (
            "SELECT date(created_at) AS d, "
            "COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'COMPLIANT' THEN 1 ELSE 0 END) AS compliant "
            "FROM analyses "
            "WHERE id NOT LIKE 'demo-%' AND id NOT IN ('1','2','3') AND created_at >= ?"
        )
        params: List[Any] = [since]

        if user_role != "ADMIN":
            if organization_id:
                sql += " AND organization_id = ?"
                params.append(organization_id)
            if user_role in ("MERCHANT_PUBLIC", "PUBLIC_USER", "NORMAL_USER") and owner_user_id:
                sql += " AND LOWER(owner_user_id) = LOWER(?)"
                params.append(owner_user_id)

        sql += " GROUP BY d ORDER BY d"

        async with db.execute(sql, tuple(params)) as cursor:
            rows = await cursor.fetchall()

        by_date = {dict(r)["d"]: dict(r) for r in rows if dict(r)["d"]}
        labels, totals, compliants, violations = [], [], [], []
        for i in range(days - 1, -1, -1):
            day = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            r = by_date.get(day, {})
            t = r.get("total") or 0
            c = r.get("compliant") or 0
            labels.append(day[5:])       # MM-DD
            totals.append(t)
            compliants.append(c)
            violations.append(t - c)
        return {"labels": labels, "total": totals, "compliant": compliants, "violations": violations}
    finally:
        await db.close()


# ── Section 5 Evidence Audit & Modification Database Operations ──

async def save_evidence_audit_log(
    analysis_id: str,
    evidence_id: str,
    rule_id: str,
    actor_username: str,
    action_type: str,
    previous_value: Optional[str] = None,
    new_value: Optional[str] = None,
    comments: Optional[str] = None,
    organization_id: Optional[str] = ""
) -> int:
    import datetime
    db = await get_db()
    try:
        now_iso = datetime.datetime.now().isoformat()
        cursor = await db.execute('''
            INSERT INTO evidence_audit_logs (analysis_id, evidence_id, rule_id, actor_username, action_type, previous_value, new_value, comments, organization_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis_id,
            evidence_id,
            rule_id,
            actor_username,
            action_type,
            previous_value,
            new_value,
            comments or "",
            organization_id or "",
            now_iso
        ))
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_evidence_audit_logs(analysis_id: str) -> List[Dict[str, Any]]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM evidence_audit_logs WHERE analysis_id = ? ORDER BY id ASC",
            (analysis_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_analysis_compliance_evidence(analysis_id: str, compliance_result: Dict[str, Any]) -> bool:
    db = await get_db()
    try:
        res_json = json.dumps(compliance_result)
        # Also re-sync score and status
        score = compliance_result.get('score', 0.0)
        status = compliance_result.get('status', 'NON_COMPLIANT')
        await db.execute('''
            UPDATE analyses 
            SET compliance_result = ?, score = ?, status = ?
            WHERE id = ?
        ''', (res_json, score, status, analysis_id))
        await db.commit()
        return True
    finally:
        await db.close()


# ── Section 7 Compliance Scoring & Risk Database Operations ──

def _extract_analysis_risk_info(analysis_row: dict) -> dict:
    """Helper to extract risk level, score, and rule/category scores safely with legacy fallback."""
    cr_raw = analysis_row.get("compliance_result")
    cr = {}
    if isinstance(cr_raw, str):
        try:
            cr = json.loads(cr_raw)
        except Exception:
            cr = {}
    elif isinstance(cr_raw, dict):
        cr = cr_raw

    score = float(analysis_row.get("score") if analysis_row.get("score") is not None else cr.get("score", 0.0))
    risk_assessment = cr.get("risk_assessment") or {}
    risk_level = risk_assessment.get("risk_level") or risk_assessment.get("level")

    failed_count = cr.get("failed_rules", 0) or 0
    passed_count = cr.get("passed_rules", 0) or 0
    review_count = (cr.get("needs_review_rules", 0) or 0) + (cr.get("warning_rules", 0) or 0)
    total_rules = cr.get("total_rules", 14) or 14

    if not risk_level:
        # Legacy fallback
        if failed_count >= 2:
            risk_level = "HIGH"
        elif failed_count == 1:
            risk_level = "CRITICAL"
        elif review_count > 0:
            risk_level = "MEDIUM"
        elif score >= 90.0:
            risk_level = "LOW"
        else:
            risk_level = "MEDIUM"

    category_scores = cr.get("category_scores", [])
    if isinstance(category_scores, dict):
        category_scores = list(category_scores.values())

    return {
        "analysis_id": analysis_row.get("id", ""),
        "product_name": analysis_row.get("product_name", "Unknown Product"),
        "timestamp": analysis_row.get("created_at", ""),
        "score": score,
        "risk_level": risk_level,
        "scoring_version": cr.get("scoring_version", "2026.1"),
        "applicable_rules_count": total_rules,
        "passed_rules": passed_count,
        "failed_rules": failed_count,
        "review_rules": review_count,
        "category_scores": category_scores,
    }


async def get_product_risk_history(
    product_name: str,
    organization_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve compliance score and risk trajectory over time for a given product with tenant scoping."""
    db = await get_db()
    try:
        norm_name = product_name.strip().lower()
        sql = "SELECT * FROM analyses WHERE LOWER(product_name) = ? AND id NOT LIKE 'demo-%' AND id NOT IN ('1','2','3')"
        params: List[Any] = [norm_name]

        if user_role != "ADMIN":
            if organization_id:
                sql += " AND organization_id = ?"
                params.append(organization_id)
            if user_role == "MERCHANT_PUBLIC" and owner_user_id:
                sql += " AND LOWER(owner_user_id) = LOWER(?)"
                params.append(owner_user_id)

        sql += " ORDER BY created_at ASC"

        async with db.execute(sql, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            
        if not rows:
            # Try LIKE matching if exact match yields 0
            sql_like = "SELECT * FROM analyses WHERE LOWER(product_name) LIKE ? AND id NOT LIKE 'demo-%' AND id NOT IN ('1','2','3')"
            params_like: List[Any] = [f"%{norm_name}%"]

            if user_role != "ADMIN":
                if organization_id:
                    sql_like += " AND organization_id = ?"
                    params_like.append(organization_id)
                if user_role == "MERCHANT_PUBLIC" and owner_user_id:
                    sql_like += " AND LOWER(owner_user_id) = LOWER(?)"
                    params_like.append(owner_user_id)

            sql_like += " ORDER BY created_at ASC"
            async with db.execute(sql_like, tuple(params_like)) as cursor:
                rows = await cursor.fetchall()

        entries = [_extract_analysis_risk_info(dict(r)) for r in rows]
        total = len(entries)
        current_risk = entries[-1]["risk_level"] if entries else "LOW"
        current_score = entries[-1]["score"] if entries else 0.0

        risk_trend = "STABLE"
        if len(entries) >= 2:
            prev_score = entries[-2]["score"]
            if current_score > prev_score + 3.0:
                risk_trend = "IMPROVING"
            elif current_score < prev_score - 3.0:
                risk_trend = "DEGRADING"

        return {
            "product_name": product_name,
            "total_analyses": total,
            "current_risk_level": current_risk,
            "current_score": current_score,
            "risk_trend": risk_trend,
            "history_entries": entries,
        }
    finally:
        await db.close()


async def get_batch_risk_distribution(
    organization_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> Dict[str, Any]:
    """Aggregate risk level distribution across screened packages with tenant scoping."""
    if user_role == "ADMIN":
        analyses = await get_analyses(organization_id=organization_id)
        if owner_user_id:
            norm_owner = owner_user_id.lower()
            analyses = [
                a for a in analyses 
                if a.get("owner_user_id") and a.get("owner_user_id", "").lower() == norm_owner
            ]
    elif user_role == "MERCHANT_PUBLIC":
        analyses = await get_analyses(organization_id=organization_id)
        if owner_user_id:
            norm_owner = owner_user_id.lower()
            analyses = [
                a for a in analyses 
                if a.get("owner_user_id") and a.get("owner_user_id", "").lower() == norm_owner
            ]
    elif organization_id:
        analyses = await get_analyses(organization_id=organization_id)
        if owner_user_id:
            norm_owner = owner_user_id.lower()
            analyses = [
                a for a in analyses 
                if a.get("owner_user_id") and a.get("owner_user_id", "").lower() == norm_owner
            ]
    else:
        analyses = await get_analyses()
        if owner_user_id:
            norm_owner = owner_user_id.lower()
            analyses = [
                a for a in analyses 
                if a.get("owner_user_id") and a.get("owner_user_id", "").lower() == norm_owner
            ]

    total = len(analyses)
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    status_counts = {"COMPLIANT": 0, "REVIEW": 0, "FAIL": 0}
    scores: List[float] = []

    for a in analyses:
        info = _extract_analysis_risk_info(a)
        lvl = info["risk_level"].upper()
        if lvl in counts:
            counts[lvl] += 1
        else:
            counts["MEDIUM"] += 1
        
        if info["failed_rules"] > 0:
            status_counts["FAIL"] += 1
        elif info["review_rules"] > 0:
            status_counts["REVIEW"] += 1
        else:
            status_counts["COMPLIANT"] += 1

        scores.append(info["score"])

    avg_score = round(sum(scores) / total, 2) if total > 0 else 0.0
    percentages = {
        lvl: round((c / total) * 100.0, 1) if total > 0 else 0.0
        for lvl, c in counts.items()
    }

    return {
        "total_analyzed": total,
        "critical_count": counts["CRITICAL"],
        "high_count": counts["HIGH"],
        "medium_count": counts["MEDIUM"],
        "low_count": counts["LOW"],
        "failure_count": status_counts["FAIL"],
        "review_required_count": status_counts["REVIEW"],
        "compliant_count": status_counts["COMPLIANT"],
        "average_score": avg_score,
        "average_risk_score": round(100.0 - avg_score, 1) if total > 0 else 0.0,
        "distribution_percentages": percentages,
    }


# ════════════════════════════════════════════════════════════════════════════
# PRE-PRINT PACKAGING ARTWORK OPERATIONS (Section 8)
# ════════════════════════════════════════════════════════════════════════════

async def save_artwork(artwork_data: Dict[str, Any]) -> None:
    """Save or update an artwork document in the database."""
    org_id = (artwork_data.get('organization_id', '') or '').strip()
    owner_id = (artwork_data.get('owner_user_id', '') or '').strip()
    if not org_id and owner_id:
        try:
            user = await get_user_by_username(owner_id)
            if user and user.get('organization_id'):
                org_id = user['organization_id']
            else:
                org_id = f"org_{owner_id.lower()}"
                existing_org = await get_organization(org_id)
                if not existing_org:
                    await create_organization({"id": org_id, "name": f"{owner_id} Org", "status": "ACTIVE"})
        except Exception:
            pass

    db = await get_db()
    try:
        await db.execute('''
            INSERT OR REPLACE INTO artworks (
                id, filename, file_path, file_type, file_size,
                page_count, dimensions, dpi, source_identity,
                compliance_ruleset, parent_artwork_id, iteration_number,
                workflow_status, approval_status, approval_record,
                analysis_result, pages_data, owner_user_id, organization_id, product_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            artwork_data['id'],
            artwork_data['filename'],
            artwork_data['file_path'],
            artwork_data['file_type'],
            artwork_data['file_size'],
            artwork_data.get('page_count', 1),
            json.dumps(artwork_data.get('dimensions', {})),
            artwork_data.get('dpi', 72.0),
            artwork_data.get('source_identity', 'PRE-PRINT ARTWORK'),
            artwork_data.get('compliance_ruleset', 'Legal Metrology (Packaged Commodities) Rules, 2011'),
            artwork_data.get('parent_artwork_id'),
            artwork_data.get('iteration_number', 1),
            artwork_data.get('workflow_status', 'DRAFT'),
            artwork_data.get('approval_status', 'PENDING'),
            json.dumps(artwork_data.get('approval_record')) if artwork_data.get('approval_record') else None,
            json.dumps(artwork_data.get('analysis_result')) if artwork_data.get('analysis_result') else None,
            json.dumps(artwork_data.get('pages_data', [])),
            artwork_data.get('owner_user_id', '') or '',
            org_id,
            artwork_data.get('product_id', '') or '',
            artwork_data.get('created_at') or datetime.now(timezone.utc).isoformat(),
            artwork_data.get('updated_at') or artwork_data.get('created_at') or datetime.now(timezone.utc).isoformat()
        ))
        await db.commit()
    finally:
        await db.close()


async def get_artwork(artwork_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an artwork by its unique ID."""
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM artworks WHERE id = ?', (artwork_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get('dimensions') and isinstance(data['dimensions'], str):
                try:
                    data['dimensions'] = json.loads(data['dimensions'])
                except Exception:
                    data['dimensions'] = {}
            if data.get('approval_record') and isinstance(data['approval_record'], str):
                try:
                    data['approval_record'] = json.loads(data['approval_record'])
                except Exception:
                    pass
            if data.get('analysis_result') and isinstance(data['analysis_result'], str):
                try:
                    data['analysis_result'] = json.loads(data['analysis_result'])
                except Exception:
                    pass
            if data.get('pages_data') and isinstance(data['pages_data'], str):
                try:
                    data['pages_data'] = json.loads(data['pages_data'])
                except Exception:
                    data['pages_data'] = []
            return data
    finally:
        await db.close()


async def list_artworks(owner_user_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all artworks, optionally filtered by owner and/or organization."""
    db = await get_db()
    try:
        conditions = []
        params = []
        if organization_id:
            conditions.append("organization_id = ?")
            params.append(organization_id)
        if owner_user_id:
            conditions.append("LOWER(owner_user_id) = LOWER(?)")
            params.append(owner_user_id)

        if conditions:
            query = f"SELECT * FROM artworks WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
        else:
            query = "SELECT * FROM artworks ORDER BY created_at DESC"

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                data = dict(row)
                if data.get('dimensions') and isinstance(data['dimensions'], str):
                    try:
                        data['dimensions'] = json.loads(data['dimensions'])
                    except Exception:
                        data['dimensions'] = {}
                if data.get('approval_record') and isinstance(data['approval_record'], str):
                    try:
                        data['approval_record'] = json.loads(data['approval_record'])
                    except Exception:
                        pass
                if data.get('analysis_result') and isinstance(data['analysis_result'], str):
                    try:
                        data['analysis_result'] = json.loads(data['analysis_result'])
                    except Exception:
                        pass
                if data.get('pages_data') and isinstance(data['pages_data'], str):
                    try:
                        data['pages_data'] = json.loads(data['pages_data'])
                    except Exception:
                        data['pages_data'] = []
                results.append(data)
            return results
    finally:
        await db.close()


async def update_artwork_analysis(
    artwork_id: str,
    analysis_result: Dict[str, Any],
    workflow_status: str,
    updated_at: str
) -> bool:
    """Update analysis result and workflow status for an artwork."""
    db = await get_db()
    try:
        await db.execute('''
            UPDATE artworks 
            SET analysis_result = ?, workflow_status = ?, updated_at = ?
            WHERE id = ?
        ''', (json.dumps(analysis_result), workflow_status, updated_at, artwork_id))
        await db.commit()
        return True
    finally:
        await db.close()


async def update_artwork_approval(
    artwork_id: str,
    approval_status: str,
    approval_record: Dict[str, Any],
    workflow_status: str,
    updated_at: str
) -> bool:
    """Update approval status and review record for an artwork."""
    db = await get_db()
    try:
        await db.execute('''
            UPDATE artworks 
            SET approval_status = ?, approval_record = ?, workflow_status = ?, updated_at = ?
            WHERE id = ?
        ''', (approval_status, json.dumps(approval_record), workflow_status, updated_at, artwork_id))
        await db.commit()
        return True
    finally:
        await db.close()


async def delete_artwork(artwork_id: str) -> bool:
    """Delete an artwork record by ID."""
    db = await get_db()
    try:
        await db.execute('DELETE FROM artworks WHERE id = ?', (artwork_id,))
        await db.commit()
        return True
    finally:
        await db.close()


# ════════════════════════════════════════════════════════════════════════════
# VERSION COMPARISON & TIMELINE OPERATIONS (Section 9)
# ════════════════════════════════════════════════════════════════════════════

async def save_version_comparison(comp_data: Dict[str, Any]) -> None:
    comp_id = comp_data.get('comparison_id') or comp_data.get('id') or str(uuid.uuid4())
    v_a = comp_data.get('version_a', {}) if isinstance(comp_data.get('version_a'), dict) else {}
    v_b = comp_data.get('version_b', {}) if isinstance(comp_data.get('version_b'), dict) else {}
    
    v_a_id = v_a.get('version_id') or comp_data.get('version_a_id', '')
    v_b_id = v_b.get('version_id') or comp_data.get('version_b_id', '')
    v_type_a = v_a.get('version_type') or comp_data.get('version_type_a', 'ANALYSIS')
    v_type_b = v_b.get('version_type') or comp_data.get('version_type_b', 'ANALYSIS')
    prod_name = v_b.get('product_name') or comp_data.get('product_name') or comp_data.get('entity_id', '')
    created_at = comp_data.get('created_at') or datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        await db.execute('''
            INSERT OR REPLACE INTO version_comparisons (
                id, version_a_id, version_b_id, version_type_a, version_type_b,
                product_name, score_a, score_b, score_delta, risk_shift,
                comparison_result, owner_user_id, organization_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            comp_id,
            v_a_id,
            v_b_id,
            v_type_a,
            v_type_b,
            prod_name,
            float(comp_data.get('score_a', 0.0)),
            float(comp_data.get('score_b', 0.0)),
            float(comp_data.get('score_delta') or comp_data.get('delta_score', 0.0)),
            comp_data.get('risk_shift', 'UNCHANGED'),
            json.dumps(comp_data),
            comp_data.get('owner_user_id', '') or '',
            comp_data.get('organization_id', '') or '',
            created_at
        ))
        await db.commit()
    finally:
        await db.close()


async def get_version_comparison(comp_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a version comparison by ID."""
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM version_comparisons WHERE id = ?', (comp_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get('comparison_result') and isinstance(data['comparison_result'], str):
                try:
                    return json.loads(data['comparison_result'])
                except Exception:
                    pass
            return data
    finally:
        await db.close()


async def list_version_comparisons(owner_user_id: Optional[str] = None, organization_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List recent version comparisons."""
    db = await get_db()
    try:
        conditions = []
        params = []
        if organization_id:
            conditions.append("organization_id = ?")
            params.append(organization_id)
        if owner_user_id:
            conditions.append("LOWER(owner_user_id) = LOWER(?)")
            params.append(owner_user_id)

        if conditions:
            query = f"SELECT * FROM version_comparisons WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT ?"
        else:
            query = "SELECT * FROM version_comparisons ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                data = dict(row)
                if data.get('comparison_result') and isinstance(data['comparison_result'], str):
                    try:
                        results.append(json.loads(data['comparison_result']))
                    except Exception:
                        results.append(data)
                else:
                    results.append(data)
            return results
    finally:
        await db.close()


async def delete_version_comparison(comp_id: str) -> bool:
    """Delete a version comparison record by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM version_comparisons WHERE id = ?", (comp_id.strip(),))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_version_timeline(
    entity_id: str,
    organization_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Builds a chronological timeline of version events for a product name or artwork chain,
    scoped strictly to the authorized tenant and user ownership.
    """
    db = await get_db()
    timeline_events: List[Dict[str, Any]] = []
    try:
        norm_id = entity_id.strip()

        # 1. Search in analyses table (Physical package screenings)
        ana_query = "SELECT * FROM analyses WHERE (LOWER(product_name) = LOWER(?) OR id = ?)"
        ana_params: List[Any] = [norm_id, norm_id]
        if user_role != "ADMIN" and organization_id:
            ana_query += " AND (organization_id = ? OR organization_id = '' OR organization_id IS NULL)"
            ana_params.append(organization_id)
        if user_role == "MERCHANT_PUBLIC" and owner_user_id:
            ana_query += " AND LOWER(owner_user_id) = LOWER(?)"
            ana_params.append(owner_user_id)
        ana_query += " ORDER BY created_at ASC"

        async with db.execute(ana_query, tuple(ana_params)) as cursor:
            analysis_rows = await cursor.fetchall()
            for r in analysis_rows:
                a_dict = dict(r)
                info = _extract_analysis_risk_info(a_dict)
                timeline_events.append({
                    "event_id": f"evt-scan-{a_dict['id']}",
                    "event_type": "ANALYSIS_RUN",
                    "title": f"Package Screening: {a_dict.get('product_name', 'Unknown')}",
                    "description": f"Compliance score: {info['score']}/100 with risk level {info['risk_level']}.",
                    "timestamp": a_dict.get("created_at", ""),
                    "version_id": a_dict["id"],
                    "actor_username": a_dict.get("owner_user_id", ""),
                    "organization_id": a_dict.get("organization_id", ""),
                    "score": info["score"],
                    "risk_level": info["risk_level"],
                    "metadata": {"type": "PHYSICAL_PACKAGE_SCREENING"}
                })

        # 2. Search in artworks table (Pre-print artwork revisions)
        art_query = "SELECT * FROM artworks WHERE (id = ? OR parent_artwork_id = ? OR LOWER(filename) LIKE LOWER(?))"
        art_params: List[Any] = [norm_id, norm_id, f"%{norm_id}%"]
        if user_role != "ADMIN" and organization_id:
            art_query += " AND (organization_id = ? OR organization_id = '' OR organization_id IS NULL)"
            art_params.append(organization_id)
        if user_role == "MERCHANT_PUBLIC" and owner_user_id:
            art_query += " AND LOWER(owner_user_id) = LOWER(?)"
            art_params.append(owner_user_id)
        art_query += " ORDER BY created_at ASC"

        async with db.execute(art_query, tuple(art_params)) as cursor:
            artwork_rows = await cursor.fetchall()
            for r in artwork_rows:
                art_dict = dict(r)
                ana_res = {}
                if art_dict.get("analysis_result") and isinstance(art_dict["analysis_result"], str):
                    try:
                        ana_res = json.loads(art_dict["analysis_result"])
                    except Exception:
                        pass
                
                score = ana_res.get("overall_score", 0.0)
                status = art_dict.get("workflow_status", "DRAFT")

                timeline_events.append({
                    "event_id": f"evt-art-{art_dict['id']}",
                    "event_type": "ARTWORK_UPLOADED" if art_dict.get("iteration_number", 1) == 1 else "CORRECTION_SUBMITTED",
                    "title": f"Artwork Revision v{art_dict.get('iteration_number', 1)}: {art_dict.get('filename', '')}",
                    "description": f"Pre-print packaging verification. Workflow status: {status}.",
                    "timestamp": art_dict.get("created_at", ""),
                    "version_id": art_dict["id"],
                    "actor_username": art_dict.get("owner_user_id", ""),
                    "organization_id": art_dict.get("organization_id", ""),
                    "score": score,
                    "risk_level": "LOW" if score >= 90 else "MEDIUM",
                    "metadata": {
                        "iteration_number": art_dict.get("iteration_number", 1),
                        "parent_artwork_id": art_dict.get("parent_artwork_id"),
                        "workflow_status": status
                    }
                })

        # 3. Search in version_comparisons table
        comp_query = "SELECT * FROM version_comparisons WHERE (LOWER(product_name) LIKE LOWER(?) OR version_a_id = ? OR version_b_id = ? OR id = ?)"
        comp_params: List[Any] = [f"%{norm_id}%", norm_id, norm_id, norm_id]
        if user_role != "ADMIN" and organization_id:
            comp_query += " AND (organization_id = ? OR organization_id = '' OR organization_id IS NULL)"
            comp_params.append(organization_id)
        if user_role == "MERCHANT_PUBLIC" and owner_user_id:
            comp_query += " AND LOWER(owner_user_id) = LOWER(?)"
            comp_params.append(owner_user_id)
        comp_query += " ORDER BY created_at ASC"

        async with db.execute(comp_query, tuple(comp_params)) as cursor:
            comp_rows = await cursor.fetchall()
            for r in comp_rows:
                c_dict = dict(r)
                timeline_events.append({
                    "event_id": f"evt-cmp-{c_dict['id']}",
                    "event_type": "COMPARISON",
                    "title": f"Version Comparison: {c_dict.get('version_a_id', '')} vs {c_dict.get('version_b_id', '')}",
                    "description": f"Score delta: {c_dict.get('score_delta', 0.0):+0.1f} ({c_dict.get('risk_shift', 'UNCHANGED')}).",
                    "timestamp": c_dict.get("created_at", ""),
                    "version_id": c_dict.get("version_b_id", "") or c_dict["id"],
                    "actor_username": c_dict.get("owner_user_id", ""),
                    "organization_id": c_dict.get("organization_id", ""),
                    "score": c_dict.get("score_b"),
                    "risk_level": "LOW" if (c_dict.get("score_b") or 0) >= 90 else "MEDIUM",
                    "metadata": {
                        "comparison_id": c_dict["id"],
                        "version_a_id": c_dict.get("version_a_id"),
                        "version_b_id": c_dict.get("version_b_id"),
                        "risk_shift": c_dict.get("risk_shift")
                    }
                })

        # Sort combined events chronologically
        timeline_events.sort(key=lambda x: x.get("timestamp", ""))
        return timeline_events
    finally:
        await db.close()


# ════════════════════════════════════════════════════════════════════════════
# 8. SECTION 10: OFFICER REVIEWS CRUD
# ════════════════════════════════════════════════════════════════════════════

async def save_review(review_dict: Dict[str, Any]) -> None:
    """Insert or update an officer review record."""
    db = await get_db()
    try:
        rev_id = review_dict["id"]
        ana_id = review_dict["analysis_id"]
        target_type = review_dict.get("target_type", "ANALYSIS")
        prod_name = review_dict.get("product_name", "")
        status = review_dict.get("status", "PENDING_REVIEW")
        assigned_officer = review_dict.get("assigned_officer", "") or ""
        assigned_by = review_dict.get("assigned_by", "") or ""
        assigned_at = review_dict.get("assigned_at")
        verified_by = review_dict.get("verified_by", "") or ""
        verified_at = review_dict.get("verified_at")
        final_human_status = review_dict.get("final_human_status", "") or ""
        ai_score = float(review_dict.get("ai_score", 0.0))
        ai_risk_level = review_dict.get("ai_risk_level", "LOW")
        ai_status = review_dict.get("ai_status", "PASS")
        
        ai_snap = review_dict.get("ai_snapshot", {})
        if not isinstance(ai_snap, str):
            ai_snap = json.dumps(ai_snap)
        human_res = review_dict.get("human_verified_result", {})
        if (not human_res or human_res == {}) and "human_score" in review_dict:
            human_res = {"score": review_dict["human_score"], "status": review_dict.get("final_human_status", "")}
        if not isinstance(human_res, str):
            human_res = json.dumps(human_res)
        field_corr = review_dict.get("field_corrections", [])
        if not isinstance(field_corr, str):
            field_corr = json.dumps(field_corr)
        ev_mods = review_dict.get("evidence_modifications", [])
        if not isinstance(ev_mods, str):
            ev_mods = json.dumps(ev_mods)
        comments = review_dict.get("comments", [])
        if not isinstance(comments, str):
            comments = json.dumps(comments)
        history = review_dict.get("history", [])
        if not isinstance(history, str):
            history = json.dumps(history)
        
        created_at = review_dict.get("created_at") or datetime.now(timezone.utc).isoformat()
        updated_at = review_dict.get("updated_at") or datetime.now(timezone.utc).isoformat()

        await db.execute('''
            INSERT OR REPLACE INTO officer_reviews (
                id, analysis_id, target_type, product_name, status,
                assigned_officer, assigned_by, assigned_at,
                verified_by, verified_at, final_human_status,
                ai_score, ai_risk_level, ai_status,
                ai_snapshot, human_verified_result, field_corrections,
                evidence_modifications, comments, history,
                organization_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rev_id, ana_id, target_type, prod_name, status,
            assigned_officer, assigned_by, assigned_at,
            verified_by, verified_at, final_human_status,
            ai_score, ai_risk_level, ai_status,
            ai_snap, human_res, field_corr,
            ev_mods, comments, history,
            review_dict.get("organization_id", "") or "",
            created_at, updated_at
        ))
        await db.commit()
    finally:
        await db.close()


async def get_review(review_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an officer review by ID."""
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM officer_reviews WHERE id = ?', (review_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)
    finally:
        await db.close()


async def get_review_by_analysis_id(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an officer review by analysis ID."""
    db = await get_db()
    try:
        async with db.execute('SELECT * FROM officer_reviews WHERE analysis_id = ?', (analysis_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)
    finally:
        await db.close()


async def list_reviews(
    status: Optional[str] = None,
    assigned_officer: Optional[str] = None,
    risk_level: Optional[str] = None,
    organization_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List officer reviews with optional filtering."""
    db = await get_db()
    try:
        query = 'SELECT * FROM officer_reviews WHERE 1=1'
        params: List[Any] = []

        if organization_id:
            query += ' AND organization_id = ?'
            params.append(organization_id)

        if status:
            if status == "PENDING":
                query += ' AND status = "PENDING_REVIEW"'
            elif status == "VERIFIED":
                query += ' AND status LIKE "VERIFIED%"'
            else:
                query += ' AND status = ?'
                params.append(status)

        if assigned_officer:
            query += ' AND LOWER(assigned_officer) = LOWER(?)'
            params.append(assigned_officer)

        if risk_level:
            query += ' AND UPPER(ai_risk_level) = UPPER(?)'
            params.append(risk_level)

        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def delete_review(review_id: str) -> bool:
    """Delete a review record (for test cleanup)."""
    db = await get_db()
    try:
        cursor = await db.execute('DELETE FROM officer_reviews WHERE id = ?', (review_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# Alias for backward compatibility with external callers and M4 contract test suites
list_officer_reviews = list_reviews


# ── Section 13: Persistent Verification Cache CRUD ──

async def save_cached_verification(
    identifier_type: str,
    identifier_value: str,
    record_data: Dict[str, Any],
    source: str,
    ttl_seconds: int = 86400 * 30
):
    """
    Saves or updates a verification record in the persistent SQLite cache.
    """
    from datetime import datetime, timezone, timedelta
    now_dt = datetime.now(timezone.utc)
    cached_at = now_dt.isoformat()
    expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
    
    clean_type = identifier_type.strip().upper()
    clean_val = identifier_value.strip()

    db = await get_db()
    try:
        await db.execute('''
            INSERT OR REPLACE INTO verification_cache (
                identifier_type, identifier_value, record_json, source, cached_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            clean_type,
            clean_val,
            json.dumps(record_data),
            source,
            cached_at,
            expires_at
        ))
        await db.commit()
    finally:
        await db.close()


async def get_cached_verification(identifier_type: str, identifier_value: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a cached verification record if present and not expired.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    clean_type = identifier_type.strip().upper()
    clean_val = identifier_value.strip()

    db = await get_db()
    try:
        async with db.execute('''
            SELECT record_json, source, cached_at, expires_at
            FROM verification_cache
            WHERE identifier_type = ? AND identifier_value = ? AND expires_at > ?
        ''', (clean_type, clean_val, now_iso)) as cursor:
            row = await cursor.fetchone()
            if row:
                rec = json.loads(row['record_json'])
                rec['_cached_at'] = row['cached_at']
                rec['_cache_source'] = row['source']
                return rec
            return None
    finally:
        await db.close()


async def delete_cached_verification(identifier_type: str, identifier_value: str) -> bool:
    """
    Deletes a specific cached verification entry.
    """
    clean_type = identifier_type.strip().upper()
    clean_val = identifier_value.strip()

    db = await get_db()
    try:
        cursor = await db.execute('''
            DELETE FROM verification_cache
            WHERE identifier_type = ? AND identifier_value = ?
        ''', (clean_type, clean_val))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def clear_expired_verification_cache() -> int:
    """
    Purges all expired records from the verification cache.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        cursor = await db.execute('''
            DELETE FROM verification_cache
            WHERE expires_at <= ?
        ''', (now_iso,))
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


async def list_cached_verifications(identifier_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Lists cached verification entries.
    """
    db = await get_db()
    try:
        query = 'SELECT identifier_type, identifier_value, source, cached_at, expires_at FROM verification_cache'
        params: List[Any] = []
        if identifier_type:
            query += ' WHERE identifier_type = ?'
            params.append(identifier_type.strip().upper())
        query += ' ORDER BY cached_at DESC LIMIT ?'
        params.append(limit)

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_verification_cache_stats() -> Dict[str, Any]:
    """
    Returns high-level statistics about the persistent verification cache.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        total = 0
        active = 0
        fssai_count = 0
        gs1_count = 0

        async with db.execute('SELECT COUNT(*) as count FROM verification_cache') as cur:
            row = await cur.fetchone()
            total = row['count'] if row else 0

        async with db.execute('SELECT COUNT(*) as count FROM verification_cache WHERE expires_at > ?', (now_iso,)) as cur:
            row = await cur.fetchone()
            active = row['count'] if row else 0

        async with db.execute('SELECT COUNT(*) as count FROM verification_cache WHERE identifier_type = "FSSAI" AND expires_at > ?', (now_iso,)) as cur:
            row = await cur.fetchone()
            fssai_count = row['count'] if row else 0

        async with db.execute('SELECT COUNT(*) as count FROM verification_cache WHERE identifier_type = "GS1_GTIN" AND expires_at > ?', (now_iso,)) as cur:
            row = await cur.fetchone()
            gs1_count = row['count'] if row else 0

        return {
            "total_cached_records": total,
            "active_cached_records": active,
            "expired_cached_records": max(0, total - active),
            "fssai_cached_count": fssai_count,
            "gs1_cached_count": gs1_count,
            "cache_engine": "SQLite persistent WAL WAL-mode cache"
        }
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# SECTION 15: SECURITY AUDIT LOGGING & CRYPTOGRAPHIC HASH CHAIN
# ═══════════════════════════════════════════════════════════════════════

GENESIS_AUDIT_HASH = "GENESIS_ROOT_METRCHECK_SEC_V1"


async def log_security_event(
    event_type: str,
    actor_username: str = "",
    ip_address: str = "",
    resource_id: str = "",
    details: str = "",
) -> Dict[str, Any]:
    """
    Append an immutable security audit event with cryptographic SHA-256 forward-chaining.
    Every event binds to the previous event's hash, preventing retroactive log tampering.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        # Fetch the most recent event's hash to form the blockchain-like hash link
        prev_hash = GENESIS_AUDIT_HASH
        async with db.execute('SELECT event_hash FROM security_audit_logs ORDER BY id DESC LIMIT 1') as cur:
            row = await cur.fetchone()
            if row and row['event_hash']:
                prev_hash = row['event_hash']

        # Deterministically compute cryptographic SHA-256 block hash
        raw_payload = f"{prev_hash}|{now_iso}|{event_type}|{actor_username or ''}|{ip_address or ''}|{resource_id or ''}|{details or ''}"
        event_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()

        cur = await db.execute('''
            INSERT INTO security_audit_logs (
                event_type, actor_username, ip_address, resource_id, details, prev_hash, event_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event_type,
            actor_username or '',
            ip_address or '',
            resource_id or '',
            details or '',
            prev_hash,
            event_hash,
            now_iso
        ))
        await db.commit()
        last_id = cur.lastrowid

        return {
            "id": last_id,
            "event_type": event_type,
            "actor_username": actor_username,
            "ip_address": ip_address,
            "resource_id": resource_id,
            "details": details,
            "prev_hash": prev_hash,
            "event_hash": event_hash,
            "created_at": now_iso
        }
    finally:
        await db.close()


async def get_security_audit_logs(limit: int = 100, event_type: str = "") -> List[Dict[str, Any]]:
    """Retrieve security audit logs, ordered chronologically descending."""
    db = await get_db()
    try:
        if event_type:
            async with db.execute(
                "SELECT * FROM security_audit_logs WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                (event_type, limit)
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
        else:
            async with db.execute(
                "SELECT * FROM security_audit_logs ORDER BY id DESC LIMIT ?",
                (limit,)
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
    finally:
        await db.close()


async def verify_security_audit_chain() -> Dict[str, Any]:
    """
    Verify the cryptographic integrity of the security audit log hash chain.
    Iterates sequentially through all entries from ID 1 up to the latest,
    verifying each block's SHA-256 hash and the previous hash linkage.
    """
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM security_audit_logs ORDER BY id ASC") as cur:
            rows = await cur.fetchall()
            records = [dict(r) for r in rows]

        if not records:
            return {
                "valid": True,
                "total_records": 0,
                "genesis_hash": GENESIS_AUDIT_HASH,
                "message": "Security audit log is empty. Chain is valid."
            }

        expected_prev_hash = GENESIS_AUDIT_HASH
        for idx, rec in enumerate(records):
            # Check 1: Previous hash link matches
            if rec["prev_hash"] != expected_prev_hash:
                return {
                    "valid": False,
                    "total_records": len(records),
                    "broken_at_id": rec["id"],
                    "broken_at_index": idx,
                    "error": f"Broken chain link at log #{rec['id']}: expected prev_hash '{expected_prev_hash}', got '{rec['prev_hash']}'"
                }

            # Check 2: Block hash matches computed hash
            raw_payload = f"{rec['prev_hash']}|{rec['created_at']}|{rec['event_type']}|{rec['actor_username'] or ''}|{rec['ip_address'] or ''}|{rec['resource_id'] or ''}|{rec['details'] or ''}"
            computed_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()
            if rec["event_hash"] != computed_hash:
                return {
                    "valid": False,
                    "total_records": len(records),
                    "broken_at_id": rec["id"],
                    "broken_at_index": idx,
                    "error": f"Tampered block payload at log #{rec['id']}: stored hash '{rec['event_hash']}' != computed hash '{computed_hash}'"
                }

            expected_prev_hash = rec["event_hash"]

        return {
            "valid": True,
            "total_records": len(records),
            "head_hash": expected_prev_hash,
            "genesis_hash": GENESIS_AUDIT_HASH,
            "message": f"Cryptographic audit chain verified successfully across {len(records)} events."
        }
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# DOWNLOAD TICKETS (SEC-AUD-11: Short-Lived Single-Use Tickets)
# ═══════════════════════════════════════════════════════════════════════

async def save_download_ticket(
    ticket_id: str,
    user_id: str,
    username: str,
    role: str,
    organization_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    expires_at: float,
) -> Dict[str, Any]:
    """Persists a new short-lived single-use download ticket in SQLite."""
    import time
    from datetime import datetime, timezone
    db = await get_db()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            INSERT INTO download_tickets (id, user_id, username, role, organization_id, resource_type, resource_id, action, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, str(user_id or ""), username, role, organization_id, resource_type, resource_id, action, expires_at, now_iso)
        )
        await db.commit()
        return {
            "id": ticket_id,
            "username": username,
            "role": role,
            "organization_id": organization_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "expires_at": expires_at,
        }
    finally:
        await db.close()


async def redeem_download_ticket_in_db(
    ticket_id: str,
    resource_type: str,
    resource_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Atomically validates and marks a single-use download ticket as redeemed.
    Returns ticket record dict if valid, or None if expired, already redeemed, or mismatched.
    """
    import time
    db = await get_db()
    try:
        now = time.time()
        cursor = await db.execute(
            """
            SELECT id, user_id, username, role, organization_id, resource_type, resource_id, action, expires_at, redeemed_at
            FROM download_tickets
            WHERE id = ?
            """,
            (ticket_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        row_dict = dict(row)

        # 1. Check already redeemed (single-use)
        if row_dict.get("redeemed_at") is not None:
            return None

        # 2. Check expiration
        if row_dict.get("expires_at", 0) < now:
            return None

        # 3. Check resource_type match
        if row_dict.get("resource_type") != resource_type:
            return None

        # 4. Check resource_id match
        if row_dict.get("resource_id") != resource_id:
            return None

        # 5. Atomically mark redeemed
        await db.execute(
            "UPDATE download_tickets SET redeemed_at = ? WHERE id = ? AND redeemed_at IS NULL",
            (now, ticket_id)
        )
        await db.commit()

        return row_dict
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# MERCHANT PRODUCT CATALOG (Section 1 & 8 Master SKU Records)
# ═══════════════════════════════════════════════════════════════════════

async def create_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new persistent product record scoped to a merchant tenant."""
    now_iso = datetime.now(timezone.utc).isoformat()
    pid = str(product_data.get("id") or uuid.uuid4())
    org_id = str(product_data.get("organization_id") or "").strip()
    owner_id = str(product_data.get("owner_user_id") or "").strip()
    p_name = str(product_data.get("product_name") or "").strip()

    row = {
        "id": pid,
        "organization_id": org_id,
        "owner_user_id": owner_id,
        "product_name": p_name,
        "brand_name": str(product_data.get("brand_name") or "").strip(),
        "category": str(product_data.get("category") or "GENERAL").strip(),
        "gtin_barcode": str(product_data.get("gtin_barcode") or "").strip(),
        "fssai_license": str(product_data.get("fssai_license") or "").strip(),
        "legal_metrology_license": str(product_data.get("legal_metrology_license") or "").strip(),
        "net_quantity_declared": str(product_data.get("net_quantity_declared") or "").strip(),
        "mrp_declared": float(product_data.get("mrp_declared") or 0.0),
        "unit_sale_price_declared": str(product_data.get("unit_sale_price_declared") or "").strip(),
        "manufacturer_name": str(product_data.get("manufacturer_name") or "").strip(),
        "country_of_origin": str(product_data.get("country_of_origin") or "India").strip(),
        "status": str(product_data.get("status") or "ACTIVE").strip(),
        "created_at": product_data.get("created_at") or now_iso,
        "updated_at": now_iso,
    }

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO products (
                id, organization_id, owner_user_id, product_name, brand_name,
                category, gtin_barcode, fssai_license, legal_metrology_license,
                net_quantity_declared, mrp_declared, unit_sale_price_declared,
                manufacturer_name, country_of_origin, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], row["organization_id"], row["owner_user_id"], row["product_name"],
                row["brand_name"], row["category"], row["gtin_barcode"], row["fssai_license"],
                row["legal_metrology_license"], row["net_quantity_declared"], row["mrp_declared"],
                row["unit_sale_price_declared"], row["manufacturer_name"], row["country_of_origin"],
                row["status"], row["created_at"], row["updated_at"]
            )
        )
        await db.commit()
        return row
    finally:
        await db.close()


async def get_product(product_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single product by ID."""
    if not product_id:
        return None
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_products(
    organization_id: str,
    owner_user_id: Optional[str] = None,
    status: Optional[str] = "ACTIVE",
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List products strictly filtered by organization tenant and optional owner/status/search."""
    if not organization_id:
        return []
    db = await get_db()
    try:
        clauses = ["organization_id = ?"]
        params: List[Any] = [organization_id]

        if owner_user_id:
            clauses.append("LOWER(owner_user_id) = LOWER(?)")
            params.append(owner_user_id)

        if status and status != "ALL":
            clauses.append("status = ?")
            params.append(status)

        if category and category != "ALL":
            clauses.append("category = ?")
            params.append(category)

        if search and search.strip():
            q = f"%{search.strip()}%"
            clauses.append("(product_name LIKE ? OR brand_name LIKE ? OR gtin_barcode LIKE ? OR manufacturer_name LIKE ?)")
            params.extend([q, q, q, q])

        where_str = " AND ".join(clauses)
        params.extend([limit, offset])

        query = f"""
            SELECT * FROM products
            WHERE {where_str}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_product(product_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update editable product fields."""
    if not product_id or not update_data:
        return await get_product(product_id)

    db = await get_db()
    try:
        allowed_fields = [
            "product_name", "brand_name", "category", "gtin_barcode", "fssai_license",
            "legal_metrology_license", "net_quantity_declared", "mrp_declared",
            "unit_sale_price_declared", "manufacturer_name", "country_of_origin", "status"
        ]
        sets = []
        params = []
        for f in allowed_fields:
            if f in update_data:
                sets.append(f"{f} = ?")
                if f == "mrp_declared":
                    params.append(float(update_data[f] or 0.0))
                else:
                    params.append(str(update_data[f] or "").strip())

        if not sets:
            return await get_product(product_id)

        now_iso = datetime.now(timezone.utc).isoformat()
        sets.append("updated_at = ?")
        params.append(now_iso)
        params.append(product_id)

        sql = f"UPDATE products SET {', '.join(sets)} WHERE id = ?"
        await db.execute(sql, params)
        await db.commit()

        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def archive_product(product_id: str) -> bool:
    """Soft delete a product by setting status = 'ARCHIVED'. Preserves all historical analyses/artworks."""
    if not product_id:
        return False
    db = await get_db()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = await db.execute(
            "UPDATE products SET status = 'ARCHIVED', updated_at = ? WHERE id = ?",
            (now_iso, product_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def hard_delete_product(product_id: str) -> bool:
    """Hard delete a product record."""
    if not product_id:
        return False
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_product(product_id: str) -> bool:
    """Convenience alias for archive_product to guarantee non-destructive lifecycle."""
    return await archive_product(product_id)


async def get_product_analyses(product_id: str, organization_id: str) -> List[Dict[str, Any]]:
    """Fetch physical scans associated with a product within the merchant tenant."""
    if not product_id or not organization_id:
        return []
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT id, product_name, image_filename, score, status, created_at,
                   owner_user_id, organization_id, product_id, integrity_hash
            FROM analyses
            WHERE product_id = ? AND organization_id = ?
            ORDER BY created_at DESC
            """,
            (product_id, organization_id)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_product_artworks(product_id: str, organization_id: str) -> List[Dict[str, Any]]:
    """Fetch packaging artworks associated with a product within the merchant tenant."""
    if not product_id or not organization_id:
        return []
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT id, filename, file_type, file_size, page_count, iteration_number,
                   workflow_status, approval_status, created_at, updated_at,
                   owner_user_id, organization_id, product_id, analysis_result
            FROM artworks
            WHERE product_id = ? AND organization_id = ?
            ORDER BY iteration_number DESC, updated_at DESC
            """,
            (product_id, organization_id)
        )
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("analysis_result") and isinstance(d["analysis_result"], str):
                try:
                    d["analysis_result"] = json.loads(d["analysis_result"])
                except Exception:
                    pass
            results.append(d)
        return results
    finally:
        await db.close()


async def get_product_summary(product_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
    """Compute rich compliance summary for a single product record."""
    product = await get_product(product_id)
    if not product or product.get("organization_id") != organization_id:
        return None

    analyses = await get_product_analyses(product_id, organization_id)
    artworks = await get_product_artworks(product_id, organization_id)

    latest_scan = analyses[0] if analyses else None
    latest_artwork = artworks[0] if artworks else None

    total_scans = len(analyses)
    total_artworks = len(artworks)

    # Calculate latest score and status
    latest_score = float(latest_scan["score"]) if latest_scan and latest_scan.get("score") is not None else 0.0
    latest_status = latest_scan["status"] if latest_scan and latest_scan.get("status") else "NOT_SCREENED"

    # Count findings across scans
    critical_findings_count = sum(1 for a in analyses if a.get("status") in ("NON_COMPLIANT", "FAIL"))
    review_findings_count = sum(1 for a in analyses if a.get("status") in ("REVIEW_REQUIRED", "WARNING"))

    return {
        "product": product,
        "total_scans": total_scans,
        "total_artworks": total_artworks,
        "latest_score": latest_score,
        "latest_status": latest_status,
        "critical_findings_count": critical_findings_count,
        "review_findings_count": review_findings_count,
        "latest_scan": latest_scan,
        "latest_artwork": latest_artwork,
    }


async def get_merchant_dashboard_metrics(organization_id: str, owner_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate genuine live metrics for the Merchant Pre-Flight Dashboard."""
    if not organization_id:
        return {
            "active_products": 0,
            "products_checked": 0,
            "attention_required": 0,
            "critical_findings": 0,
            "packaging_artworks": 0,
        }

    db = await get_db()
    try:
        # 1. Count active products
        p_cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM products WHERE organization_id = ? AND status = 'ACTIVE'",
            (organization_id,)
        )
        p_row = await p_cursor.fetchone()
        active_products = p_row["cnt"] if p_row else 0

        # 2. Count analyses (products checked)
        a_cursor = await db.execute(
            "SELECT COUNT(*) AS cnt, "
            "SUM(CASE WHEN status IN ('NON_COMPLIANT', 'FAIL') THEN 1 ELSE 0 END) AS crit_cnt, "
            "SUM(CASE WHEN status IN ('REVIEW_REQUIRED', 'WARNING') THEN 1 ELSE 0 END) AS rev_cnt "
            "FROM analyses WHERE organization_id = ?",
            (organization_id,)
        )
        a_row = await a_cursor.fetchone()
        products_checked = a_row["cnt"] if a_row else 0
        critical_findings = a_row["crit_cnt"] if a_row and a_row["crit_cnt"] is not None else 0
        attention_required = a_row["rev_cnt"] if a_row and a_row["rev_cnt"] is not None else 0

        # 3. Count artworks
        art_cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM artworks WHERE organization_id = ?",
            (organization_id,)
        )
        art_row = await art_cursor.fetchone()
        packaging_artworks = art_row["cnt"] if art_row else 0

        return {
            "active_products": active_products,
            "products_checked": products_checked,
            "attention_required": attention_required,
            "critical_findings": critical_findings,
            "packaging_artworks": packaging_artworks,
        }
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
# PHASE 4B: ENFORCEMENT CASE MANAGEMENT & NOTICE LEDGER REPOSITORY
# ═══════════════════════════════════════════════════════════════════════

def generate_case_reference() -> str:
    """Generates unique, stable, non-sequential case reference like MC-ENF-2026-A8B9C1D2."""
    now_year = datetime.now(timezone.utc).year
    suffix = uuid.uuid4().hex[:8].upper()
    return f"MC-ENF-{now_year}-{suffix}"


def generate_notice_reference(notice_type: str = "SHOW_CAUSE") -> str:
    """Generates unique statutory notice reference like MC-SCN-2026-X7Y8Z9W0 or MC-CMP-2026-X7Y8Z9W0."""
    now_year = datetime.now(timezone.utc).year
    suffix = uuid.uuid4().hex[:8].upper()
    nt = (notice_type or "SHOW_CAUSE").upper()
    if "SHOW_CAUSE" in nt or "SCN" in nt:
        prefix = "SCN"
    elif "COMPOUND" in nt or "CMP" in nt:
        prefix = "CMP"
    elif "SEIZURE" in nt or "SZR" in nt:
        prefix = "SZR"
    elif "PROSECUTION" in nt or "PRS" in nt:
        prefix = "PRS"
    else:
        prefix = "NOT"
    return f"MC-{prefix}-{now_year}-{suffix}"


async def save_enforcement_case(case_dict: Dict[str, Any]) -> None:
    """Insert or update an enforcement case record."""
    db = await get_db()
    try:
        c_id = case_dict["id"]
        c_ref = case_dict.get("case_reference") or generate_case_reference()
        ana_id = case_dict["analysis_id"]
        rev_id = case_dict.get("review_id", "") or ""
        prod_id = case_dict.get("product_id", "") or ""
        org_id = case_dict.get("organization_id", "org_ministry")
        m_org_id = case_dict.get("merchant_organization_id", "") or ""
        prod_name = case_dict.get("product_name", "") or ""
        status = case_dict.get("status", "OPEN")
        severity = case_dict.get("severity", "HIGH")
        j_state = case_dict.get("jurisdiction_state", "") or ""
        j_dist = case_dict.get("jurisdiction_district", "") or ""
        viol_sum = case_dict.get("violation_summary", "") or ""
        created_by = case_dict.get("created_by", "")
        assigned_officer = case_dict.get("assigned_officer", "") or ""
        opened_at = case_dict.get("opened_at") or datetime.now(timezone.utc).isoformat()
        updated_at = case_dict.get("updated_at") or datetime.now(timezone.utc).isoformat()
        closed_at = case_dict.get("closed_at")
        closure_reason = case_dict.get("closure_reason", "") or ""
        resolution_type = case_dict.get("resolution_type", "") or ""
        
        timeline = case_dict.get("timeline", [])
        if not isinstance(timeline, str):
            timeline = json.dumps(timeline)
        created_at = case_dict.get("created_at") or datetime.now(timezone.utc).isoformat()

        await db.execute('''
            INSERT OR REPLACE INTO enforcement_cases (
                id, case_reference, analysis_id, review_id, product_id,
                organization_id, merchant_organization_id, product_name,
                status, severity, jurisdiction_state, jurisdiction_district,
                violation_summary, created_by, assigned_officer,
                opened_at, updated_at, closed_at, closure_reason,
                resolution_type, timeline, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            c_id, c_ref, ana_id, rev_id, prod_id,
            org_id, m_org_id, prod_name,
            status, severity, j_state, j_dist,
            viol_sum, created_by, assigned_officer,
            opened_at, updated_at, closed_at, closure_reason,
            resolution_type, timeline, created_at
        ))
        await db.commit()
    finally:
        await db.close()


async def insert_enforcement_case(case_dict: Dict[str, Any]) -> None:
    """Insert a brand-new enforcement case using plain INSERT (no OR REPLACE).

    Unlike save_enforcement_case (which uses INSERT OR REPLACE for updates),
    this function uses a strict INSERT so that SQLite's partial UNIQUE index on
    (analysis_id) WHERE status NOT IN ('RESOLVED','CLOSED') raises an
    IntegrityError if a concurrent request already committed an active case for
    the same analysis_id.  This provides a database-level safety net independent
    of the application-level threading.Lock.

    Call this ONLY when creating a new case (not for updates/transitions).
    """
    import aiosqlite as _aiosqlite
    db = await get_db()
    try:
        c_id = case_dict["id"]
        c_ref = case_dict.get("case_reference") or generate_case_reference()
        ana_id = case_dict["analysis_id"]
        rev_id = case_dict.get("review_id", "") or ""
        prod_id = case_dict.get("product_id", "") or ""
        org_id = case_dict.get("organization_id", "org_ministry")
        m_org_id = case_dict.get("merchant_organization_id", "") or ""
        prod_name = case_dict.get("product_name", "") or ""
        status = case_dict.get("status", "OPEN")
        severity = case_dict.get("severity", "HIGH")
        j_state = case_dict.get("jurisdiction_state", "") or ""
        j_dist = case_dict.get("jurisdiction_district", "") or ""
        viol_sum = case_dict.get("violation_summary", "") or ""
        created_by = case_dict.get("created_by", "")
        assigned_officer = case_dict.get("assigned_officer", "") or ""
        opened_at = case_dict.get("opened_at") or datetime.now(timezone.utc).isoformat()
        updated_at = case_dict.get("updated_at") or datetime.now(timezone.utc).isoformat()
        closed_at = case_dict.get("closed_at")
        closure_reason = case_dict.get("closure_reason", "") or ""
        resolution_type = case_dict.get("resolution_type", "") or ""

        timeline = case_dict.get("timeline", [])
        if not isinstance(timeline, str):
            timeline = json.dumps(timeline)
        created_at = case_dict.get("created_at") or datetime.now(timezone.utc).isoformat()

        try:
            await db.execute('''
                INSERT INTO enforcement_cases (
                    id, case_reference, analysis_id, review_id, product_id,
                    organization_id, merchant_organization_id, product_name,
                    status, severity, jurisdiction_state, jurisdiction_district,
                    violation_summary, created_by, assigned_officer,
                    opened_at, updated_at, closed_at, closure_reason,
                    resolution_type, timeline, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                c_id, c_ref, ana_id, rev_id, prod_id,
                org_id, m_org_id, prod_name,
                status, severity, j_state, j_dist,
                viol_sum, created_by, assigned_officer,
                opened_at, updated_at, closed_at, closure_reason,
                resolution_type, timeline, created_at
            ))
            await db.commit()
        except Exception as exc:
            # Re-raise with a clear message so the API layer can map it to HTTP 409
            raise exc
    finally:
        await db.close()


async def get_enforcement_case(case_id_or_ref: str) -> Optional[Dict[str, Any]]:
    """Retrieve an enforcement case by UUID id or case_reference."""
    db = await get_db()
    try:
        async with db.execute(
            'SELECT * FROM enforcement_cases WHERE id = ? OR case_reference = ?',
            (case_id_or_ref, case_id_or_ref)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            c = dict(row)
            if isinstance(c.get("timeline"), str):
                try:
                    c["timeline"] = json.loads(c["timeline"])
                except Exception:
                    c["timeline"] = []
            return c
    finally:
        await db.close()


async def get_enforcement_case_by_analysis_id(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve active or existing case associated with an analysis."""
    db = await get_db()
    try:
        async with db.execute(
            'SELECT * FROM enforcement_cases WHERE analysis_id = ? ORDER BY created_at DESC LIMIT 1',
            (analysis_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            c = dict(row)
            if isinstance(c.get("timeline"), str):
                try:
                    c["timeline"] = json.loads(c["timeline"])
                except Exception:
                    c["timeline"] = []
            return c
    finally:
        await db.close()


async def list_enforcement_cases(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    assigned_officer: Optional[str] = None,
    jurisdiction_state: Optional[str] = None,
    jurisdiction_district: Optional[str] = None,
    merchant_organization_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Server-side filterable, priority-sorted list of enforcement cases."""
    db = await get_db()
    try:
        query = 'SELECT * FROM enforcement_cases WHERE 1=1'
        count_query = 'SELECT COUNT(*) as cnt FROM enforcement_cases WHERE 1=1'
        params: List[Any] = []
        count_params: List[Any] = []

        if status:
            query += ' AND status = ?'
            count_query += ' AND status = ?'
            params.append(status.upper())
            count_params.append(status.upper())

        if severity:
            query += ' AND severity = ?'
            count_query += ' AND severity = ?'
            params.append(severity.upper())
            count_params.append(severity.upper())

        if assigned_officer:
            query += ' AND assigned_officer = ?'
            count_query += ' AND assigned_officer = ?'
            params.append(assigned_officer)
            count_params.append(assigned_officer)

        if jurisdiction_state:
            query += ' AND LOWER(jurisdiction_state) = LOWER(?)'
            count_query += ' AND LOWER(jurisdiction_state) = LOWER(?)'
            params.append(jurisdiction_state)
            count_params.append(jurisdiction_state)

        if jurisdiction_district:
            query += ' AND LOWER(jurisdiction_district) = LOWER(?)'
            count_query += ' AND LOWER(jurisdiction_district) = LOWER(?)'
            params.append(jurisdiction_district)
            count_params.append(jurisdiction_district)

        if merchant_organization_id:
            query += ' AND merchant_organization_id = ?'
            count_query += ' AND merchant_organization_id = ?'
            params.append(merchant_organization_id)
            count_params.append(merchant_organization_id)

        if organization_id:
            query += ' AND (organization_id = ? OR organization_id = "org_ministry")'
            count_query += ' AND (organization_id = ? OR organization_id = "org_ministry")'
            params.append(organization_id)
            count_params.append(organization_id)

        if search:
            search_clause = ' AND (case_reference LIKE ? OR product_name LIKE ? OR violation_summary LIKE ?)'
            query += search_clause
            count_query += search_clause
            p_val = f"%{search.strip()}%"
            params.extend([p_val, p_val, p_val])
            count_params.extend([p_val, p_val, p_val])

        # Severity ranking (CRITICAL > HIGH > MEDIUM > LOW) + newest opened_at
        query += '''
            ORDER BY 
                CASE severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    WHEN 'LOW' THEN 4
                    ELSE 5
                END ASC,
                opened_at DESC
            LIMIT ? OFFSET ?
        '''
        params.extend([limit, offset])

        async with db.execute(count_query, tuple(count_params)) as cur:
            c_row = await cur.fetchone()
            total_count = c_row['cnt'] if c_row else 0

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            cases = []
            for r in rows:
                c = dict(r)
                if isinstance(c.get("timeline"), str):
                    try:
                        c["timeline"] = json.loads(c["timeline"])
                    except Exception:
                        c["timeline"] = []
                cases.append(c)
            return cases, total_count
    finally:
        await db.close()


async def save_enforcement_notice(notice_dict: Dict[str, Any]) -> None:
    """Insert or update an enforcement statutory notice record."""
    db = await get_db()
    try:
        n_id = notice_dict["id"]
        n_ref = notice_dict.get("notice_reference") or generate_notice_reference(notice_dict.get("notice_type", "SHOW_CAUSE"))
        case_id = notice_dict["case_id"]
        n_type = notice_dict.get("notice_type", "SHOW_CAUSE")
        status = notice_dict.get("status", "ISSUED")
        issued_by = notice_dict.get("issued_by", "")
        issued_at = notice_dict.get("issued_at") or datetime.now(timezone.utc).isoformat()
        recip_org = notice_dict.get("recipient_organization_id", "") or ""
        recip_name = notice_dict.get("recipient_name", "") or ""
        subject = notice_dict.get("subject", "Statutory Notice under Legal Metrology Act, 2009")
        content = notice_dict.get("content", "")
        deadline_days = int(notice_dict.get("deadline_days", 15))
        created_at = notice_dict.get("created_at") or datetime.now(timezone.utc).isoformat()
        updated_at = notice_dict.get("updated_at") or datetime.now(timezone.utc).isoformat()

        await db.execute('''
            INSERT OR REPLACE INTO enforcement_notices (
                id, notice_reference, case_id, notice_type, status,
                issued_by, issued_at, recipient_organization_id,
                recipient_name, subject, content, deadline_days,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            n_id, n_ref, case_id, n_type, status,
            issued_by, issued_at, recip_org,
            recip_name, subject, content, deadline_days,
            created_at, updated_at
        ))
        await db.commit()
    finally:
        await db.close()


async def get_enforcement_notice(notice_id_or_ref: str) -> Optional[Dict[str, Any]]:
    """Retrieve an enforcement notice by ID or reference number."""
    db = await get_db()
    try:
        async with db.execute(
            'SELECT * FROM enforcement_notices WHERE id = ? OR notice_reference = ?',
            (notice_id_or_ref, notice_id_or_ref)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)
    finally:
        await db.close()


async def list_enforcement_notices_by_case(case_id: str) -> List[Dict[str, Any]]:
    """Retrieve all notices issued under a specific case."""
    db = await get_db()
    try:
        async with db.execute(
            'SELECT * FROM enforcement_notices WHERE case_id = ? ORDER BY issued_at DESC',
            (case_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def save_penalty_calculation(penalty_dict: Dict[str, Any]) -> None:
    """Save an immutable penalty calculation record linked to a case."""
    db = await get_db()
    try:
        p_id = penalty_dict.get("id") or f"pen-{uuid.uuid4().hex[:8]}"
        case_id = penalty_dict["case_id"]
        ana_id = penalty_dict["analysis_id"]
        applicable = 1 if penalty_dict.get("applicable", True) else 0
        est_fine = float(penalty_dict.get("estimated_fine_inr", 0.0))
        f_min = float(penalty_dict.get("fine_range_min_inr", penalty_dict.get("fine_range_inr", [0, 0])[0] if isinstance(penalty_dict.get("fine_range_inr"), (list, tuple)) else 0.0))
        f_max = float(penalty_dict.get("fine_range_max_inr", penalty_dict.get("fine_range_inr", [0, 0])[1] if isinstance(penalty_dict.get("fine_range_inr"), (list, tuple)) else est_fine))
        basis = penalty_dict.get("basis", "")
        sections = penalty_dict.get("sections", [])
        if not isinstance(sections, str):
            sections = json.dumps(sections)
        repeat = 1 if penalty_dict.get("repeat_offence") else 0
        prior = int(penalty_dict.get("prior_notices", 0))
        v_count = int(penalty_dict.get("violation_count", 0))
        by_user = penalty_dict.get("calculated_by", "")
        at_time = penalty_dict.get("calculated_at") or datetime.now(timezone.utc).isoformat()
        reason = penalty_dict.get("reason", "") or ""
        created_at = penalty_dict.get("created_at") or datetime.now(timezone.utc).isoformat()

        await db.execute('''
            INSERT INTO penalty_calculations (
                id, case_id, analysis_id, applicable,
                estimated_fine_inr, fine_range_min_inr, fine_range_max_inr,
                basis, sections, repeat_offence, prior_notices,
                violation_count, calculated_by, calculated_at, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            p_id, case_id, ana_id, applicable,
            est_fine, f_min, f_max,
            basis, sections, repeat, prior,
            v_count, by_user, at_time, reason, created_at
        ))
        await db.commit()
    finally:
        await db.close()


async def list_penalties_by_case(case_id: str) -> List[Dict[str, Any]]:
    """Retrieve full chronological penalty calculation history for a case."""
    db = await get_db()
    try:
        async with db.execute(
            'SELECT * FROM penalty_calculations WHERE case_id = ? ORDER BY calculated_at DESC',
            (case_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            records = []
            for r in rows:
                p = dict(r)
                p["applicable"] = bool(p["applicable"])
                p["repeat_offence"] = bool(p["repeat_offence"])
                if isinstance(p.get("sections"), str):
                    try:
                        p["sections"] = json.loads(p["sections"])
                    except Exception:
                        p["sections"] = []
                records.append(p)
            return records
    finally:
        await db.close()


async def get_enforcement_dashboard_metrics(
    organization_id: Optional[str] = None,
    officer_username: Optional[str] = None
) -> Dict[str, Any]:
    """Aggregate live KPI metrics for Enforcement Dashboard strictly scoped to organization_id."""
    db = await get_db()
    try:
        where_clause = " WHERE 1=1"
        params: List[Any] = []
        if organization_id:
            where_clause += " AND organization_id = ?"
            params.append(organization_id)

        # Status counts
        query = f'''
            SELECT 
                COUNT(*) as total_cases,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_cnt,
                SUM(CASE WHEN status = 'INVESTIGATION' THEN 1 ELSE 0 END) as inv_cnt,
                SUM(CASE WHEN status = 'PENALTY_REVIEW' THEN 1 ELSE 0 END) as pen_cnt,
                SUM(CASE WHEN status = 'NOTICE_ISSUED' THEN 1 ELSE 0 END) as not_cnt,
                SUM(CASE WHEN status = 'HEARING' THEN 1 ELSE 0 END) as hear_cnt,
                SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) as res_cnt,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed_cnt,
                SUM(CASE WHEN status NOT IN ('RESOLVED', 'CLOSED') THEN 1 ELSE 0 END) as active_cnt
            FROM enforcement_cases {where_clause}
        '''
        async with db.execute(query, tuple(params)) as cur:
            row = await cur.fetchone()
            open_cnt = row['open_cnt'] or 0 if row else 0
            inv_cnt = row['inv_cnt'] or 0 if row else 0
            pen_cnt = row['pen_cnt'] or 0 if row else 0
            not_cnt = row['not_cnt'] or 0 if row else 0
            hear_cnt = row['hear_cnt'] or 0 if row else 0
            res_cnt = row['res_cnt'] or 0 if row else 0
            closed_cnt = row['closed_cnt'] or 0 if row else 0
            active_cnt = row['active_cnt'] or 0 if row else 0

        # Assigned to specific officer within org
        assigned_to_me = 0
        if officer_username:
            a_query = "SELECT COUNT(*) as cnt FROM enforcement_cases WHERE assigned_officer = ? AND status NOT IN ('RESOLVED', 'CLOSED')"
            a_params: List[Any] = [officer_username]
            if organization_id:
                a_query += " AND organization_id = ?"
                a_params.append(organization_id)
            async with db.execute(a_query, tuple(a_params)) as cur:
                a_row = await cur.fetchone()
                assigned_to_me = a_row['cnt'] if a_row else 0

        # Notices count strictly scoped to organization
        if organization_id:
            n_query = '''
                SELECT COUNT(n.id) as cnt 
                FROM enforcement_notices n 
                INNER JOIN enforcement_cases c ON n.case_id = c.id 
                WHERE c.organization_id = ?
            '''
            async with db.execute(n_query, (organization_id,)) as cur:
                n_row = await cur.fetchone()
                total_notices = n_row['cnt'] if n_row else 0
        else:
            async with db.execute("SELECT COUNT(*) as cnt FROM enforcement_notices") as cur:
                n_row = await cur.fetchone()
                total_notices = n_row['cnt'] if n_row else 0

        # Total penalties estimated strictly scoped to organization
        if organization_id:
            p_query = '''
                SELECT SUM(p.estimated_fine_inr) as total_fine 
                FROM penalty_calculations p 
                INNER JOIN enforcement_cases c ON p.case_id = c.id 
                WHERE c.organization_id = ?
            '''
            async with db.execute(p_query, (organization_id,)) as cur:
                p_row = await cur.fetchone()
                total_fine = float(p_row['total_fine'] or 0.0) if p_row else 0.0
        else:
            async with db.execute("SELECT SUM(estimated_fine_inr) as total_fine FROM penalty_calculations") as cur:
                p_row = await cur.fetchone()
                total_fine = float(p_row['total_fine'] or 0.0) if p_row else 0.0

        return {
            "open_cases": open_cnt,
            "investigation_cases": inv_cnt,
            "penalty_review_cases": pen_cnt,
            "notices_issued_cases": not_cnt,
            "hearing_cases": hear_cnt,
            "resolved_cases": res_cnt,
            "closed_cases": closed_cnt,
            "total_active_cases": active_cnt,
            "assigned_to_me": assigned_to_me,
            "total_penalties_estimated_inr": total_fine,
            "total_notices_served": total_notices,
        }
    finally:
        await db.close()


