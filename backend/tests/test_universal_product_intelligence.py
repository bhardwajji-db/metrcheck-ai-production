"""
Unit and Integration Tests for Universal Multi-Product Intelligence:
1. GS1 Barcode Country of Origin Decoding (India '890', US, China, Germany, etc.)
2. FSSAI 14-Digit State, Category, and Year Decoding ('09' -> Uttar Pradesh, '27' -> Maharashtra)
3. Universal Indian Postal PIN Code Location Engine ('201301' -> Noida, UP, '560001' -> Bengaluru, KA)
4. Extraction Engine Integration (populating decoded state, origin, PIN, and sector licenses)
5. Cross-Checking Intelligence:
   - FSSAI State <-> Manufacturer Address consistency
   - Barcode Country <-> Declared Country of Origin consistency
   - Postal PIN <-> Address Location consistency
"""
import pytest
from integrations.gs1.prefix_catalog import decode_gs1_gtin
from integrations.fssai.state_codes import decode_fssai_licence
from integrations.postal.pin_decoder import decode_pin_code, extract_pin_codes
from integrations.fssai.verifier import fssai_verifier
from integrations.gs1.verifier import gs1_verifier
from integrations.cross_checker import cross_check_engine, CrossCheckStatus
from extraction.extractor import extractor


# ── 1. GS1 Barcode Prefix Decoding ──────────────────────────────────────────

def test_gs1_barcode_india_prefix_decoding():
    # Standard Indian EAN-13 barcode starting with 890
    res = decode_gs1_gtin("8901030383458")
    assert res is not None
    assert res["is_india"] is True
    assert res["country_name"] == "India"
    assert res["prefix"] == "890"
    assert res["gtin_type"] == "GTIN-13"


def test_gs1_barcode_international_prefixes():
    # US / Canada prefix (e.g. 012...)
    us_res = decode_gs1_gtin("012345678905")
    assert us_res is not None
    assert "United States" in us_res["country_name"]
    assert us_res["is_india"] is False

    # China prefix (690...)
    cn_res = decode_gs1_gtin("6901234567895")
    assert cn_res is not None
    assert cn_res["country_name"] == "China"
    assert cn_res["is_india"] is False

    # Germany prefix (400...)
    de_res = decode_gs1_gtin("4001234567890")
    assert de_res is not None
    assert de_res["country_name"] == "Germany"


# ── 2. FSSAI Licence State & Structure Decoding ─────────────────────────────

def test_fssai_state_code_uttar_pradesh():
    # FSSAI starting with 109... -> Category 1 (License), State 09 (Uttar Pradesh), Year 24 (2024)
    lic = "10924011000123"
    res = decode_fssai_licence(lic)
    assert res is not None
    assert res["state_name"] == "Uttar Pradesh"
    assert res["state_code"] == "09"
    assert res["state_abbr"] == "UP"
    assert res["license_type"] == "Central/State License"
    assert res["registration_year"] == "2024"
    assert "Noida" in res["state_cities"]


def test_fssai_state_code_maharashtra_and_delhi():
    # Maharashtra: State code 27, Registration category 2, Year 22 (2022)
    res_mh = decode_fssai_licence("22722001000456")
    assert res_mh is not None
    assert res_mh["state_name"] == "Maharashtra"
    assert res_mh["state_code"] == "27"
    assert res_mh["state_abbr"] == "MH"
    assert res_mh["is_registration"] is True
    assert res_mh["registration_year"] == "2022"

    # Delhi: State code 07
    res_dl = decode_fssai_licence("10721011000789")
    assert res_dl is not None
    assert res_dl["state_name"] == "Delhi"
    assert res_dl["state_code"] == "07"


def test_fssai_central_license():
    # Central License: State code 00 or 99
    res_cen = decode_fssai_licence("10020011000123")
    assert res_cen is not None
    assert res_cen["is_central_license"] is True


# ── 3. Universal Indian Postal PIN Code Location Engine ─────────────────────

def test_postal_pin_decoding_uttar_pradesh():
    # Noida PIN 201301
    res = decode_pin_code("201301")
    assert res is not None
    assert res["state_name"] == "Uttar Pradesh"
    assert res["state_code"] == "09"
    assert "Noida" in res["region"]

    # Extract from full address text
    addr = "Manufactured by ABC Pvt Ltd, Sector 62, Noida, Gautam Buddha Nagar, PIN - 201309, India"
    extracted = decode_pin_code(addr)
    assert extracted is not None
    assert extracted["pin_code"] == "201309"
    assert extracted["state_name"] == "Uttar Pradesh"


def test_postal_pin_decoding_karnataka_and_maharashtra():
    # Bengaluru PIN 560001
    res_ka = decode_pin_code("560001")
    assert res_ka is not None
    assert res_ka["state_name"] == "Karnataka"
    assert "Bengaluru" in res_ka["region"]

    # Mumbai PIN 400001
    res_mh = decode_pin_code("400001")
    assert res_mh is not None
    assert res_mh["state_name"] == "Maharashtra"
    assert "Mumbai" in res_mh["region"]


# ── 4. End-to-End Extraction Enrichment ─────────────────────────────────────

def test_extractor_enriches_origin_and_state():
    sample_label = """
    NutriBite Protein Cookies 200g
    MRP Rs. 149.00
    Net Wt: 200 g
    Pkd Date: 15/01/2026
    Batch No: NB-2026-X
    Manufactured by: Healthy Foods India Pvt Ltd
    Plot 14, Sector 63, Noida, UP - 201301
    FSSAI Lic. No. 10924011000123
    EAN-13: 8901030383458
    Customer Care: care@healthyfoods.in
    """
    prod_info = extractor.extract(sample_label)

    # 1. Barcode decoded to India
    assert prod_info.barcode_detected == "8901030383458"
    assert prod_info.barcode_origin_country == "India"
    assert prod_info.barcode_prefix == "890"

    # 2. Country of Origin inferred from barcode since label text omitted explicit "Country of Origin: ..."
    assert prod_info.country_of_origin == "India"

    # 3. FSSAI state decoded to Uttar Pradesh
    assert prod_info.fssai_license == "10924011000123"
    assert prod_info.fssai_decoded_state == "Uttar Pradesh"
    assert prod_info.fssai_license_type == "Central/State License"
    assert prod_info.fssai_registration_year == "2024"

    # 4. Postal PIN decoded to Noida, Uttar Pradesh
    assert prod_info.address_pin_code == "201301"
    assert prod_info.address_decoded_state == "Uttar Pradesh"


# ── 5. Cross-Check Consistency Evaluation ───────────────────────────────────

@pytest.mark.asyncio
async def test_cross_checks_state_and_origin_matches():
    fssai_rec = await fssai_verifier.verify("10924011000123")
    assert fssai_rec.decoded_state == "Uttar Pradesh"

    gs1_rec = await gs1_verifier.verify("8901030383458")
    assert gs1_rec.origin_country == "India"

    # Test State Match
    st_check = cross_check_engine.check_fssai_state_consistency(
        fssai_record=fssai_rec,
        extracted_address="Sector 62, Noida, Uttar Pradesh 201301",
        address_decoded_state="Uttar Pradesh"
    )
    assert st_check.status == CrossCheckStatus.MATCH
    assert "aligns" in st_check.discrepancy_details

    # Test State Mismatch (UP License on Maharashtra Address)
    st_mismatch = cross_check_engine.check_fssai_state_consistency(
        fssai_record=fssai_rec,
        extracted_address="MIDC Industrial Area, Andheri East, Mumbai, Maharashtra 400093",
        address_decoded_state="Maharashtra"
    )
    assert st_mismatch.status == CrossCheckStatus.MISMATCH
    assert st_mismatch.is_critical_mismatch is True
    assert "Location Discrepancy" in st_mismatch.discrepancy_details

    # Test Origin Country Match
    orig_check = cross_check_engine.check_barcode_origin_consistency(
        gs1_record=gs1_rec,
        extracted_country="India"
    )
    assert orig_check.status == CrossCheckStatus.MATCH

    # Test Origin Country Mismatch
    orig_mismatch = cross_check_engine.check_barcode_origin_consistency(
        gs1_record=gs1_rec,
        extracted_country="Made in Germany"
    )
    assert orig_mismatch.status == CrossCheckStatus.MISMATCH
    assert orig_mismatch.is_critical_mismatch is True
