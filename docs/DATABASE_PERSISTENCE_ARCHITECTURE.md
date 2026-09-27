# MetrCheck AI: Database Persistence & Storage Architecture

**Document Version**: 2.4.0  
**Target Milestone**: Milestone 4 (Database Persistence & Storage Architecture - R4)  
**Status**: APPROVED & ACTIVE  
**Engine**: Async SQLite (`aiosqlite`) + Write-Ahead Logging (WAL)  
**Isolation**: Multi-Tenant Row-Level Scoping & Fail-Closed RBAC  

---

## Table of Contents
1. [Overview & Concurrency Model](#1-overview--concurrency-model)
   - 1.1 Architectural Rationale & Engine Selection
   - 1.2 Write-Ahead Logging (WAL) Mode Mechanics
   - 1.3 Asynchronous Non-Blocking Execution via `aiosqlite`
   - 1.4 Busy Handler & Concurrency Queueing (`busy_timeout=5000`)
   - 1.5 WAL Checkpoint Management
2. [18-Table Relational Schema & Idempotent Migrations](#2-18-table-relational-schema--idempotent-migrations)
   - 2.1 Complete Relational Entity Inventory
   - 2.2 Table Schemas, Constraints & Indexes
   - 2.3 Idempotent Zero-Downtime Migration Architecture
   - 2.4 Canonical Organization & User Seeding
3. [Multi-Tenant Scoping & Fail-Closed RBAC](#3-multi-tenant-scoping--fail-closed-rbac)
   - 3.1 Organization Hierarchy & Tenancy Model
   - 3.2 Security Guard Implementation (`check_tenant_access`)
   - 3.3 Defense-in-Depth Query Filtering
4. [Query Interface & Review Symbols](#4-query-interface--review-symbols)
   - 4.1 Filtered Query Interface (`list_reviews`)
   - 4.2 Review Symbols & Backward Compatibility Alias (`list_officer_reviews`)
5. [Cloud Storage & Free-Tier Persistence Strategy](#5-cloud-storage--free-tier-persistence-strategy)
   - 5.1 Docker Volume Mounts (`/data/metrcheck.db`, `/data/uploads`)
   - 5.2 Hugging Face Spaces Free-Tier Ephemeral Storage Reality & Automated Dataset Checkpoint Synchronization Strategy
   - 5.3 Production Safety Guard Architecture (`_check_safety_guard` & `_is_cloud_production_path`)
6. [Verification & Maintenance Runbook](#6-verification--maintenance-runbook)
   - 6.1 Concurrency & WAL Mode Health Checks
   - 6.2 18-Table Schema Integrity Audit
   - 6.3 Multi-Tenant Boundary Validation
   - 6.4 Disaster Recovery & Checkpoint Synchronization Runbook

---

## 1. Overview & Concurrency Model

### 1.1 Architectural Rationale & Engine Selection
MetrCheck AI operates as an automated regulatory compliance screening and visual audit system for packaged commodities in India. The application requires robust, transactional persistence for compliance audits, packaging images, pre-print artwork dockets, user accounts, and cryptographic legal logs.

To satisfy the core requirement of **zero monthly hosting cost on legitimate free tiers** while eliminating laptop dependencies, MetrCheck AI utilizes an optimized **asynchronous SQLite (`aiosqlite`) architecture**. This eliminates the financial overhead and operational complexity of running external database server clusters (e.g. AWS RDS or GCP Cloud SQL) while delivering microsecond read latencies and ACID transaction guarantees.

### 1.2 Write-Ahead Logging (WAL) Mode Mechanics
Traditional SQLite rollback journals enforce a single-writer / single-reader lock on the database file, causing reader starvation during heavy audit workloads. MetrCheck AI strictly configures Write-Ahead Logging (WAL) mode upon every connection:

```sql
PRAGMA journal_mode=WAL;
```

**Key Concurrency Benefits**:
1. **Readers Do Not Block Writers**: Reading coroutines read consistent snapshots from the main database file (`metrcheck.db`) and the shared-memory index (`metrcheck.db-shm`), while writers simultaneously append new transactions to the WAL file (`metrcheck.db-wal`).
2. **Writers Do Not Block Readers**: Read queries execute concurrently without waiting for write transactions (such as OCR analysis commits) to complete.
3. **Reduced Disk I/O Overhead**: Disk writes in WAL mode are sequential append-only operations, dramatically minimizing random-write latency on cloud container storage.

### 1.3 Asynchronous Non-Blocking Execution via `aiosqlite`
Python's standard `sqlite3` driver executes synchronously, which would block FastAPI's `asyncio` event loop during intensive disk I/O. MetrCheck AI wraps all database operations with `aiosqlite`, delegating SQLite operations to an underlying thread pool executor.

The connection factory in `backend/database/db.py`:
```python
async def get_db():
    _check_safety_guard()
    db = await aiosqlite.connect(settings.DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA busy_timeout=5000;")
    return db
```

### 1.4 Busy Handler & Concurrency Queueing (`busy_timeout=5000`)
Under SQLite's single-writer model, concurrent write transactions must serialize. To prevent immediate `sqlite3.OperationalError: database is locked` failures when multiple users submit packaging analyses simultaneously, the connection factory enforces:

```sql
PRAGMA busy_timeout=5000;
```

When a writer encounters a locked table, SQLite automatically retries with exponential backoff for up to 5,000 milliseconds (5.0 seconds). This queueing window provides seamless handling of high concurrency spikes across asynchronous workers.

### 1.5 WAL Checkpoint Management
Transactions in the `-wal` file must periodically merge into the main database file. MetrCheck AI handles checkpointing through two mechanisms:
1. **Automatic SQLite Checkpointing**: SQLite triggers a passive checkpoint when the WAL reaches 1,000 pages (~4MB).
2. **Passive Programmatic Checkpointing**: During cloud persistence sync cycles and graceful shutdown, the system issues:
   ```sql
   PRAGMA wal_checkpoint(PASSIVE);
   ```
   `PASSIVE` checkpoints copy as many committed frames as possible without waiting for active readers or interrupting ongoing requests.

---

## 2. 18-Table Relational Schema & Idempotent Migrations

### 2.1 Complete Relational Entity Inventory
MetrCheck AI provisions an 18-table relational schema designed for multi-tenant isolation, statutory compliance verification, and cryptographic auditability:

| # | Table Name | Purpose | Primary Key | Key Relationships / Tenant Scoping |
|---|------------|---------|-------------|------------------------------------|
| 1 | `organizations` | Tenant isolation root boundaries | `id` (TEXT) | Parent for users, products, analyses |
| 2 | `products` | Merchant product catalog master records | `id` (TEXT) | Scoped by `organization_id`, `owner_user_id` |
| 3 | `analyses` | Commodity scan results, OCR & compliance | `id` (TEXT) | Scoped by `organization_id`, links to `product_id` |
| 4 | `users` | User credentials, roles, token versions | `id` (INTEGER AUTO) | Scoped by `organization_id` |
| 5 | `password_resets` | Password reset tokens & expiration | `id` (INTEGER AUTO) | Links to `username` |
| 6 | `account_audit_logs` | User identity & authentication events | `id` (INTEGER AUTO) | Links to `actor_username`, `target_username` |
| 7 | `evidence_audit_logs` | Officer corrections to bounding boxes | `id` (INTEGER AUTO) | Scoped by `organization_id`, links to `analysis_id` |
| 8 | `artworks` | Pre-print packaging artwork iterations | `id` (TEXT) | Scoped by `organization_id`, links to `product_id` |
| 9 | `version_comparisons`| Packaging version compliance diffs | `id` (TEXT) | Scoped by `organization_id`, links to version IDs |
| 10 | `officer_reviews` | Legal Metrology & FSSAI officer reviews | `id` (TEXT) | Scoped by `organization_id`, links to `analysis_id` |
| 11 | `verification_cache`| External FSSAI & GS1 API lookup cache | `(type, value)` | Composite PK for high-speed cache lookups |
| 12 | `security_audit_logs`| Tamper-evident cryptographic log | `id` (INTEGER AUTO) | SHA-256 hash chained (`prev_hash`, `event_hash`)|
| 13 | `download_tickets` | Short-lived single-use download tokens | `id` (TEXT) | Scoped by `organization_id`, indexed by `expires_at`|
| 14 | `rate_limit_events` | Multi-worker sliding-window rate limits| `id` (INTEGER AUTO) | Compound index `(key, timestamp)` |
| 15 | `officer_access_requests` | Officer registration applications | `id` (INTEGER AUTO) | Scoped by jurisdiction and status |
| 16 | `enforcement_cases` | Statutory non-compliance legal cases | `id` (TEXT) | Scoped by `organization_id`, partial unique index |
| 17 | `enforcement_notices` | Legal Show-Cause & Demand notices | `id` (TEXT) | Scoped by `recipient_organization_id`, links to case|
| 18 | `penalty_calculations`| Legal compounding fee assessments | `id` (TEXT) | Links to `case_id`, `analysis_id` |

### 2.2 Table Schemas, Constraints & Indexes

#### 1. `organizations`
```sql
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    org_type TEXT NOT NULL DEFAULT 'MERCHANT',
    jurisdiction TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

#### 2. `products`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_products_org ON products(organization_id);
CREATE INDEX IF NOT EXISTS idx_products_owner ON products(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_products_gtin ON products(gtin_barcode);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
```

#### 3. `analyses`
```sql
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
    product_id TEXT DEFAULT '',
    integrity_hash TEXT DEFAULT '',
    system_version TEXT DEFAULT '',
    ocr_engine_version TEXT DEFAULT '',
    ruleset_version TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_analyses_org ON analyses(organization_id);
CREATE INDEX IF NOT EXISTS idx_analyses_product_id ON analyses(product_id);
```

#### 4. `users`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL AND email != '';
```

#### 5. `password_resets`
```sql
CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);
```

#### 6. `account_audit_logs`
```sql
CREATE TABLE IF NOT EXISTS account_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_username TEXT,
    target_username TEXT,
    event_type TEXT NOT NULL,
    details TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
```

#### 7. `evidence_audit_logs`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_evidence_audit_org ON evidence_audit_logs(organization_id);
```

#### 8. `artworks`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_artworks_org ON artworks(organization_id);
CREATE INDEX IF NOT EXISTS idx_artworks_product_id ON artworks(product_id);
```

#### 9. `version_comparisons`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_version_comparisons_org ON version_comparisons(organization_id);
CREATE INDEX IF NOT EXISTS idx_version_comp_org ON version_comparisons(organization_id);
```

#### 10. `officer_reviews`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_officer_reviews_org ON officer_reviews(organization_id);
CREATE INDEX IF NOT EXISTS idx_reviews_org ON officer_reviews(organization_id);
```

#### 11. `verification_cache`
```sql
CREATE TABLE IF NOT EXISTS verification_cache (
    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    record_json TEXT NOT NULL,
    source TEXT NOT NULL,
    cached_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (identifier_type, identifier_value)
);
```

#### 12. `security_audit_logs` (Cryptographic SHA-256 Hash Chain)
```sql
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
);
```

#### 13. `download_tickets` (Single-Use Short-Lived HMAC Tokens)
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_download_tickets_exp ON download_tickets(expires_at);
```

#### 14. `rate_limit_events` (Distributed Sliding-Window Events)
```sql
CREATE TABLE IF NOT EXISTS rate_limit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_ts ON rate_limit_events(key, timestamp);
```

#### 15. `officer_access_requests`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_officer_req_id ON officer_access_requests(request_id);
CREATE INDEX IF NOT EXISTS idx_officer_req_status ON officer_access_requests(status);
CREATE INDEX IF NOT EXISTS idx_officer_req_email ON officer_access_requests(official_email);
```

#### 16. `enforcement_cases`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_enf_cases_ref ON enforcement_cases(case_reference);
CREATE INDEX IF NOT EXISTS idx_enf_cases_org ON enforcement_cases(organization_id);
CREATE INDEX IF NOT EXISTS idx_enf_cases_merch_org ON enforcement_cases(merchant_organization_id);
CREATE INDEX IF NOT EXISTS idx_enf_cases_status ON enforcement_cases(status);
CREATE INDEX IF NOT EXISTS idx_enf_cases_assigned ON enforcement_cases(assigned_officer);
CREATE INDEX IF NOT EXISTS idx_enf_cases_analysis ON enforcement_cases(analysis_id);
-- Partial unique index: strictly prevents duplicate active cases on the same analysis
CREATE UNIQUE INDEX IF NOT EXISTS idx_enf_cases_unique_active_analysis 
ON enforcement_cases(analysis_id) 
WHERE status NOT IN ('RESOLVED', 'CLOSED');
```

#### 17. `enforcement_notices`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_enf_notices_ref ON enforcement_notices(notice_reference);
CREATE INDEX IF NOT EXISTS idx_enf_notices_case ON enforcement_notices(case_id);
CREATE INDEX IF NOT EXISTS idx_enf_notices_recip_org ON enforcement_notices(recipient_organization_id);
```

#### 18. `penalty_calculations`
```sql
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
);
CREATE INDEX IF NOT EXISTS idx_penalties_case ON penalty_calculations(case_id);
CREATE INDEX IF NOT EXISTS idx_penalties_analysis ON penalty_calculations(analysis_id);
```

### 2.3 Idempotent Zero-Downtime Migration Architecture
MetrCheck AI executes migrations programmatically inside `init_db()` upon container boot. This design guarantees zero manual maintenance requirements:

1. **Table Creation**: `CREATE TABLE IF NOT EXISTS` ensures safety against existing schemas.
2. **Column Additions**: Evolution occurs via automated `ALTER TABLE <tbl> ADD COLUMN <col> <typedef>` wrapped inside `try...except Exception: pass`. If the column exists, SQLite raises an operational error which is safely ignored.
3. **Index Creation**: `CREATE INDEX IF NOT EXISTS` guarantees that missing indexes are applied without re-indexing penalties.
4. **Data Backfilling**:
   - Updates existing users with missing `status` or `token_version`.
   - Idempotently resolves and provisions tenant organizations for unassigned users using `resolve_default_organization_for_user()`.
   - Backfills non-compliant historical analyses into `officer_reviews` if not already present.

### 2.4 Canonical Organization & User Seeding
`init_db()` provisions three canonical root organizations via `ON CONFLICT(id) DO UPDATE`:
- `org_ministry`: Regulator ("Ministry of Consumer Affairs & Legal Metrology Directorate", `REGULATOR`, National).
- `org_merchant_demo`: Merchant ("Demo Merchant Brand Packaging Corp", `MERCHANT`, National).
- `org_user_demo`: Consumer/Public User Space ("Personal User Space", `USER`, National).

Default demo accounts (`admin`, `officer`, `merchant`, `audit`, `user`) are seeded idempotently with secure default credentials if not already present.

---

## 3. Multi-Tenant Scoping & Fail-Closed RBAC

### 3.1 Organization Hierarchy & Tenancy Model
MetrCheck AI enforces strict multi-tenant organizational isolation:
- Every data entity (`analyses`, `artworks`, `products`, `officer_reviews`, `enforcement_cases`, etc.) carries an `organization_id`.
- Users are assigned to an `organization_id`.
- Access controls operate on a **fail-closed** policy: any ambiguous or unassigned tenancy claim defaults to access denial (`403 Forbidden`).

### 3.2 Security Guard Implementation (`check_tenant_access`)
The authoritative multi-tenant boundary guard is implemented in `backend/auth/security.py`:

```python
def check_tenant_access(
    user: Optional[dict],
    resource: Optional[dict],
    allow_public: bool = False,
    raise_exception: bool = False
) -> bool:
    """
    Multi-tenant isolation security enforcement guard (Strictly Fail-Closed).
    """
    if not user:
        if allow_public:
            return True
        if raise_exception:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return False

    if not resource:
        if raise_exception:
            raise HTTPException(status_code=404, detail="Resource not found.")
        return False

    user_role = user.get("role")
    
    # 1. Admin: System-wide statutory oversight across all organizations
    if user_role == ROLE_ADMIN:
        return True

    user_org = (user.get("organization_id") or "").strip()
    res_org = (resource.get("organization_id") or "").strip()
    owner = (resource.get("owner_user_id") or "").strip()
    username = (user.get("username") or "").strip()
    uid = str(user.get("id", "")).strip() if user.get("id") is not None else ""

    # 2. Enforcement / Audit Officers: Strictly scoped to their organization_id
    if user_role in (ROLE_ENFORCEMENT, ROLE_AUDIT):
        if not user_org or not res_org or user_org != res_org:
            if raise_exception:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Resource does not belong to your organization."
                )
            return False
        return True

    # 3. Normal Users: Strictly scoped to personal scan ownership
    if user_role in (ROLE_USER, "NORMAL_USER", "USER", "PUBLIC_USER"):
        is_owner = False
        if owner:
            is_owner = (owner.lower() == username.lower()) or (bool(uid) and owner == uid)
        if not is_owner:
            if raise_exception:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You do not have permission to access this resource."
                )
            return False
        return True

    # 4. Merchants: Scoped to organization_id AND record ownership
    if user_role == ROLE_MERCHANT:
        if not user_org or not res_org or user_org != res_org:
            if raise_exception:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Resource does not belong to your organization."
                )
            return False
        
        is_owner = False
        if owner:
            is_owner = (owner.lower() == username.lower()) or (bool(uid) and owner == uid)
        if not is_owner:
            if raise_exception:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You do not have permission to access this resource."
                )
            return False
        return True

    if raise_exception:
        raise HTTPException(status_code=403, detail="Access denied: Insufficient privileges.")
    return False
```

### 3.3 Defense-in-Depth Query Filtering
Tenant scoping is enforced at two distinct layers:
1. **Database Query Level**: All read queries (`get_analyses`, `list_reviews`, `list_artworks`, `list_enforcement_cases`) accept an optional `organization_id` parameter, injecting `WHERE organization_id = ?` directly into the SQL statement.
2. **Application Boundary Guard**: When fetching individual entities by ID (`/api/compliance/evidence/{id}`, `/api/report/{id}`, `/api/history/{id}`), `check_tenant_access(user, resource, raise_exception=True)` runs prior to returning data, preventing Horizontal Privilege Escalation (IDOR).

---

## 4. Query Interface & Review Symbols

### 4.1 Filtered Query Interface (`list_reviews`)
Officer review records are queried through `list_reviews` in `backend/database/db.py`:

```python
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
```

### 4.2 Review Symbols & Backward Compatibility Alias (`list_officer_reviews`)
In early iterations and architectural contract specifications, the query function was referred to as `list_officer_reviews`. While internal backend services (`review_service.py`, `review_routes.py`) invoke `list_reviews`, external integration tests and contract suites import `list_officer_reviews`.

To maintain strict contract compliance and prevent `ImportError` regressions, `backend/database/db.py` explicitly exports the module-level alias:

```python
# Alias for backward compatibility with external callers and M4 contract test suites
list_officer_reviews = list_reviews
```

**Verification Invariant**:
```python
from database.db import list_officer_reviews, list_reviews
assert list_officer_reviews is list_reviews
```

---

## 5. Cloud Storage & Free-Tier Persistence Strategy

### 5.1 Docker Volume Mounts (`/data/metrcheck.db`, `/data/uploads`)
In production containers (`Dockerfile`), storage paths are defined via standard environment variables:

```dockerfile
ENV PYTHONUNBUFFERED=1 \
    OCR_ENGINE=paddleocr \
    UPLOAD_DIR=/data/uploads \
    DATABASE_PATH=/data/metrcheck.db
```

Permissions and non-root execution:
- Container runs as non-root user `user` (UID 1000).
- Storage directories `/data` and `/data/uploads` are created and chowned to UID 1000:
  ```dockerfile
  RUN mkdir -p /data/uploads && chown -R 1000:1000 /data && chmod -R 777 /data
  ```
- In local and staging deployments, `docker-compose.yml` mounts host persistent storage:
  ```yaml
  volumes:
    - ./data:/data
  ```

### 5.2 Hugging Face Spaces Free-Tier Ephemeral Storage Reality & Automated Dataset Checkpoint Synchronization Strategy

#### The Free-Tier Ephemeral Reality
Hugging Face Spaces provides 16 GB RAM / 2 vCPU Docker container compute on its free tier. While the container environment grants 50 GB of disk space, **this disk storage is strictly ephemeral**:
1. When a Space goes to sleep after 48 hours of inactivity, the container is stopped.
2. When restarted (or rebuilt on a git push), a fresh Docker container is provisioned from the image build.
3. Any files written to `/data/metrcheck.db` or `/data/uploads` during runtime are **permanently wiped**.
4. Hugging Face offers Persistent Storage Volumes as a paid hardware add-on starting at **$5.00/month** (20 GB tier).

Because `ORIGINAL_REQUEST.md` mandates:
> *"production-ready, 100% cloud-hosted architecture with zero laptop dependencies, zero mocked data, and **zero monthly hosting cost on legitimate free tiers**"*

relying on paid volumes is prohibited.

#### Automated Dataset Checkpoint Synchronization Strategy
To guarantee 100% data persistence at zero monthly cost, MetrCheck AI implements an automated **Hugging Face Dataset Checkpoint Synchronization Strategy**:

```
 ┌────────────────────────────────────────────────────────┐
 │            Hugging Face Space (Docker Container)       │
 │                                                        │
 │   FastAPI Backend (aiosqlite WAL)                      │
 │     │                                                  │
 │     ├──> Writes to /data/metrcheck.db + -wal           │
 │     │                                                  │
 │     ├──> 1. Cold-Start Hydration:                      │
 │     │      hf_hub_download(repo_type="dataset")        │
 │     │                                                  │
 │     └──> 2. Passive Checkpoint & Snapshot Sync:        │
 │            PRAGMA wal_checkpoint(PASSIVE);            │
 │            upload_file(path="/data/metrcheck.db")      │
 └─────────────────────────┬──────────────────────────────┘
                           │ HTTPS (HF_TOKEN)
                           ▼
 ┌────────────────────────────────────────────────────────┐
 │    Hugging Face Private Dataset Repository             │
 │    (Free Tier: 50 GB Storage, Unlimited Lifespan)      │
 │    repo_id: "omsainikaul/metrcheck-storage-vault"      │
 └────────────────────────────────────────────────────────┘
```

**Strategy Mechanics**:
1. **Storage Vault**: A free, private Hugging Face Dataset repository (e.g. `metrcheck-storage-vault`) serves as persistent cloud object storage.
2. **Authentication**: Uses the Space's existing `HF_TOKEN` secret.
3. **Cold-Start Hydration**: During container boot in `init_db()`:
   - The application checks if `/data/metrcheck.db` exists.
   - If absent, it queries the dataset repository via `huggingface_hub.hf_hub_download`:
     ```python
     from huggingface_hub import hf_hub_download
     db_path = hf_hub_download(
         repo_id=os.environ.get("HF_DATASET_REPO", "omsainikaul/metrcheck-storage-vault"),
         repo_type="dataset",
         filename="metrcheck.db",
         local_dir="/data",
         token=os.environ.get("HF_TOKEN")
     )
     ```
   - If the snapshot exists, it is restored into `/data/metrcheck.db` and immediately opened by `aiosqlite`. If no snapshot exists, `init_db()` creates a fresh database.
4. **Runtime Checkpoint & Sync**:
   - Prior to snapshotting, `PRAGMA wal_checkpoint(PASSIVE);` flushes pending WAL transactions to `metrcheck.db`.
   - The consolidated database is uploaded asynchronously via `huggingface_hub.HfApi().upload_file`.
   - Graceful shutdown handles upload on `SIGTERM` / `SIGINT`.

### 5.3 Production Safety Guard Architecture (`_check_safety_guard` & `_is_cloud_production_path`)

#### The Vulnerability
In standard development, `PROD_DATABASE_PATH` points to `<backend_dir>/metrc_check.db`. Previously, `_check_safety_guard()` only compared:
```python
if resolved_db == PROD_DATABASE_PATH:
    raise RuntimeError(...)
```
In cloud containers, `DATABASE_PATH` is set to `/data/metrcheck.db`. Because `/data/metrcheck.db != PROD_DATABASE_PATH`, automated test suites (`pytest`) or test runs with `TEST_MODE=1` bypassed the safety check entirely, risking production database truncation or corruption.

#### Hardened Safety Guard Implementation
The safety guard in `backend/database/db.py` contains multi-path inspection:

```python
def _is_cloud_production_path(path: str) -> bool:
    """Check if the given path matches the cloud production database location."""
    norm = os.path.normpath(str(path)).replace("\\", "/")
    return (
        norm == "/data/metrcheck.db"
        or norm.startswith("/data/")
        or norm.startswith("c:/data/")
    )


def _check_safety_guard():
    """
    Enforces strict isolation: automated tests cannot connect to or modify
    the production database (local or cloud container).
    """
    is_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    if settings.TEST_MODE or os.environ.get("TEST_MODE") == "1" or is_pytest:
        resolved_db = os.path.abspath(settings.DATABASE_PATH)
        is_cloud_prod = _is_cloud_production_path(resolved_db)
        is_prod_env = (
            os.environ.get("ENVIRONMENT") == "production"
            or os.environ.get("METRCHECK_ENV") == "production"
            or getattr(settings, "ENVIRONMENT", "").lower() == "production"
        )
        if (
            resolved_db == PROD_DATABASE_PATH
            or is_cloud_prod
            or (is_prod_env and "test" not in os.path.basename(resolved_db))
        ):
            raise RuntimeError(
                f"SAFETY ERROR: Automated tests cannot run against the production/cloud database ({resolved_db})!\n"
                f"Please ensure tests use isolated_test_env() or conftest with a dedicated temporary database."
            )
```

**Guaranteed Invariants**:
- Any test execution attempting to point to `/data/metrcheck.db` raises `RuntimeError`.
- Any test execution attempting to point to `PROD_DATABASE_PATH` raises `RuntimeError`.
- Any test execution running in `ENVIRONMENT=production` targeting a non-test DB raises `RuntimeError`.
- Dedicated temporary test databases (e.g. `test_metrc_check.db`) pass through safely.

---

## 6. Verification & Maintenance Runbook

### 6.1 Concurrency & WAL Mode Health Checks
Verify WAL mode and busy timeout on active database:
```bash
sqlite3 /data/metrcheck.db "PRAGMA journal_mode;"
# Expected output: wal

sqlite3 /data/metrcheck.db "PRAGMA busy_timeout;"
# Expected output: 5000
```

Verify WAL and SHM files exist during active transactions:
```bash
ls -la /data/metrcheck.db*
# -rw-r--r-- 1 user user ... /data/metrcheck.db
# -rw-r--r-- 1 user user ... /data/metrcheck.db-wal
# -rw-r--r-- 1 user user ... /data/metrcheck.db-shm
```

### 6.2 18-Table Schema Integrity Audit
Execute SQLite schema audit verifying all 18 tables are provisioned:
```bash
sqlite3 /data/metrcheck.db "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN (
    'organizations', 'products', 'analyses', 'users', 'password_resets',
    'account_audit_logs', 'evidence_audit_logs', 'artworks', 'version_comparisons',
    'officer_reviews', 'verification_cache', 'security_audit_logs',
    'download_tickets', 'rate_limit_events', 'officer_access_requests',
    'enforcement_cases', 'enforcement_notices', 'penalty_calculations'
);"
# Expected output: 18
```

Verify partial index preventing duplicate active enforcement cases:
```bash
sqlite3 /data/metrcheck.db "SELECT sql FROM sqlite_master WHERE name='idx_enf_cases_unique_active_analysis';"
# Expected output contains: WHERE status NOT IN ('RESOLVED', 'CLOSED')
```

### 6.3 Multi-Tenant Boundary Validation
Verify fail-closed isolation across tenant boundaries:
```python
# 1. Admin accesses cross-tenant docket
assert check_tenant_access({"role": "ADMIN"}, {"organization_id": "org_merchant_demo"}) is True

# 2. Officer blocked from accessing different tenant docket
assert check_tenant_access(
    {"role": "ENFORCEMENT_OFFICER", "organization_id": "org_ministry"},
    {"organization_id": "org_merchant_demo"}
) is False

# 3. Merchant blocked from accessing another merchant's docket
assert check_tenant_access(
    {"role": "MERCHANT", "organization_id": "org_alpha", "username": "alice"},
    {"organization_id": "org_beta", "owner_user_id": "bob"}
) is False

# 4. Unauthenticated request blocked
assert check_tenant_access(None, {"organization_id": "org_merchant_demo"}) is False
```

### 6.4 Disaster Recovery & Checkpoint Synchronization Runbook

#### Manual Passive WAL Checkpoint
If container maintenance or snapshotting is required:
```bash
sqlite3 /data/metrcheck.db "PRAGMA wal_checkpoint(PASSIVE);"
```

#### Manual Database Compaction (VACUUM)
To reclaim deleted scan storage:
```bash
sqlite3 /data/metrcheck.db "VACUUM;"
```

#### Database Integrity Check
To verify cryptographic and B-Tree structural integrity:
```bash
sqlite3 /data/metrcheck.db "PRAGMA integrity_check;"
# Expected output: ok
```

#### Manual Dataset Backup (Hugging Face CLI)
```bash
huggingface-cli upload omsainikaul/metrcheck-storage-vault /data/metrcheck.db metrcheck.db --repo-type=dataset
```
