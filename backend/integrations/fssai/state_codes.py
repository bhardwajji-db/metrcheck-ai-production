"""
FSSAI 14-Digit Licence Number State Code & Structure Catalog
Maps the 2-digit state code (digits 2-3 of the statutory 14-digit FSSAI licence)
to Indian States and Union Territories, alongside common abbreviations and major cities.
"""
from typing import Optional, Dict, Any, List
import re

# Indian Official 2-digit State & UT Codes (FSSAI / GST / ISO 3166-2:IN)
INDIA_FSSAI_STATE_CODES: Dict[str, Dict[str, Any]] = {
    "00": {
        "name": "Central Licensing Authority / Multi-State HQ",
        "abbr": "CENTRAL",
        "is_central": True,
        "cities": ["New Delhi", "Delhi", "HQ"]
    },
    "01": {
        "name": "Jammu and Kashmir",
        "abbr": "JK",
        "is_central": False,
        "cities": ["Srinagar", "Jammu", "Anantnag", "Baramulla"]
    },
    "02": {
        "name": "Himachal Pradesh",
        "abbr": "HP",
        "is_central": False,
        "cities": ["Shimla", "Dharamshala", "Solan", "Mandi", "Baddi"]
    },
    "03": {
        "name": "Punjab",
        "abbr": "PB",
        "is_central": False,
        "cities": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Mohali", "Bathinda"]
    },
    "04": {
        "name": "Chandigarh",
        "abbr": "CH",
        "is_central": False,
        "cities": ["Chandigarh"]
    },
    "05": {
        "name": "Uttarakhand",
        "abbr": "UK",
        "is_central": False,
        "cities": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rudrapur", "Pantnagar"]
    },
    "06": {
        "name": "Haryana",
        "abbr": "HR",
        "is_central": False,
        "cities": ["Gurugram", "Gurgaon", "Faridabad", "Panipat", "Ambala", "Karnal", "Sonipat", "Manesar"]
    },
    "07": {
        "name": "Delhi",
        "abbr": "DL",
        "is_central": False,
        "cities": ["Delhi", "New Delhi", "North Delhi", "South Delhi", "West Delhi", "East Delhi", "Dwarka"]
    },
    "08": {
        "name": "Rajasthan",
        "abbr": "RJ",
        "is_central": False,
        "cities": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Udaipur", "Ajmer", "Bhiwadi", "Alwar"]
    },
    "09": {
        "name": "Uttar Pradesh",
        "abbr": "UP",
        "is_central": False,
        "cities": ["Noida", "Greater Noida", "Ghaziabad", "Lucknow", "Kanpur", "Varanasi", "Agra", "Meerut", "Prayagraj", "Bareilly", "Aligarh", "Moradabad", "Gorakhpur", "Mathura"]
    },
    "10": {
        "name": "Bihar",
        "abbr": "BR",
        "is_central": False,
        "cities": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga"]
    },
    "11": {
        "name": "Sikkim",
        "abbr": "SK",
        "is_central": False,
        "cities": ["Gangtok", "Namchi", "Gyalshing"]
    },
    "12": {
        "name": "Arunachal Pradesh",
        "abbr": "AR",
        "is_central": False,
        "cities": ["Itanagar", "Naharlagun", "Pasighat"]
    },
    "13": {
        "name": "Nagaland",
        "abbr": "NL",
        "is_central": False,
        "cities": ["Kohima", "Dimapur", "Mokokchung"]
    },
    "14": {
        "name": "Manipur",
        "abbr": "MN",
        "is_central": False,
        "cities": ["Imphal", "Churachandpur", "Thoubal"]
    },
    "15": {
        "name": "Mizoram",
        "abbr": "MZ",
        "is_central": False,
        "cities": ["Aizawl", "Lunglei", "Champhai"]
    },
    "16": {
        "name": "Tripura",
        "abbr": "TR",
        "is_central": False,
        "cities": ["Agartala", "Udaipur", "Dharmanagar"]
    },
    "17": {
        "name": "Meghalaya",
        "abbr": "ML",
        "is_central": False,
        "cities": ["Shillong", "Tura", "Jowai"]
    },
    "18": {
        "name": "Assam",
        "abbr": "AS",
        "is_central": False,
        "cities": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia"]
    },
    "19": {
        "name": "West Bengal",
        "abbr": "WB",
        "is_central": False,
        "cities": ["Kolkata", "Howrah", "Asansol", "Siliguri", "Durgapur", "Bardhaman", "Kharagpur"]
    },
    "20": {
        "name": "Jharkhand",
        "abbr": "JH",
        "is_central": False,
        "cities": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar", "Hazaribagh"]
    },
    "21": {
        "name": "Odisha",
        "abbr": "OD",
        "is_central": False,
        "cities": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri"]
    },
    "22": {
        "name": "Chhattisgarh",
        "abbr": "CG",
        "is_central": False,
        "cities": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Rajnandgaon", "Durg"]
    },
    "23": {
        "name": "Madhya Pradesh",
        "abbr": "MP",
        "is_central": False,
        "cities": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Dewas", "Pithampur"]
    },
    "24": {
        "name": "Gujarat",
        "abbr": "GJ",
        "is_central": False,
        "cities": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar", "Anand", "Vapi", "Bharuch"]
    },
    "25": {
        "name": "Daman and Diu",
        "abbr": "DD",
        "is_central": False,
        "cities": ["Daman", "Diu"]
    },
    "26": {
        "name": "Dadra and Nagar Haveli",
        "abbr": "DN",
        "is_central": False,
        "cities": ["Silvassa"]
    },
    "27": {
        "name": "Maharashtra",
        "abbr": "MH",
        "is_central": False,
        "cities": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Aurangabad", "Chhatrapati Sambhajinagar", "Solapur", "Navi Mumbai", "Bhiwandi", "Kolhapur", "Tarapur"]
    },
    "28": {
        "name": "Andhra Pradesh",
        "abbr": "AP",
        "is_central": False,
        "cities": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Tirupati", "Kakinada"]
    },
    "29": {
        "name": "Karnataka",
        "abbr": "KA",
        "is_central": False,
        "cities": ["Bengaluru", "Bangalore", "Mysuru", "Mysore", "Hubballi", "Mangaluru", "Mangalore", "Belagavi", "Davangere", "Ballari"]
    },
    "30": {
        "name": "Goa",
        "abbr": "GA",
        "is_central": False,
        "cities": ["Panaji", "Margao", "Vasco da Gama", "Mapusa"]
    },
    "31": {
        "name": "Lakshadweep",
        "abbr": "LD",
        "is_central": False,
        "cities": ["Kavaratti"]
    },
    "32": {
        "name": "Kerala",
        "abbr": "KL",
        "is_central": False,
        "cities": ["Thiruvananthapuram", "Kochi", "Cochin", "Kozhikode", "Calicut", "Thrissur", "Kollam", "Palakkad", "Alappuzha", "Kannur"]
    },
    "33": {
        "name": "Tamil Nadu",
        "abbr": "TN",
        "is_central": False,
        "cities": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Erode", "Vellore", "Hosur"]
    },
    "34": {
        "name": "Puducherry",
        "abbr": "PY",
        "is_central": False,
        "cities": ["Puducherry", "Pondicherry", "Karaikal", "Mahe", "Yanam"]
    },
    "35": {
        "name": "Andaman and Nicobar Islands",
        "abbr": "AN",
        "is_central": False,
        "cities": ["Port Blair"]
    },
    "36": {
        "name": "Telangana",
        "abbr": "TG",
        "is_central": False,
        "cities": ["Hyderabad", "Warangal", "Nizamabad", "Khammam", "Karimnagar", "Secunderabad"]
    },
    "37": {
        "name": "Ladakh",
        "abbr": "LA",
        "is_central": False,
        "cities": ["Leh", "Kargil"]
    },
    "99": {
        "name": "Central Licensing Authority",
        "abbr": "CENTRAL",
        "is_central": True,
        "cities": ["New Delhi", "Delhi"]
    }
}


def decode_fssai_licence(licence_number: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Decodes the statutory structure of a 14-digit FSSAI FoSCoS licence number:
    - Digit 1: Licence Category (1 = State/Central Licence, 2 = Registration)
    - Digits 2-3: State / UT Code (00-37, 99)
    - Digits 4-5: Year of Registration (e.g. '24' -> '2024')
    - Digits 6-8: Enrolling Authority / Kind of Business
    - Digits 9-14: Serial Number
    """
    if not licence_number:
        return None
    clean = re.sub(r'\D', '', str(licence_number))
    if len(clean) != 14:
        return None
    if clean[0] not in ('1', '2'):
        return None

    cat_digit = clean[0]
    lic_type = "Central/State License" if cat_digit == '1' else "FSSAI Registration"
    state_code = clean[1:3]
    year_digits = clean[3:5]
    reg_year = f"20{year_digits}" if int(year_digits) < 80 else f"19{year_digits}"

    state_info = INDIA_FSSAI_STATE_CODES.get(state_code, {
        "name": f"State Code {state_code}",
        "abbr": state_code,
        "is_central": False,
        "cities": []
    })

    return {
        "licence_number": clean,
        "license_type": lic_type,
        "is_registration": (cat_digit == '2'),
        "state_code": state_code,
        "state_name": state_info["name"],
        "state_abbr": state_info["abbr"],
        "is_central_license": state_info.get("is_central", False),
        "registration_year": reg_year,
        "state_cities": state_info.get("cities", []),
        "summary": f"{state_info['name']} ({lic_type}, {reg_year})"
    }
