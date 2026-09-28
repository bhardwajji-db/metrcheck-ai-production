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

## Follow-up — 2026-09-28T05:58:24Z

Optimize OCR inference latency and fix statutory field extraction inaccuracies in the MetrCheck AI regulatory compliance screening system on production cloud (512MB RAM, 0.1 vCPU) and local environments without mocks or regressions.

Working directory: c:\Users\Avinash\OneDrive\Desktop\OMSAINI_FOLDER
Integrity mode: development

## Requirements

### R1. OCR Latency Optimization & Elimination of Unnecessary Fallback Passes
In `backend/ocr/paddle_engine.py`:
- Remove the premature fallback trigger `len(words1) < 8` that falsely labels clean, sparse front-panel packaging images (e.g. snack packets with 4-6 prominent words like 'FAMILY PACK TakaTak CHATPATA MASALA') as degraded and launches a second 1.35x upscaled OCR pass. Only invoke full-image fallback if `len(words1) == 0`.
- Enable batched crop recognition (`batch_sampler.batch_size = 4` or `8` and chunk size 8) in PaddleX's SVTR model so that multi-box back panels (40+ crops) are evaluated in batched C++ predictor tensors instead of sequential single-crop Python loops.
- Skip secondary targeted region OCR when Pass 1 already extracts valid tokens (`len(words1) >= 6`), reducing per-image processing time from 40s+ down to ~10-15s.

### R2. Statutory Extraction Accuracy & Nutrition Leakage Prevention
In `backend/extraction/extractor.py`:
- **Net Quantity**: Prevent nutrition table facts (e.g. `Protein ... 17.0g`, `Carbohydrate ... 65g`, `Fat ... 25g`, `per 100g`, `per serve`) from ever being misidentified as Net Quantity. If statutory anchors (`Net Wt`, `Net Quantity`) are absent or unstamped, do not grab arbitrary standalone numbers from adjacent nutrition lines.
- **Product Name Synthesis**: Fuse prominent front-panel sub-brand and commodity words (e.g. `TakaTak` + `Chatpata Masala`) into the true product title (`TakaTak Chatpata Masala`) rather than truncating to only the commodity suffix (`Chatpata Masala`).
- **Brand Name Prioritization**: Prevent generic corporate manufacturer suffixes (`ITC Limited` -> `Itc`, `Hindustan Unilever` -> `Hindustan Unilever`) from overriding the actual packaging brand (`Bingo`, `Kissan`, `Haldiram's`) detected on the front panel.
- **Batch Number Sanitization**: Filter out statutory keywords like `BEST`, `EXP`, `MFG`, `DATE`, `USE`, `BEFORE` from being extracted as batch numbers.
- **FSSAI License Substring Recovery**: Extract 14-digit numeric license patterns even when prepended or joined with OCR noise artifacts (e.g. `RODUA100405100910` -> `10014051000910`).
- **Manufacturer Entity Isolation**: Strip customer care headers (`THE CONSUMER SERVICE MANAGER`, `FOR FEEDBACK`, `flavour`) from company entity strings so clean manufacturer names and addresses are extracted.

### R3. Local & Real Image Verification
Verify extraction against real user test images in `c:\Users\Avinash\Downloads\`:
- `taka taak front.jpg` and `takataak back.webp` (Haldiram's TakaTak Chatpata Masala)
- Real packaging test cases (Kissan Tomato Ketchup, Tata Salt, Kurkure)
Ensure extracted fields match ground truth and zero crashes or regressions occur in existing test suites (`pytest backend/tests`).

### R4. Production Deployment & Live Verification
Commit and push all fixes to production git remote (`https://github.com/bhardwajji-db/metrcheck-ai-production.git` on branch `main`).
Poll Render deployment API until the build is live, and execute live end-to-end API tests on `https://metrcheck-ai-d6cx.onrender.com/api/analyze` to confirm response times under 35 seconds and accurate field extraction.

## Acceptance Criteria

### Automated Verification
- [ ] Pytest test suite passes without regressions (`pytest backend/tests`).
- [ ] Single-image and multi-image local OCR benchmarks demonstrate >= 2.5x speed improvement without degraded word recall.
- [ ] Extraction unit tests confirm:
  - Net Quantity excludes nutrition facts (e.g., Protein 17.0g).
  - TakaTak front + back extracts `Product Name: TakaTak Chatpata Masala`.
  - Batch number rejects `BEST`.
  - FSSAI license extracts valid 14 digits from noisy strings.

### Cloud Deployment & Live Functionality
- [ ] Deployment builds cleanly on Render and transitions to `Status: live`.
- [ ] Live API test on `https://metrcheck-ai-d6cx.onrender.com/api/analyze` completes in under 35 seconds for multi-panel images.
- [ ] Live analysis response returns accurate product name, net quantity, brand, and legal metrology rule evaluations.
