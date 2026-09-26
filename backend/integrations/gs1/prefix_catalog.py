"""
GS1 Country Prefix Catalog
Maps GS1 prefix ranges (first 2-3 digits of GTIN/EAN-13 barcodes) to the issuing
GS1 Member Organization and Country of Origin.
"""
from typing import Optional, Dict, Any, Tuple
import re

# Table of GS1 Prefix Ranges -> (Country Name, ISO Alpha-2/3 or notes)
GS1_PREFIX_TABLE = [
    # North America
    ((0, 139), "United States & Canada", "US/CA"),
    # France & Monaco
    ((300, 379), "France", "FR"),
    ((380, 380), "Bulgaria", "BG"),
    ((383, 383), "Slovenia", "SI"),
    ((385, 385), "Croatia", "HR"),
    ((387, 387), "Bosnia and Herzegovina", "BA"),
    ((389, 389), "Montenegro", "ME"),
    # Germany
    ((400, 440), "Germany", "DE"),
    # Japan
    ((450, 459), "Japan", "JP"),
    ((490, 499), "Japan", "JP"),
    # Russia & CIS
    ((460, 469), "Russia", "RU"),
    ((470, 470), "Kyrgyzstan", "KG"),
    ((471, 471), "Taiwan", "TW"),
    ((474, 474), "Estonia", "EE"),
    ((475, 475), "Latvia", "LV"),
    ((476, 476), "Azerbaijan", "AZ"),
    ((477, 477), "Lithuania", "LT"),
    ((478, 478), "Uzbekistan", "UZ"),
    ((479, 479), "Sri Lanka", "LK"),
    ((480, 480), "Philippines", "PH"),
    ((481, 481), "Belarus", "BY"),
    ((482, 482), "Ukraine", "UA"),
    ((484, 484), "Moldova", "MD"),
    ((485, 485), "Armenia", "AM"),
    ((486, 486), "Georgia", "GE"),
    ((487, 487), "Kazakhstan", "KZ"),
    ((488, 488), "Tajikistan", "TJ"),
    ((489, 489), "Hong Kong", "HK"),
    # UK & Europe
    ((500, 509), "United Kingdom", "GB"),
    ((520, 521), "Greece", "GR"),
    ((528, 528), "Lebanon", "LB"),
    ((529, 529), "Cyprus", "CY"),
    ((530, 530), "Albania", "AL"),
    ((531, 531), "North Macedonia", "MK"),
    ((535, 535), "Malta", "MT"),
    ((539, 539), "Ireland", "IE"),
    ((540, 549), "Belgium & Luxembourg", "BE/LU"),
    ((560, 560), "Portugal", "PT"),
    ((569, 569), "Iceland", "IS"),
    ((570, 579), "Denmark", "DK"),
    ((590, 590), "Poland", "PL"),
    ((594, 594), "Romania", "RO"),
    ((599, 599), "Hungary", "HU"),
    # Africa & Middle East
    ((600, 601), "South Africa", "ZA"),
    ((603, 603), "Ghana", "GH"),
    ((604, 604), "Senegal", "SN"),
    ((608, 608), "Bahrain", "BH"),
    ((609, 609), "Mauritius", "MU"),
    ((611, 611), "Morocco", "MA"),
    ((613, 613), "Algeria", "DZ"),
    ((615, 615), "Nigeria", "NG"),
    ((616, 616), "Kenya", "KE"),
    ((618, 618), "Ivory Coast", "CI"),
    ((619, 619), "Tunisia", "TN"),
    ((620, 620), "Tanzania", "TZ"),
    ((621, 621), "Syria", "SY"),
    ((622, 622), "Egypt", "EG"),
    ((624, 624), "Libya", "LY"),
    ((625, 625), "Jordan", "JO"),
    ((626, 626), "Iran", "IR"),
    ((627, 627), "Kuwait", "KW"),
    ((628, 628), "Saudi Arabia", "SA"),
    ((629, 629), "United Arab Emirates", "AE"),
    ((640, 649), "Finland", "FI"),
    # China
    ((690, 699), "China", "CN"),
    # Norway & Sweden
    ((700, 709), "Norway", "NO"),
    ((729, 729), "Israel", "IL"),
    ((730, 739), "Sweden", "SE"),
    # Latin America
    ((740, 740), "Guatemala", "GT"),
    ((741, 741), "El Salvador", "SV"),
    ((742, 742), "Honduras", "HN"),
    ((743, 743), "Nicaragua", "NI"),
    ((744, 744), "Costa Rica", "CR"),
    ((745, 745), "Panama", "PA"),
    ((746, 746), "Dominican Republic", "DO"),
    ((750, 750), "Mexico", "MX"),
    ((754, 755), "Canada", "CA"),
    ((759, 759), "Venezuela", "VE"),
    ((760, 769), "Switzerland & Liechtenstein", "CH/LI"),
    ((770, 771), "Colombia", "CO"),
    ((773, 773), "Uruguay", "UY"),
    ((775, 775), "Peru", "PE"),
    ((777, 777), "Bolivia", "BO"),
    ((778, 779), "Argentina", "AR"),
    ((780, 780), "Chile", "CL"),
    ((784, 784), "Paraguay", "PY"),
    ((786, 786), "Ecuador", "EC"),
    ((789, 790), "Brazil", "BR"),
    # Southern Europe
    ((800, 839), "Italy", "IT"),
    ((840, 849), "Spain", "ES"),
    ((850, 850), "Cuba", "CU"),
    ((858, 858), "Slovakia", "SK"),
    ((859, 859), "Czech Republic", "CZ"),
    ((860, 860), "Serbia", "RS"),
    ((865, 865), "Mongolia", "MN"),
    ((867, 867), "North Korea", "KP"),
    ((868, 869), "Turkey", "TR"),
    ((870, 879), "Netherlands", "NL"),
    ((880, 880), "South Korea", "KR"),
    ((884, 884), "Cambodia", "KH"),
    ((885, 885), "Thailand", "TH"),
    ((888, 888), "Singapore", "SG"),
    # India (GS1 India)
    ((890, 890), "India", "IN"),
    ((893, 893), "Vietnam", "VN"),
    ((896, 896), "Pakistan", "PK"),
    ((899, 899), "Indonesia", "ID"),
    # Austria
    ((900, 919), "Austria", "AT"),
    # Australia & New Zealand
    ((930, 939), "Australia", "AU"),
    ((940, 949), "New Zealand", "NZ"),
    ((955, 955), "Malaysia", "MY"),
    ((958, 958), "Macau", "MO"),
]


def decode_gs1_gtin(gtin: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Decodes the country of origin / issuing member organization from a GTIN barcode.
    Accepts GTIN-8, GTIN-12, GTIN-13, or GTIN-14 strings.
    Returns:
        {
            "prefix": "890",
            "country_name": "India",
            "country_code": "IN",
            "is_india": True,
            "gtin_type": "GTIN-13"
        }
    or None if unrecognized/invalid.
    """
    if not gtin:
        return None
    clean = re.sub(r'\D', '', str(gtin))
    if len(clean) not in (8, 12, 13, 14):
        return None

    gtin_type = f"GTIN-{len(clean)}"

    # Normalize to 13-digit representation for prefix matching
    # GTIN-14: strip leading indicator packaging digit
    # GTIN-12 (UPC-A): prefix with 0
    # GTIN-8: EAN-8 uses distinct prefix assignments or zero-padding
    if len(clean) == 14:
        norm_gtin = clean[1:]
    elif len(clean) == 12:
        norm_gtin = "0" + clean
    elif len(clean) == 8:
        # Check 2 or 3 digit prefix directly
        prefix_3 = int(clean[:3])
        for (start, end), country, code in GS1_PREFIX_TABLE:
            if start <= prefix_3 <= end:
                return {
                    "prefix": clean[:3],
                    "country_name": country,
                    "country_code": code,
                    "is_india": (clean[:3] == "890"),
                    "gtin_type": gtin_type,
                    "raw_gtin": clean
                }
        return None
    else:
        norm_gtin = clean

    prefix_3 = int(norm_gtin[:3])
    for (start, end), country, code in GS1_PREFIX_TABLE:
        if start <= prefix_3 <= end:
            return {
                "prefix": norm_gtin[:3],
                "country_name": country,
                "country_code": code,
                "is_india": (norm_gtin[:3] == "890"),
                "gtin_type": gtin_type,
                "raw_gtin": clean
            }

    return None
