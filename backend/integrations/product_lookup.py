import re
import logging
from typing import Optional, Dict, Any, List
import urllib.request
import json
from integrations.gs1.prefix_catalog import decode_gs1_gtin
from integrations.gs1.verifier import GS1BarcodeVerifier

logger = logging.getLogger(__name__)

class ProductLookupService:
    """
    Live Product Intelligence Service.
    Queries global open product databases (OpenFoodFacts, GS1 prefix catalog)
    to fetch verified statutory declarations, ingredients, nutrition, brand, and pack images
    given a GTIN / EAN barcode or QR code.
    """

    USER_AGENT = "MetrCheckAI-ComplianceEngine/2.4 (https://metrcheck-ai-d6cx.onrender.com; metrcheck@compliance.gov.in)"

    @classmethod
    def fetch_by_barcode(cls, barcode: str, timeout_sec: float = 6.0) -> Dict[str, Any]:
        clean_code = re.sub(r'\D', '', str(barcode or '')).strip()
        if not clean_code or len(clean_code) < 8:
            return {
                "found": False,
                "barcode": barcode,
                "message": "Invalid barcode format. Expected GTIN-8, GTIN-12, GTIN-13, or GTIN-14."
            }

        # 1. GS1 Checksum & Prefix Decoding
        is_valid_checksum = GS1BarcodeVerifier.validate_gtin_checksum(clean_code)
        origin_meta = decode_gs1_gtin(clean_code)
        country_name = origin_meta.get("country_name") if origin_meta else "Unknown"
        prefix = origin_meta.get("prefix") if origin_meta else ""

        result = {
            "found": False,
            "barcode": clean_code,
            "gtin_format": f"GTIN-{len(clean_code)}",
            "is_valid_checksum": is_valid_checksum,
            "origin_country": country_name,
            "gs1_prefix": prefix,
            "product_name": None,
            "brand": None,
            "net_quantity": None,
            "categories": [],
            "ingredients": None,
            "nutrition": {},
            "image_url": None,
            "fssai_license": None,
            "provider": "OpenFoodFacts Global Database",
            "message": "Product not found in open global registry."
        }

        # 2. Query OpenFoodFacts API
        urls = [
            f"https://world.openfoodfacts.org/api/v2/product/{clean_code}.json",
            f"https://in.openfoodfacts.org/api/v2/product/{clean_code}.json"
        ]

        for url in urls:
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": cls.USER_AGENT,
                        "Accept": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if resp.status == 200:
                        payload = json.loads(resp.read().decode("utf-8"))
                        status = payload.get("status")
                        if status == 1 and "product" in payload:
                            prod = payload["product"]
                            result["found"] = True
                            result["product_name"] = prod.get("product_name") or prod.get("product_name_en") or prod.get("generic_name")
                            result["brand"] = prod.get("brands") or prod.get("brand_owner")
                            result["net_quantity"] = prod.get("quantity")
                            result["image_url"] = prod.get("image_front_url") or prod.get("image_url")
                            result["ingredients"] = prod.get("ingredients_text") or prod.get("ingredients_text_en")
                            
                            cats = prod.get("categories") or ""
                            if cats:
                                result["categories"] = [c.strip() for c in cats.split(",") if c.strip()][:5]

                            # Extract nutrition facts
                            nutriments = prod.get("nutriments", {})
                            if nutriments:
                                result["nutrition"] = {
                                    "energy_kcal": nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal"),
                                    "proteins_g": nutriments.get("proteins_100g") or nutriments.get("proteins"),
                                    "carbohydrates_g": nutriments.get("carbohydrates_100g") or nutriments.get("carbohydrates"),
                                    "fat_g": nutriments.get("fat_100g") or nutriments.get("fat"),
                                    "sugars_g": nutriments.get("sugars_100g") or nutriments.get("sugars"),
                                    "sodium_mg": (nutriments.get("sodium_100g") or 0) * 1000 if "sodium_100g" in nutriments else None
                                }

                            # Search for potential FSSAI number in labels/tags
                            labels_text = " ".join([str(v) for v in [prod.get("labels"), prod.get("emb_codes"), prod.get("manufacturing_places")] if v])
                            fssai_m = re.search(r'\b([12]\d{13})\b', labels_text)
                            if fssai_m:
                                result["fssai_license"] = fssai_m.group(1)

                            result["message"] = f"Product successfully matched: {result['product_name'] or 'Packaged Commodity'}"
                            return result
            except Exception as e:
                logger.debug(f"OpenFoodFacts lookup failed for {url}: {e}")

        return result

product_lookup_service = ProductLookupService()
