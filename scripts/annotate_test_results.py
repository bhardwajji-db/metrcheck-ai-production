import asyncio
import os
import sys
import shutil
import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(str(BACKEND))

from ocr.paddle_engine import PaddleOCREngine
from extraction.extractor import LocalExtractor
from compliance.engine import ComplianceEngine
from models.schemas import ProductImageEvidence

ARTIFACT_DIR = Path(r"C:\Users\Avinash\.gemini\antigravity-cli\brain\65cd071c-2ba3-4c81-8631-c13c31bd6924")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

def annotate_image(image_path: str, words, key_matches, output_path: str):
    img = cv2.imread(image_path)
    if img is None:
        return
    overlay = img.copy()

    # Colors (BGR)
    COLORS = {
        "NET_QUANTITY": (0, 200, 0),       # Green
        "CONSUMER_CARE": (220, 100, 0),    # Blue/Cyan
        "MANUFACTURER": (0, 140, 255),     # Orange
        "FSSAI": (180, 0, 180),            # Purple
        "PRODUCT_NAME": (0, 215, 255),     # Yellow
        "DEFAULT": (120, 120, 120)         # Gray
    }

    # Draw semi-transparent boxes
    for match in key_matches:
        bbox = match["bbox"]
        cat = match.get("category", "DEFAULT")
        color = COLORS.get(cat, (0, 255, 0))
        x1, y1, x2, y2 = bbox
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        
        # Label badge
        label = match["label"]
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(img, (x1, max(0, y1 - lh - 6)), (x1 + lw + 6, y1), color, -1)
        cv2.putText(img, label, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # Blend overlay
    cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)
    cv2.imwrite(output_path, img)
    print(f"[+] Saved annotated visualization: {output_path}")

async def process(image_path: str, orig_name: str, annot_name: str):
    src = Path(image_path)
    orig_dest = ARTIFACT_DIR / orig_name
    annot_dest = ARTIFACT_DIR / annot_name
    shutil.copyfile(src, orig_dest)
    print(f"[+] Copied original to: {orig_dest}")

    engine = PaddleOCREngine()
    ocr_result = await engine.extract(str(src))

    extractor = LocalExtractor()
    extracted = extractor.extract(ocr_result.full_text, ocr_data=ocr_result.words)

    # Find bounding boxes for key extracted terms
    key_matches = []
    
    def find_words_matching(keywords, label, category):
        for w in ocr_result.words:
            w_lower = w.text.lower()
            for kw in keywords:
                if kw.lower() in w_lower and len(kw) > 2:
                    if w.bbox and len(w.bbox) == 4:
                        key_matches.append({
                            "bbox": w.bbox,
                            "label": label,
                            "category": category,
                            "text": w.text
                        })
                    break

    # Net Quantity
    find_words_matching(["143g", "143 g", "400g", "400 g", "quantity", "weight"], "Net Qty", "NET_QUANTITY")
    # Customer Care
    find_words_matching(["1800224020", "8347688000", "feedback", "alpino.co.in", "pepsico.com", "care", "toll"], "Customer Care", "CONSUMER_CARE")
    # Manufacturer
    find_words_matching(["pepsico", "gurugram", "haryana", "alpino", "mfg", "marketed"], "Mfr / Packer", "MANUFACTURER")
    # FSSAI
    find_words_matching(["10014064000435", "10716022000249", "fssai", "lic"], "FSSAI Lic", "FSSAI")
    # Product
    find_words_matching(["potatochips", "oats", "chips", "peanut"], "Product", "PRODUCT_NAME")

    annotate_image(str(src), ocr_result.words, key_matches, str(annot_dest))
    return {
        "words_count": len(ocr_result.words),
        "confidence": ocr_result.average_confidence,
        "extracted": extracted.model_dump() if hasattr(extracted, 'model_dump') else extracted.dict()
    }

async def main():
    fixtures = BACKEND / "fixtures"
    lays = fixtures / "lays_back.jpeg"
    alpino = fixtures / "alpino_back.png"

    print("Annotating Lay's Potato Chips...")
    lays_res = await process(str(lays), "lays_original.jpg", "lays_annotated.jpg")

    print("Annotating Alpino Peanut Butter...")
    alpino_res = await process(str(alpino), "alpino_original.png", "alpino_annotated.png")

    print("\nAnnotation complete!")

if __name__ == "__main__":
    asyncio.run(main())
