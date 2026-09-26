# E2E Test Infra: MetrCheck AI Cloud Deployment

## Test Philosophy
- Opaque-box, requirement-driven, zero dependency on internal implementation designs.
- Validates the complete deployment via HTTP/HTTPS endpoints and browser interfaces without relying on local machine processes.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial + Real-World Workload Testing.

---

## Feature Inventory & Test Matrix
| # | Feature | Requirement Source | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|-------------------|:------:|:------:|:------:|:------:|
| 1 | Health Check (`/api/health`) | R2 | 5 | 5 | ✓ | ✓ |
| 2 | Production Config & Secrets | R2 | 5 | 5 | ✓ | ✓ |
| 3 | Clean Frontend Bundle & Routing | R3 | 5 | 5 | ✓ | ✓ |
| 4 | Dynamic API Decoupling | R3 | 5 | 5 | ✓ | ✓ |
| 5 | Packaging Image Upload (Multi-view) | R3, R6 | 5 | 5 | ✓ | ✓ |
| 6 | PaddleOCR PP-OCRv4 Text Extraction | R1, R2, R6 | 5 | 5 | ✓ | ✓ |
| 7 | Legal Metrology Rules (LM-001..LM-009) | R1, R6 | 5 | 5 | ✓ | ✓ |
| 8 | FSSAI Compliance Rules (FS-001..FS-005) | R1, R6 | 5 | 5 | ✓ | ✓ |
| 9 | Red Bounding Box Defect Visualizer | R1, R3, R6 | 5 | 5 | ✓ | ✓ |
| 10 | Statutory Missing Declaration Projection | R1, R3, R6 | 5 | 5 | ✓ | ✓ |
| 11 | Compliance Scorecard & Metric Docket | R1, R3, R6 | 5 | 5 | ✓ | ✓ |
| 12 | GS1 EAN-13 & FSSAI Code Decoding | R1, R3, R6 | 5 | 5 | ✓ | ✓ |
| 13 | Multilingual ReportLab PDF Generation | R1, R2, R6 | 5 | 5 | ✓ | ✓ |
| 14 | SHA-256 Tamper-Evident Report Hashing | R1, R4, R6 | 5 | 5 | ✓ | ✓ |
| 15 | SQLite WAL Mode & Data Persistence | R4 | 5 | 5 | ✓ | ✓ |
| 16 | Multi-Tenant Data Isolation | R4 | 5 | 5 | ✓ | ✓ |
| 17 | Cloud Container Port 7860 Routing | R2, R5 | 5 | 5 | ✓ | ✓ |
| 18 | Automated Git CI/CD Redeployment | R5 | 5 | 5 | ✓ | ✓ |

---

## Test Architecture
- **Opaque-Box E2E Runner**: Python `requests` & `httpx` script exercising public endpoints (`/api/health`, `/api/analyze`, `/api/report/{id}`, `/api/version`, `/api/compliance/evidence/{id}`).
- **Test File**: `tests/e2e/test_cloud_production_e2e.py`
- **Pass/Fail Semantics**: HTTP status codes, JSON schema validation, SVG/coordinate bounds validation, PDF binary signature (`%PDF-`) and SHA-256 integrity verification.

---

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: >= 5 tests per feature (Happy-path tests verifying each feature in isolation).
- **Tier 2 (Boundary & Corner Cases)**: >= 5 tests per feature (Empty payloads, invalid images, oversized files, missing mandatory fields, boundary dimensions, malformed FSSAI numbers).
- **Tier 3 (Cross-Feature Combinations)**: Pairwise interactions (e.g. food product with GS1 barcode + missing expiry + Hindi PDF report; non-food product with high-contrast packaging + English PDF report).
- **Tier 4 (Real-World Application Scenarios)**:
  1. *FMCG Packaged Biscuit*: Real 4-panel image pack with MRP, Net Qty, FSSAI license, and ingredients.
  2. *Packaged Spice / Condiment*: Real dual-panel image with vegetarian logo, batch number, customer care details, and best before date.
  3. *Imported Cosmetic / Personal Care*: Non-food packaged commodity testing Legal Metrology LM-001..LM-009 while skipping FSSAI.
  4. *Defective Packaged Snack*: Real image deliberately missing statutory declaration (triggering red bounding box defect docket + missing declaration projection).
  5. *Multi-Tenant Concurrent Audit*: Simultaneous submissions from separate tenants validating strict data and audit isolation.
