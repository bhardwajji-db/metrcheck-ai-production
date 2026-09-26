"""
Universal Indian Postal PIN Code Intelligence Engine
Extracts and decodes the 6-digit Indian PIN code from any manufacturer, packer,
or importer address on any packaged product (Food, Electronics, Cosmetics, FMCG).
Maps PIN prefixes to State, Union Territory, Postal Circle, and prominent cities/districts.
"""
from typing import Optional, Dict, Any, List
import re

# 3-digit and 2-digit PIN prefix mapping to State & Major Region
PIN_PREFIX_MAP: Dict[str, Dict[str, str]] = {
    # Delhi
    "11": {"state": "Delhi", "state_code": "07", "region": "Delhi NCR / Capital Region"},
    
    # Haryana
    "121": {"state": "Haryana", "state_code": "06", "region": "Faridabad"},
    "122": {"state": "Haryana", "state_code": "06", "region": "Gurugram / Gurgaon / Manesar"},
    "124": {"state": "Haryana", "state_code": "06", "region": "Rohtak"},
    "131": {"state": "Haryana", "state_code": "06", "region": "Sonipat / Kundli"},
    "132": {"state": "Haryana", "state_code": "06", "region": "Panipat / Karnal"},
    "133": {"state": "Haryana", "state_code": "06", "region": "Ambala"},
    "134": {"state": "Haryana", "state_code": "06", "region": "Panchkula"},
    "12": {"state": "Haryana", "state_code": "06", "region": "Haryana"},
    "13": {"state": "Haryana", "state_code": "06", "region": "Haryana"},
    
    # Punjab & Chandigarh
    "160": {"state": "Chandigarh", "state_code": "04", "region": "Chandigarh"},
    "141": {"state": "Punjab", "state_code": "03", "region": "Ludhiana"},
    "143": {"state": "Punjab", "state_code": "03", "region": "Amritsar"},
    "144": {"state": "Punjab", "state_code": "03", "region": "Jalandhar"},
    "147": {"state": "Punjab", "state_code": "03", "region": "Patiala"},
    "16": {"state": "Chandigarh", "state_code": "04", "region": "Chandigarh / Mohali Circle"},
    "14": {"state": "Punjab", "state_code": "03", "region": "Punjab"},
    "15": {"state": "Punjab", "state_code": "03", "region": "Punjab"},

    # Himachal Pradesh
    "171": {"state": "Himachal Pradesh", "state_code": "02", "region": "Shimla"},
    "173": {"state": "Himachal Pradesh", "state_code": "02", "region": "Solan / Baddi Industrial Area"},
    "17": {"state": "Himachal Pradesh", "state_code": "02", "region": "Himachal Pradesh"},

    # Jammu & Kashmir and Ladakh
    "180": {"state": "Jammu and Kashmir", "state_code": "01", "region": "Jammu"},
    "190": {"state": "Jammu and Kashmir", "state_code": "01", "region": "Srinagar"},
    "194": {"state": "Ladakh", "state_code": "37", "region": "Leh / Ladakh"},
    "18": {"state": "Jammu and Kashmir", "state_code": "01", "region": "Jammu & Kashmir"},
    "19": {"state": "Jammu and Kashmir", "state_code": "01", "region": "Jammu & Kashmir"},

    # Uttar Pradesh & Uttarakhand
    "201": {"state": "Uttar Pradesh", "state_code": "09", "region": "Noida / Greater Noida / Ghaziabad"},
    "202": {"state": "Uttar Pradesh", "state_code": "09", "region": "Aligarh"},
    "203": {"state": "Uttar Pradesh", "state_code": "09", "region": "Bulandshahr"},
    "208": {"state": "Uttar Pradesh", "state_code": "09", "region": "Kanpur Nagar"},
    "209": {"state": "Uttar Pradesh", "state_code": "09", "region": "Kanpur Dehat"},
    "210": {"state": "Uttar Pradesh", "state_code": "09", "region": "Banda / Chitrakoot"},
    "211": {"state": "Uttar Pradesh", "state_code": "09", "region": "Prayagraj / Allahabad"},
    "221": {"state": "Uttar Pradesh", "state_code": "09", "region": "Varanasi"},
    "226": {"state": "Uttar Pradesh", "state_code": "09", "region": "Lucknow"},
    "243": {"state": "Uttar Pradesh", "state_code": "09", "region": "Bareilly"},
    "244": {"state": "Uttar Pradesh", "state_code": "09", "region": "Moradabad"},
    "248": {"state": "Uttarakhand", "state_code": "05", "region": "Dehradun"},
    "249": {"state": "Uttarakhand", "state_code": "05", "region": "Haridwar / Rishikesh"},
    "250": {"state": "Uttar Pradesh", "state_code": "09", "region": "Meerut"},
    "263": {"state": "Uttarakhand", "state_code": "05", "region": "Nainital / Haldwani / Rudrapur"},
    "281": {"state": "Uttar Pradesh", "state_code": "09", "region": "Mathura"},
    "282": {"state": "Uttar Pradesh", "state_code": "09", "region": "Agra"},
    "20": {"state": "Uttar Pradesh", "state_code": "09", "region": "Western Uttar Pradesh"},
    "21": {"state": "Uttar Pradesh", "state_code": "09", "region": "Uttar Pradesh (Prayagraj Zone)"},
    "22": {"state": "Uttar Pradesh", "state_code": "09", "region": "Central Uttar Pradesh (Lucknow Zone)"},
    "23": {"state": "Uttar Pradesh", "state_code": "09", "region": "Uttar Pradesh"},
    "24": {"state": "Uttar Pradesh", "state_code": "09", "region": "Uttar Pradesh / Uttarakhand (Bareilly Zone)"},
    "25": {"state": "Uttar Pradesh", "state_code": "09", "region": "Uttar Pradesh (Meerut Zone)"},
    "26": {"state": "Uttarakhand", "state_code": "05", "region": "Uttarakhand (Kumaon Zone)"},
    "27": {"state": "Uttar Pradesh", "state_code": "09", "region": "Uttar Pradesh (Gorakhpur Zone)"},
    "28": {"state": "Uttar Pradesh", "state_code": "09", "region": "Uttar Pradesh (Agra / Jhansi Zone)"},

    # Rajasthan
    "301": {"state": "Rajasthan", "state_code": "08", "region": "Alwar / Bhiwadi Industrial Area"},
    "302": {"state": "Rajasthan", "state_code": "08", "region": "Jaipur"},
    "313": {"state": "Rajasthan", "state_code": "08", "region": "Udaipur"},
    "324": {"state": "Rajasthan", "state_code": "08", "region": "Kota"},
    "342": {"state": "Rajasthan", "state_code": "08", "region": "Jodhpur"},
    "30": {"state": "Rajasthan", "state_code": "08", "region": "Rajasthan (Jaipur Zone)"},
    "31": {"state": "Rajasthan", "state_code": "08", "region": "Rajasthan (Udaipur Zone)"},
    "32": {"state": "Rajasthan", "state_code": "08", "region": "Rajasthan (Kota Zone)"},
    "33": {"state": "Rajasthan", "state_code": "08", "region": "Rajasthan (Bikaner Zone)"},
    "34": {"state": "Rajasthan", "state_code": "08", "region": "Rajasthan (Jodhpur Zone)"},

    # Gujarat & Daman/Diu/Dadra
    "380": {"state": "Gujarat", "state_code": "24", "region": "Ahmedabad"},
    "382": {"state": "Gujarat", "state_code": "24", "region": "Gandhinagar / Sanand"},
    "388": {"state": "Gujarat", "state_code": "24", "region": "Anand"},
    "390": {"state": "Gujarat", "state_code": "24", "region": "Vadodara"},
    "392": {"state": "Gujarat", "state_code": "24", "region": "Bharuch / Ankleshwar"},
    "395": {"state": "Gujarat", "state_code": "24", "region": "Surat"},
    "396": {"state": "Gujarat", "state_code": "24", "region": "Vapi / Valsad / Daman / Silvassa"},
    "360": {"state": "Gujarat", "state_code": "24", "region": "Rajkot"},
    "36": {"state": "Gujarat", "state_code": "24", "region": "Gujarat (Saurashtra Zone)"},
    "37": {"state": "Gujarat", "state_code": "24", "region": "Gujarat (Kutch Zone)"},
    "38": {"state": "Gujarat", "state_code": "24", "region": "Gujarat (Ahmedabad Zone)"},
    "39": {"state": "Gujarat", "state_code": "24", "region": "Gujarat (South Gujarat / Vadodara / Surat Zone)"},

    # Maharashtra & Goa
    "400": {"state": "Maharashtra", "state_code": "27", "region": "Mumbai / Navi Mumbai"},
    "401": {"state": "Maharashtra", "state_code": "27", "region": "Thane / Palghar / Tarapur Industrial Area"},
    "403": {"state": "Goa", "state_code": "30", "region": "Goa (Panaji / Margao)"},
    "411": {"state": "Maharashtra", "state_code": "27", "region": "Pune / Pimpri-Chinchwad"},
    "421": {"state": "Maharashtra", "state_code": "27", "region": "Thane / Bhiwandi / Kalyan"},
    "422": {"state": "Maharashtra", "state_code": "27", "region": "Nashik"},
    "431": {"state": "Maharashtra", "state_code": "27", "region": "Chhatrapati Sambhajinagar / Aurangabad"},
    "440": {"state": "Maharashtra", "state_code": "27", "region": "Nagpur"},
    "40": {"state": "Maharashtra", "state_code": "27", "region": "Maharashtra (Mumbai Metropolitan Region)"},
    "41": {"state": "Maharashtra", "state_code": "27", "region": "Maharashtra (Pune Zone)"},
    "42": {"state": "Maharashtra", "state_code": "27", "region": "Maharashtra (Nashik Zone)"},
    "43": {"state": "Maharashtra", "state_code": "27", "region": "Maharashtra (Marathwada Zone)"},
    "44": {"state": "Maharashtra", "state_code": "27", "region": "Maharashtra (Vidarbha Zone)"},

    # Madhya Pradesh & Chhattisgarh
    "452": {"state": "Madhya Pradesh", "state_code": "23", "region": "Indore / Pithampur"},
    "462": {"state": "Madhya Pradesh", "state_code": "23", "region": "Bhopal"},
    "482": {"state": "Madhya Pradesh", "state_code": "23", "region": "Jabalpur"},
    "490": {"state": "Chhattisgarh", "state_code": "22", "region": "Bhilai / Durg"},
    "492": {"state": "Chhattisgarh", "state_code": "22", "region": "Raipur"},
    "45": {"state": "Madhya Pradesh", "state_code": "23", "region": "Madhya Pradesh (Indore Zone)"},
    "46": {"state": "Madhya Pradesh", "state_code": "23", "region": "Madhya Pradesh (Bhopal Zone)"},
    "47": {"state": "Madhya Pradesh", "state_code": "23", "region": "Madhya Pradesh (Gwalior Zone)"},
    "48": {"state": "Madhya Pradesh", "state_code": "23", "region": "Madhya Pradesh (Jabalpur Zone)"},
    "49": {"state": "Chhattisgarh", "state_code": "22", "region": "Chhattisgarh"},

    # Andhra Pradesh & Telangana
    "500": {"state": "Telangana", "state_code": "36", "region": "Hyderabad / Secunderabad"},
    "50": {"state": "Telangana", "state_code": "36", "region": "Telangana (Hyderabad Zone)"},
    "51": {"state": "Andhra Pradesh", "state_code": "28", "region": "Andhra Pradesh (Rayalaseema Zone)"},
    "52": {"state": "Andhra Pradesh", "state_code": "28", "region": "Andhra Pradesh (Vijayawada Zone)"},
    "53": {"state": "Andhra Pradesh", "state_code": "28", "region": "Andhra Pradesh (Visakhapatnam Zone)"},

    # Karnataka
    "560": {"state": "Karnataka", "state_code": "29", "region": "Bengaluru (Bangalore) Urban"},
    "562": {"state": "Karnataka", "state_code": "29", "region": "Bengaluru Rural / Hoskote"},
    "570": {"state": "Karnataka", "state_code": "29", "region": "Mysuru (Mysore)"},
    "575": {"state": "Karnataka", "state_code": "29", "region": "Mangaluru (Mangalore)"},
    "580": {"state": "Karnataka", "state_code": "29", "region": "Hubballi / Dharwad"},
    "56": {"state": "Karnataka", "state_code": "29", "region": "Karnataka (Bengaluru Zone)"},
    "57": {"state": "Karnataka", "state_code": "29", "region": "Karnataka (Mysuru / Mangaluru Zone)"},
    "58": {"state": "Karnataka", "state_code": "29", "region": "Karnataka (North Karnataka Zone)"},
    "59": {"state": "Karnataka", "state_code": "29", "region": "Karnataka (Belagavi Zone)"},

    # Tamil Nadu & Puducherry
    "600": {"state": "Tamil Nadu", "state_code": "33", "region": "Chennai"},
    "605": {"state": "Puducherry", "state_code": "34", "region": "Puducherry (Pondicherry)"},
    "635": {"state": "Tamil Nadu", "state_code": "33", "region": "Hosur / Krishnagiri Industrial Zone"},
    "641": {"state": "Tamil Nadu", "state_code": "33", "region": "Coimbatore"},
    "625": {"state": "Tamil Nadu", "state_code": "33", "region": "Madurai"},
    "60": {"state": "Tamil Nadu", "state_code": "33", "region": "Tamil Nadu (Chennai Zone)"},
    "61": {"state": "Tamil Nadu", "state_code": "33", "region": "Tamil Nadu (Tiruchirappalli Zone)"},
    "62": {"state": "Tamil Nadu", "state_code": "33", "region": "Tamil Nadu (Madurai Zone)"},
    "63": {"state": "Tamil Nadu", "state_code": "33", "region": "Tamil Nadu (Salem / Hosur Zone)"},
    "64": {"state": "Tamil Nadu", "state_code": "33", "region": "Tamil Nadu (Coimbatore Zone)"},

    # Kerala & Lakshadweep
    "682": {"state": "Kerala", "state_code": "32", "region": "Kochi / Ernakulam"},
    "695": {"state": "Kerala", "state_code": "32", "region": "Thiruvananthapuram"},
    "68": {"state": "Kerala", "state_code": "32", "region": "Kerala (Kochi / Central Zone)"},
    "69": {"state": "Kerala", "state_code": "32", "region": "Kerala (Thiruvananthapuram Zone)"},
    "67": {"state": "Kerala", "state_code": "32", "region": "Kerala (Kozhikode / Malabar Zone)"},

    # West Bengal, Sikkim & Andaman
    "700": {"state": "West Bengal", "state_code": "19", "region": "Kolkata"},
    "711": {"state": "West Bengal", "state_code": "19", "region": "Howrah"},
    "734": {"state": "West Bengal", "state_code": "19", "region": "Siliguri / Darjeeling"},
    "737": {"state": "Sikkim", "state_code": "11", "region": "Sikkim (Gangtok)"},
    "744": {"state": "Andaman and Nicobar Islands", "state_code": "35", "region": "Port Blair / Andaman"},
    "70": {"state": "West Bengal", "state_code": "19", "region": "West Bengal (Kolkata Metropolitan)"},
    "71": {"state": "West Bengal", "state_code": "19", "region": "West Bengal (Burdwan Zone)"},
    "72": {"state": "West Bengal", "state_code": "19", "region": "West Bengal (Midnapore Zone)"},
    "73": {"state": "West Bengal", "state_code": "19", "region": "West Bengal (North Bengal Zone)"},
    "74": {"state": "West Bengal", "state_code": "19", "region": "West Bengal (Nadia Zone)"},

    # Odisha
    "751": {"state": "Odisha", "state_code": "21", "region": "Bhubaneswar"},
    "753": {"state": "Odisha", "state_code": "21", "region": "Cuttack"},
    "769": {"state": "Odisha", "state_code": "21", "region": "Rourkela"},
    "75": {"state": "Odisha", "state_code": "21", "region": "Odisha (Bhubaneswar Zone)"},
    "76": {"state": "Odisha", "state_code": "21", "region": "Odisha (Berhampur Zone)"},
    "77": {"state": "Odisha", "state_code": "21", "region": "Odisha (Sambalpur Zone)"},

    # North Eastern States
    "781": {"state": "Assam", "state_code": "18", "region": "Guwahati"},
    "78": {"state": "Assam", "state_code": "18", "region": "Assam"},
    "793": {"state": "Meghalaya", "state_code": "17", "region": "Shillong"},
    "795": {"state": "Manipur", "state_code": "14", "region": "Imphal"},
    "796": {"state": "Mizoram", "state_code": "15", "region": "Aizawl"},
    "797": {"state": "Nagaland", "state_code": "13", "region": "Kohima / Dimapur"},
    "799": {"state": "Tripura", "state_code": "16", "region": "Agartala"},
    "791": {"state": "Arunachal Pradesh", "state_code": "12", "region": "Itanagar"},
    "79": {"state": "North Eastern Region", "state_code": "", "region": "North East India"},

    # Bihar & Jharkhand
    "800": {"state": "Bihar", "state_code": "10", "region": "Patna"},
    "834": {"state": "Jharkhand", "state_code": "20", "region": "Ranchi"},
    "831": {"state": "Jharkhand", "state_code": "20", "region": "Jamshedpur"},
    "826": {"state": "Jharkhand", "state_code": "20", "region": "Dhanbad"},
    "80": {"state": "Bihar", "state_code": "10", "region": "Bihar (Patna Zone)"},
    "81": {"state": "Bihar", "state_code": "10", "region": "Bihar (Bhagalpur Zone)"},
    "82": {"state": "Jharkhand", "state_code": "20", "region": "Jharkhand (Dhanbad Zone)"},
    "83": {"state": "Jharkhand", "state_code": "20", "region": "Jharkhand (Ranchi Zone)"},
    "84": {"state": "Bihar", "state_code": "10", "region": "Bihar (Muzaffarpur Zone)"},
    "85": {"state": "Bihar", "state_code": "10", "region": "Bihar (Purnia Zone)"}
}


def extract_pin_codes(text: Optional[str]) -> List[str]:
    """
    Extracts candidate 6-digit Indian PIN codes from address text.
    Valid Indian PIN codes start with digits 1-8 and have length 6.
    Avoids 10-digit phone numbers and 14-digit FSSAI licenses.
    """
    if not text:
        return []
    # Match 6-digit number that starts with 1-8 with boundaries or PIN: prefix
    # Exclude numbers flanked by digits
    matches = re.findall(r'(?:PIN|PINCODE|PIN\s*CODE)?[\s.:\-]*\b([1-8]\d{5})\b', text, re.IGNORECASE)
    # Filter out false positives (e.g. repeated numbers or dates)
    valid_pins = []
    for pin in matches:
        if len(pin) == 6 and pin[0] in "12345678":
            if pin not in valid_pins:
                valid_pins.append(pin)
    return valid_pins


def decode_pin_code(pin_or_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Decodes a 6-digit PIN code or searches for a PIN code within an address string.
    Returns:
        {
            "pin_code": "201301",
            "state_name": "Uttar Pradesh",
            "state_code": "09",
            "region": "Noida / Greater Noida / Ghaziabad",
            "country": "India",
            "summary": "Noida / Greater Noida / Ghaziabad, Uttar Pradesh (PIN 201301)"
        }
    """
    if not pin_or_text:
        return None

    # Check if direct 6-digit pin was supplied
    clean_digits = re.sub(r'\D', '', str(pin_or_text).strip())
    pin = clean_digits if len(clean_digits) == 6 and clean_digits[0] in "12345678" else None

    if not pin:
        candidates = extract_pin_codes(str(pin_or_text))
        pin = candidates[0] if candidates else None

    if not pin:
        return None

    # Try 3-digit prefix first for high-resolution region, then 2-digit prefix
    prefix_3 = pin[:3]
    prefix_2 = pin[:2]

    geo_data = PIN_PREFIX_MAP.get(prefix_3) or PIN_PREFIX_MAP.get(prefix_2)
    if not geo_data:
        return {
            "pin_code": pin,
            "state_name": "India (Postal Circle)",
            "state_code": "",
            "region": "Indian Postal Region",
            "country": "India",
            "summary": f"India (PIN {pin})"
        }

    return {
        "pin_code": pin,
        "state_name": geo_data["state"],
        "state_code": geo_data.get("state_code", ""),
        "region": geo_data["region"],
        "country": "India",
        "summary": f"{geo_data['region']}, {geo_data['state']} (PIN {pin})"
    }
