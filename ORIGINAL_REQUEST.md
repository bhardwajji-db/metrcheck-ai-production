# Original User Request

## Initial Request — 2026-09-26T18:37:29Z

Deploy the complete MetrCheck AI regulatory compliance screening and visual audit system from the existing Git repository to a production-ready, 100% cloud-hosted architecture with zero laptop dependencies, zero mocked data, and zero monthly hosting cost on legitimate free tiers.

Working directory: c:\Users\Avinash\OneDrive\Desktop\OMSAINI_FOLDER
Integrity mode: development

## Requirements

### R1. Repository & Deployment Audit
Audit the existing Git repository (https://github.com/omsainikaul/metrcheck-ai.git), verify all backend routes, test suites (1,048 passing tests), frontend Vite configuration, Dockerfiles, and environment variable requirements. Ensure no existing OCR logic, compliance rules, defect red boxes, or multilingual report generators are altered or replaced with mocks.

### R2. Production Backend Containerization & OCR Execution
Prepare and harden the FastAPI backend container for production cloud execution with Python 3.11, OpenCV headless, PaddleOCR PP-OCRv4, Tesseract OCR fallback, and ReportLab. Ensure the runtime allocates sufficient memory (~1GB+) without crashing, passes backend health checks (/api/health), handles secure CORS origins via environment variables, validates 32+ character production SECRET_KEY, and avoids hard-coded localhost or laptop IPs.

### R3. Production Frontend Build & Dynamic API Decoupling
Ensure the React + TypeScript + Vite frontend builds with zero TypeScript errors and dynamically resolves the production backend API via VITE_API_URL (or relative /api behind reverse proxy). Verify that browser HTTPS calls cleanly reach the backend without mixed-content or CORS blocking.

### R4. Database Persistence & Storage Architecture
Preserve the existing async SQLite database schema, WAL mode, migrations, and tenant isolation tables using persistent cloud storage volumes (or equivalent cloud persistence) so compliance history, preprints, user accounts, and audit records persist indefinitely without laptop reliance.

### R5. Cloud Provider Architecture & Automated Git CI/CD
Deploy the system to a viable, verified free-tier cloud architecture (recommended: Hugging Face Spaces 16GB RAM Docker for ML backend/all-in-one container + Vercel for frontend edge CDN) connected directly to main branch of https://github.com/omsainikaul/metrcheck-ai.git. Enable automated rebuild and redeployment on git push. Provide exact environment variable configurations and document any external dashboard authorization steps required by the user.

### R6. Live Production Verification & Operational Playbook
Verify live deployed URLs using real packaged commodity images. Confirm OCR text extraction, red bounding box defect visualizer, missing declaration projection, PDF/HTML report generation, GS1 barcode and FSSAI license decoding, SHA-256 audit hashing, and persistent storage. Produce an operational runbook detailing live URLs, log inspection, update workflows, and rollback procedures.

## Acceptance Criteria

### Automated Verification
- [ ] Backend test suite passes without regressions (pytest backend/tests).
- [ ] Frontend builds cleanly with zero TypeScript errors (npm run build).
- [ ] Docker container builds and starts cleanly with production health check returning HTTP 200 {"status": "ok"} on /api/health.
- [ ] Production environment variables (SECRET_KEY, CORS_ORIGINS, ENVIRONMENT=production, UPLOAD_DIR, DATABASE_PATH) validate without throwing startup security errors.

### Cloud Deployment & Live Functionality
- [ ] The application is accessible on a public, valid HTTPS URL without requiring any local processes on the user's laptop.
- [ ] Uploading a real packaged commodity image via the production frontend successfully triggers OCR, returns real Legal Metrology and FSSAI compliance evaluations, and renders red bounding box evidence.
- [ ] Downloadable PDF and HTML compliance reports are generated with valid SHA-256 integrity hashes.
- [ ] Data created during audit runs persists across container restarts.
- [ ] Pushing commits to GitHub automatically triggers a cloud rebuild and redeploy.
