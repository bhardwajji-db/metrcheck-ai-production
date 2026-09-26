# Project: MetrCheck AI Cloud Deployment

## Architecture
MetrCheck AI is an automated regulatory compliance screening and visual audit system for packaged commodities in India. The cloud-hosted architecture operates on legitimate free tiers with zero monthly hosting cost and zero laptop dependencies:

1. **Cloud Compute & Backend Container**:
   - Host: Hugging Face Spaces (Docker Space Tier: free 16 GB RAM, 2 vCPU).
   - Container: Multi-stage Debian Bookworm container (`python:3.11-slim` + Nginx).
   - Backend Runtime: FastAPI (v2.4.0) with Uvicorn worker running on `127.0.0.1:8000`.
   - OCR Engine: PaddleOCR PP-OCRv4 (DBNet text detection + SVTR recognition) with MKLDNN CPU acceleration and multi-scale fine-print secondary extraction.
   - Multilingual PDF Engine: ReportLab with `fonts-noto-core` (`NotoSans-Regular.ttf`) supporting 10 Indian languages.
   - Reverse Proxy: Nginx listening on port 7860 (Hugging Face standard) reverse proxying `/api/` to `127.0.0.1:8000` with 300s timeout and buffering configurations.

2. **Frontend Delivery**:
   - Delivery Mode 1 (Primary / Unified): Nginx in the all-in-one container serves the compiled React 19 + TypeScript + Vite 8 static SPA directly on port 7860, routing `/api/` to FastAPI locally (same-origin, 0 CORS issues, 0 mixed content).
   - Delivery Mode 2 (Decoupled Edge CDN): Vercel Edge CDN deploying `frontend/` static assets, connecting dynamically to the Hugging Face Space via `VITE_API_URL=https://<space-name>.hf.space`.

3. **Data Persistence**:
   - Database: Async SQLite (`aiosqlite`) with WAL mode (`PRAGMA journal_mode=WAL;`), busy timeout 5000ms, and 18 isolated tables.
   - Storage Volume: Persistent storage directory `/data` (configured via `DATABASE_PATH=/data/metrcheck.db` and `UPLOAD_DIR=/data/uploads`).
   - Self-Healing Init: `init_db()` automatically provisions tables and seeds demo accounts if running on fresh ephemeral storage.

4. **Continuous Deployment**:
   - GitHub Repository: `https://github.com/omsainikaul/metrcheck-ai.git` on branch `main`.
   - CI Pipeline: GitHub Actions running `pytest backend/tests` (1,040 tests) and `npm run build` on every push and PR.
   - CD Sync: GitHub Actions git-sync workflow pushing directly to Hugging Face Spaces Git remote upon every merge to `main`.

---

## Code Layout
```
OMSAINI_FOLDER/
├── backend/                        # FastAPI Python 3.11 Backend
│   ├── auth/                       # JWT authentication, RBAC, tenant checks
│   ├── compliance/                 # Regulatory engines
│   │   ├── rules/                  # LM-001..LM-009, FS-001..FS-005 statutory rules
│   │   ├── engine.py               # Compliance orchestrator
│   │   ├── evidence_locator.py     # Defect bounding box & missing declaration locator
│   │   └── scoring.py              # Risk scoring & penalty calculations
│   ├── database/                   # aiosqlite connection, 18-table schema, WAL mode
│   ├── ocr/                        # PaddleOCR PP-OCRv4 engine & candidate refinement
│   ├── routers/                    # 20 FastAPI router endpoints (/api/*)
│   ├── services/                   # ReportLab PDF, integrity SHA-256, GS1/FSSAI decoders
│   ├── templates/                  # HTML report & email templates
│   ├── tests/                      # 95 test files (1,040 tests)
│   ├── config.py                   # Pydantic Settings & production secret validator
│   ├── main.py                     # App factory & router registration
│   └── requirements.txt            # Python dependencies
├── frontend/                       # React 19 + TS + Vite 8 Frontend
│   ├── src/
│   │   ├── components/             # EvidenceViewer (red boxes), Scorecard, Docket, etc.
│   │   ├── pages/                  # Analyze, Results, Dashboard, Admin, History
│   │   ├── services/               # api.ts (dynamic VITE_API_URL or relative /api)
│   │   └── types/                  # TypeScript interfaces
│   ├── package.json                # React 19, Tailwind CSS 4, Vite 8
│   ├── vite.config.ts              # Vite config with /api proxy
│   └── nginx.conf                  # Nginx reverse proxy configuration
├── Dockerfile                      # Production multi-stage Dockerfile (Nginx + Python 3.11)
├── docker-compose.yml              # Local / staging compose definition
├── .github/workflows/              # Automated CI/CD workflows
├── ORIGINAL_REQUEST.md             # Authoritative user requirements
├── PROJECT.md                      # Architecture, Feature Inventory & Milestones
├── TEST_INFRA.md                   # Opaque-box E2E test suite specification
└── README.md                       # Repository overview & Hugging Face metadata
```

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Repository & Dependency Audit | Verify git status, 1,040 tests passing, clean frontend build, and zero mocks | M1 | R1 |
| 2 | Statutory Rules Authenticity | 9 Legal Metrology rules (LM-001..LM-009) + 5 FSSAI rules (FS-001..FS-005) | M1 | R1 |
| 3 | PaddleOCR PP-OCRv4 Core | Deep learning DBNet text detection + SVTR recognition with multi-scale fine-print OCR | M2 | R2 |
| 4 | No-Tesseract Policy | Strictly enforce PaddleOCR as sole engine; confirm Tesseract exclusion | M2 | R2 |
| 5 | Indic Font Rendering | Debian `fonts-noto-core` for 10 Indic languages PDF generation | M2 | R2 |
| 6 | Container Hardening & Port 7860 | Multi-stage Dockerfile exposing port 7860 with non-root security & Nginx proxy | M2 | R2 |
| 7 | Production Security Validation | Validate `SECRET_KEY >= 32` chars, reject wildcards in `CORS_ORIGINS`, env vars | M2 | R2 |
| 8 | Health Check `/api/health` | HTTP 200 health check returning status, ocr_available, db, version | M2 | R2 |
| 9 | Dynamic API Decoupling | Frontend `api.ts` dynamic resolution via `VITE_API_URL` or relative `/api` | M3 | R3 |
| 10 | Clean Vite TS Compilation | `npm run build` with zero TypeScript errors into production bundles | M3 | R3 |
| 11 | Red Bounding Box Defect Visualizer | SVG overlay with `#red-glow` filter and `#ef4444` defect bounding boxes | M3 | R3 |
| 12 | Missing Declaration Projection | Projection frame on PDP/info panel when statutory declarations are absent | M3 | R3 |
| 13 | Compliance Scorecard & Docket | Risk levels, score /100, passed/needs review/failed cards, defect dockets | M3 | R3 |
| 14 | External Code Decoders | 14-digit FSSAI license parser and EAN-13 GS1 barcode country/checksum decoder | M3 | R3 |
| 15 | Multilingual Report Generation | ReportLab PDF (10 languages) & HTML compliance reports with SHA-256 hash | M3 | R3, R6 |
| 16 | Async SQLite WAL Persistence | `aiosqlite` with WAL mode, 18 tables, busy timeout 5000ms, tenant isolation | M4 | R4 |
| 17 | Cloud Volume Strategy | Persistent storage mapping for `/data/metrcheck.db` and `/data/uploads` | M4 | R4 |
| 18 | Hugging Face Spaces Deployment | 16GB RAM Docker deployment on HF Spaces (free tier, zero cost) | M5 | R5 |
| 19 | Vercel Edge CDN Deployment | Decoupled frontend hosting on Vercel Edge CDN with `VITE_API_URL` | M5 | R5 |
| 20 | GitHub Actions CI/CD Pipeline | Automated test execution and git-sync to Hugging Face Spaces on push to `main` | M5 | R5 |
| 21 | Real Commodity E2E Verification | Live testing with real commodity packaging (OCR, compliance, red boxes, PDF) | M6 | R6 |
| 22 | Operational Runbook | Complete runbook: live URLs, logs, updates, rollback, zero-laptop instructions | M6 | R6 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Repository & Codebase Audit Verification | Full audit of git repo, verify 1,040 passing tests, verify zero mocks in OCR & rules | none | DONE |
| M2 | Production Backend Containerization & OCR Hardening | Hardened Dockerfile (port 7860, fonts-noto-core, Python 3.11, Nginx), security env vars, health check | M1 | DONE |
| M3 | Production Frontend Build & Dynamic API Decoupling | Clean Vite build, dynamic API resolution via `VITE_API_URL`, verify UI visualizers & decoders | M1 | IN_PROGRESS |
| M4 | Database Persistence & Storage Architecture | Configure WAL mode cloud persistence, test data survival across restarts, multi-tenant isolation | M2 | PLANNED |
| M5 | Cloud Provider Architecture & Automated Git CI/CD | Set up Hugging Face Spaces Docker (16GB) + Vercel config, GitHub Actions CI & sync workflow | M2, M3, M4 | PLANNED |
| M6 | Live Production Verification & Operational Playbook | Live testing with real packaged commodity images, PDF/HTML generation, SHA-256 verification, runbook | M5 | PLANNED |

---

## Interface Contracts

### 1. Browser Frontend ↔ Backend API (`/api/*`)
- Health Check: `GET /api/health` -> `{"status": "healthy"|"ok", "ocr_available": true, "ocr_engine": "PaddleOCREngine", "database": "connected", "version": "2.4.0"}`
- Analyze Packaging: `POST /api/analyze` (multipart/form-data: images `front`, `back`, `side1`, `side2`, `product_name`, `category`) -> JSON `AnalysisResponse`
- Evidence Query: `GET /api/compliance/evidence/{analysis_id}` -> JSON `EvidenceResponse` containing bounding boxes `[ymin, xmin, ymax, xmax]` normalized to [0, 1000]
- Report Download: `GET /api/report/{analysis_id}?lang={lang}` -> `application/pdf` with `X-Report-SHA256` header
- Version Metadata: `GET /api/version` -> JSON `{"version": "2.4.0", "environment": "production", "git_commit": "..."}`

### 2. Nginx Reverse Proxy ↔ Uvicorn Backend
- Nginx listens on `0.0.0.0:7860` (Hugging Face default)
- Direct static file serving: `/usr/share/nginx/html` with `try_files $uri $uri/ /index.html`
- Upstream proxy: `/api/` -> `http://127.0.0.1:8000/api/` with `proxy_set_header Host $host`, `proxy_read_timeout 300s`, `client_max_body_size 50M`

### 3. GitHub Actions ↔ Hugging Face Spaces Git Remote
- CI Action: `pytest backend/tests` + `cd frontend && npm ci && npm run build`
- Deploy Sync: `git push https://omsainikaul:$HF_TOKEN@huggingface.co/spaces/omsainikaul/metrcheck-ai main:main --force`
