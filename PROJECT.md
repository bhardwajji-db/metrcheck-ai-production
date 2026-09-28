# Project: MetrCheck AI Optimization & Production Deployment

## Architecture
- `backend/ocr/`: Multi-scale PaddleOCR + Tesseract fallback engine.
- `backend/extraction/`: Statutory Legal Metrology & FSSAI declaration extractor, regex repair heuristics, and brand/product name synthesis.
- `backend/tests/`: Pytest suite with 96 test files, temporary database session isolation, and physical packaging test fixtures.
- Cloud / Production: GitHub remote `https://github.com/bhardwajji-db/metrcheck-ai-production.git` (branch `main`), Render Docker service hosting FastAPI + headless OpenCV + PaddleOCR + Vite React frontend.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | OCR Fallback Trigger Elimination | Eliminate len(words1) < 8 fallback trigger; only fallback if len(words1) == 0 | M1 | ORIGINAL_REQUEST R1 |
| 2 | Secondary Targeted OCR Bypass | Skip secondary region pass when len(words1) >= 6 or clean front panel | M1 | ORIGINAL_REQUEST R1 |
| 3 | SVTR Batched Crop Recognition | Enable batch_sampler.batch_size = 8 and CHUNK_SIZE = 8 with hasattr guard | M1 | ORIGINAL_REQUEST R1 |
| 4 | Net Quantity Nutrition Exclusion | Mask nutrition blocks, require strict Net anchors, exclude Protein/Carb/Fat facts | M2 | ORIGINAL_REQUEST R2 |
| 5 | Product Name Synthesis | Fuse front-panel sub-brand (TakaTak) with commodity suffix (Chatpata Masala) | M2 | ORIGINAL_REQUEST R2 |
| 6 | Brand Name Prioritization | Prioritize front-panel logo over back-panel corporate/trademark owner clauses | M2 | ORIGINAL_REQUEST R2 |
| 7 | Batch Number Sanitization | Filter statutory keywords (BEST, EXP, MFG, DATE, USE, BEFORE) from batch numbers | M2 | ORIGINAL_REQUEST R2 |
| 8 | FSSAI Substring Recovery | Extract 14 digits from fused noise (RODUA10014051000910 -> 10014051000910) | M2 | ORIGINAL_REQUEST R2 |
| 9 | Manufacturer Entity Isolation | Strip consumer care headers (CONSUMER SERVICE MANAGER, FOR FEEDBACK) | M2 | ORIGINAL_REQUEST R2 |
| 10 | Local Packaging Benchmark | Run benchmarks on TakaTak, Kissan, Tata Salt; confirm >= 2.5x speedup | M3 | ORIGINAL_REQUEST R3 |
| 11 | Zero Pytest Regressions | Verify all 1,040+ tests in backend/tests pass cleanly | M3 | ORIGINAL_REQUEST R3 |
| 12 | Git Production Push | Push commits to bhardwajji-db/metrcheck-ai-production.git on main branch | M4 | ORIGINAL_REQUEST R4 |
| 13 | Render Cloud Deployment | Poll Render deployment status until live | M4 | ORIGINAL_REQUEST R4 |
| 14 | Live API SLA Verification | Verify https://metrcheck-ai-d6cx.onrender.com/api/analyze < 35s latency & fields | M4 | ORIGINAL_REQUEST R4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: OCR Latency Optimization | backend/ocr/paddle_engine.py | none | DONE |
| 2 | M2: Statutory Extraction Accuracy | backend/extraction/extractor.py, patterns.py, backend/ocr/repair.py | none | IN_PROGRESS |
| 3 | M3: Local Benchmark & Image Verification | backend/tests/ | M1, M2 | PLANNED |
| 4 | M4: Production Deployment & Live Verification | Git remote, Render cloud deployment, Live API | M1, M2, M3 | PLANNED |

## Interface Contracts
### OCR Engine (`paddle_engine.py`) ↔ Extraction Engine (`extractor.py`)
- Function: `PaddleOCREngine.extract_text_multiscale(image_path: str, lang: str)`
- Output: `tuple[list[str], list[str], list[float], int]` -> `(lines, words, confidences, pass_count)`
- Contract: Word bounding boxes, word strings, and reading-order line grouping must preserve original spatial coordinates and case sensitivity.

### Extraction Engine (`extractor.py`) ↔ Compliance Pipeline & API (`api/routes/analyze.py`)
- Function: `extract_all(ocr_result: dict, image_shape: tuple)`
- Output: `dict` containing statutory keys: `net_quantity`, `product_name`, `brand`, `batch_number`, `fssai_license`, `manufacturer_name`, `manufacturer_address`.
- Contract: Missing or non-statutory declarations must return `None` or `NOT_FOUND`, never misclassifying nutrition facts as net weight.

## Code Layout
- `backend/ocr/paddle_engine.py`: Multi-scale OCR inference engine. Owned exclusively by M1 Worker.
- `backend/extraction/extractor.py`: Statutory rule extraction & NLP parser. Owned exclusively by M2 Worker.
- `backend/extraction/patterns.py`: Regular expression patterns for Indian packaging. Owned exclusively by M2 Worker.
- `backend/ocr/repair.py`: Text sanitization and repair heuristics. Owned exclusively by M2 Worker.
- `backend/tests/`: Pytest regression and packaging verification suite. Owned exclusively by M3 Worker.
- `render.yaml`, `Dockerfile`: Deployment configuration.
