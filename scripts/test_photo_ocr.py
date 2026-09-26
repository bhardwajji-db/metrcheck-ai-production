import asyncio
import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(str(BACKEND))

from ocr.paddle_engine import PaddleOCREngine
from extraction.extractor import LocalExtractor
from compliance.engine import ComplianceEngine
from models.schemas import ProductImageEvidence

async def test_single_photo(image_path: str, title: str):
    print("\n" + "=" * 78)
    print(f" TESTING PHOTO: {os.path.basename(image_path)} — {title}")
    print("=" * 78)

    if not os.path.exists(image_path):
        print(f"[!] File not found: {image_path}")
        return

    # 1. OCR Engine
    print("\n[1] Running PaddleOCR (PP-OCRv4) text detection & recognition...")
    engine = PaddleOCREngine()
    ocr_result = await engine.extract(image_path)
    
    print(f"  * Engine:             {ocr_result.engine}")
    print(f"  * Words Detected:     {len(ocr_result.words)}")
    print(f"  * Average Confidence: {ocr_result.average_confidence:.2f}%")
    print(f"  * Total Characters:   {len(ocr_result.full_text)}")
    print(f"\n  [OCR Detected Lines Sample (First 10 lines)]:")
    for line in ocr_result.full_text.splitlines()[:10]:
        if line.strip():
            print(f"    | {line.strip()}")

    # 2. Extract statutory details
    print("\n[2] Extracting Packaging Attributes via NLP / Regex Extractor...")
    extractor = LocalExtractor()
    extracted_data = extractor.extract(ocr_result.full_text, ocr_data=ocr_result.words)
    
    d = extracted_data.model_dump() if hasattr(extracted_data, 'model_dump') else extracted_data.dict()
    print("\n  [Extracted Packaging Declarations]:")
    fields_to_show = [
        ("Product Name", d.get("product_name")),
        ("MRP / Retail Price", d.get("mrp")),
        ("Net Quantity", d.get("net_quantity")),
        ("Unit Sale Price (USP)", d.get("unit_sale_price")),
        ("Mfg / Pkd Date", d.get("mfg_date")),
        ("Expiry / Best Before", d.get("expiry_date") or d.get("best_before")),
        ("Manufacturer", d.get("manufacturer_name")),
        ("Address / Location", d.get("manufacturer_address")),
        ("Consumer Care Phone", d.get("consumer_care_phone")),
        ("Consumer Care Email", d.get("consumer_care_email")),
        ("Country of Origin", d.get("country_of_origin")),
        ("FSSAI License No", d.get("fssai_license_number")),
    ]
    for label, val in fields_to_show:
        status = "[DETECTED]" if val else "[NOT FOUND]"
        print(f"    {status:<14} {label:<24}: {val}")

    # 3. Compliance Engine Evaluation
    print("\n[3] Evaluating Statutory Legal Metrology Rules...")
    compliance_engine = ComplianceEngine()
    panel_evidence = [ProductImageEvidence(label="Back", words=ocr_result.words)]
    check_result = compliance_engine.check(
        product_info=extracted_data,
        ocr_text=ocr_result.full_text,
        images=panel_evidence
    )

    score = check_result.get("score", 0)
    passed_count = check_result.get("passed_count", 0)
    failed_count = check_result.get("failed_count", 0)
    warning_count = check_result.get("warning_count", 0)
    
    print(f"\n  [Compliance Scoring]:")
    print(f"    Compliance Score : {score} / 100")
    print(f"    Passed Rules     : {passed_count}")
    print(f"    Failed Rules     : {failed_count}")
    print(f"    Warning Rules    : {warning_count}")

    print(f"\n  [Evaluated Rule Checks Sample]:")
    checks = check_result.get("checks", [])
    for c in checks[:10]:
        c_id = getattr(c, 'rule_id', '')
        c_label = getattr(c, 'field_label', '')
        c_status = getattr(c, 'status', '')
        c_val = getattr(c, 'detected_value', '')
        print(f"    [{c_status:<8}] {c_id:<8} ({c_label}): {c_val or 'Not Detected'}")

async def main():
    fixtures_dir = BACKEND / "fixtures"
    
    # 1. Alpino Peanut Butter Back Label
    alpino_back = fixtures_dir / "alpino_back.png"
    if alpino_back.exists():
        await test_single_photo(str(alpino_back), "Alpino Peanut Butter (Back Label)")

    # 2. Lay's Potato Chips Back Label
    lays_back = fixtures_dir / "lays_back.jpeg"
    if lays_back.exists():
        await test_single_photo(str(lays_back), "Lay's Potato Chips (Back Label)")

if __name__ == "__main__":
    asyncio.run(main())
