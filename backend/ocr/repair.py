import re
from typing import Optional

def repair_fssai_license(text: str) -> Optional[str]:
    """
    High-recall contextual FSSAI licence repair.
    Searches for clean or slightly OCR-corrupted 14-digit sequences.
    Performs OCR character substitution: 'O'/'o'->0, 'l'/'I'->1, 'S'->5, 'B'->8, 'Z'/'z'->2.
    Uses non-digit lookarounds (?<!\d)([12]\d{13})(?!\d) to recover 14 digits
    even when prepended or joined with OCR noise artifacts (e.g. RODUA10014051000910).
    """
    if not text:
        return None

    # 1. First check for 14-digit sequence bounded by non-digits
    m = re.search(r'(?<!\d)([12]\d{13})(?!\d)', text)
    if m:
        return m.group(1)

    # 2. Contextual search near FSSAI / Lic No / Licence No
    ctx_match = re.search(r'(?:FSSAI|FSBAI|FOSSA|Lic\.?\s*(?:No\.?|Number)?|Licence\s*No\.?)[\s.:\-=]*([A-Za-z0-9\s\-]{13,25})', text, re.IGNORECASE)
    if ctx_match:
        cand = re.sub(r'[^0-9OlISBGzZ]', '', ctx_match.group(1)).translate(str.maketrans('OlISBGzZ', '01158622'))
        m_cand = re.search(r'(?<!\d)([12]\d{13})(?!\d)', cand)
        if m_cand:
            return m_cand.group(1)

    # 3. Check standalone candidates with character substitutions bounded by non-alphanumerics
    candidates = re.finditer(r'(?<![0-9OlISBGzZ])([12][0-9OlISBGzZ\s\-]{13,20})(?![0-9OlISBGzZ])', text)
    for cm in candidates:
        cand = cm.group(1)
        repaired = re.sub(r'[\s\-]', '', cand).translate(str.maketrans('OlISBGzZ', '01158622'))
        m_rep = re.search(r'(?<!\d)([12]\d{13})(?!\d)', repaired)
        if m_rep:
            return m_rep.group(1)

    return None

STATUTORY_BATCH_REJECT_TERMS = {
    'BEST', 'BEFORE', 'EXP', 'EXPIRY', 'EXP_DATE', 'MFG', 'MFD', 'PKD', 'PACKED',
    'DATE', 'DATES', 'DT', 'USE', 'BY', 'USEBY', 'USE_BY', 'BESTBEFORE',
    'LOT', 'BATCH', 'BN', 'BNO', 'MRP', 'RS', 'INR', 'USP', 'NET', 'WT',
    'QTY', 'WEIGHT', 'QUANTITY', 'MONTHS', 'YEARS', 'DAYS', 'FROM', 'INCL',
    'TAXES', 'ALL', 'SEE', 'BELOW', 'BOTTOM', 'OF', 'PACK', 'PANEL', 'FLAP',
    'PRINTED', 'SIDE', 'CONTAINER', 'STAMP', 'CAP', 'NECK', 'CRIMP', 'POUCH',
    'LABEL', 'JAR', 'CAN', 'BOX', 'TOP', 'REFER', 'DETAILS', 'THE', 'AT',
    'OFPACK', 'PACKAGE', 'BASE', 'UNDER', 'OVER', 'REVERSE', 'PLEASE',
    'PACKAGING', 'MANUFACTURE', 'CONSUME', 'PRICE', 'TAX', 'CONSUMER',
    'CARE', 'MANAGER', 'SERVICE', 'CUSTOMER', 'FEEDBACK'
}

INSTRUCTION_TERMS = {
    'PLEASE', 'SEE', 'BOTTOM', 'OF', 'PACK', 'BELOW', 'CONTAINER', 'STAMP',
    'PRINTED', 'SIDE', 'CAP', 'NECK', 'CRIMP', 'POUCH', 'LABEL', 'JAR', 'CAN',
    'BOX', 'TOP', 'DATE', 'FOR', 'AND', 'REFER', 'DETAILS', 'THE', 'AT',
    'OFPACK', 'PACKAGE', 'PANEL', 'FLAP', 'BASE', 'UNDER', 'OVER', 'REVERSE',
    'BEST', 'BEFORE', 'USE', 'EXPIRY', 'EXP', 'MFG', 'MFD', 'PKD', 'PACKED',
    'MONTHS', 'YEARS', 'DAYS', 'FROM', 'PACKAGING', 'MANUFACTURE', 'CONSUME',
    'PRICE', 'TAXES', 'INCL', 'ALL', 'TAX', 'MRP', 'RS', 'INR', 'NET', 'WEIGHT', 'QTY',
    'CONSUMER', 'CARE', 'MANAGER', 'SERVICE', 'CUSTOMER', 'FEEDBACK'
}

def repair_net_quantity(val: str) -> str:
    """
    Contextual Net Quantity repair.
    Fixes common OCR digit/letter confusions (e.g., '400 9' -> '400 g', 'g435g' -> '435 g').
    Standardizes units to metric representations ('g', 'kg', 'ml', 'L', 'N').
    """
    if not val:
        return ""

    val = val.strip()
    # Check for prefix OCR noise e.g. g435g or m435g or net400g
    m_noise = re.search(r'^(?:g|m|net|wt)?\s*(\d+(?:\.\d+)?)\s*(g|gm|gms|kg|kgs|ml|mls|l|ltr|litre|liter|piece|pcs|n|units?|count|9|ग्राम|किग्रा|मिली|लीटर)\b', val, re.IGNORECASE)
    if m_noise:
        num, unit = m_noise.group(1), m_noise.group(2).lower()
        if unit in ('9', 'g', 'gm', 'gms', 'grams', 'ग्राम'):
            return f"{num} g"
        elif unit in ('kg', 'kgs', 'kilograms', 'किग्रा'):
            return f"{num} kg"
        elif unit in ('ml', 'mls', 'मिली'):
            return f"{num} ml"
        elif unit in ('l', 'ltr', 'liter', 'litre', 'लीटर'):
            return f"{num} L"
        elif unit in ('n', 'pcs', 'piece', 'units', 'unit', 'count'):
            return f"{num} N"

    # In-line repair: e.g. '400 9' within string
    val_clean = re.sub(r'\b(\d+(?:\.\d+)?)\s*9\b', r'\1 g', val)
    val_clean = val_clean.lower().replace('gm', 'g').replace('gms', 'g').replace('ltr', 'L').replace('liter', 'L').replace('litre', 'L')
    return val_clean.strip()

def repair_mrp(val: str) -> str:
    """
    Contextual MRP repair.
    Ensures currency prefix ₹, cleans punctuation and asterisks (e.g. '* 60.00' -> '₹60.00'),
    cleans comma decimal separator (299,00 -> 299.00), strips trailing slashes (299/- -> ₹299.00).
    Rejects dates, barcodes, FSSAI licenses, phone numbers, PIN codes, nutritional values,
    and unprinted instruction text (e.g., 'SEE BOTTOM OF PACK', 'REFER TO JAR').
    """
    if not val:
        return ""

    val = val.strip()
    # Reject obvious dates like 29/01/26 or 29.01.2026
    if re.search(r'\b\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}\b', val):
        return ""
    # Reject barcode or FSSAI sequences (10+ digits without decimals)
    if re.search(r'\b\d{8,}\b', val) and '.' not in val:
        return ""

    # Check for explicit currency indicator before stripping
    has_explicit_currency = bool(re.search(r'(?:₹|Rs\.?|INR)\s*\d+', val, re.IGNORECASE))
    raw_has_currency = bool(re.search(r'(?:₹|Rs\.?|INR)', val, re.IGNORECASE))

    # Reject unprinted instructional phrases unless an explicit currency-prefixed number is present
    has_instruction = bool(re.search(
        r'\b(?:SEE|BOTTOM|BELOW|CONTAINER|STAMP|PRINTED|SIDE|CAP|NECK|CRIMP|POUCH|LABEL|JAR|CAN|BOX|TOP|REFER|DETAILS|OFPACK|PACKAGE|PANEL|FLAP|BASE|UNDER|OVER|REVERSE|PACK)\b',
        val,
        re.IGNORECASE
    ))
    if has_instruction and not has_explicit_currency:
        return ""

    # Reject nutrition / energy / serving context without explicit currency
    if re.search(r'\b(?:kcal|cal|kj|energy|protein|carb|fat|sodium|serv|serving|portion|g|gm|kg|ml|l)\b', val, re.IGNORECASE) and not has_explicit_currency:
        return ""

    # Reject batch / mfd / exp / lic / pin code headers without explicit currency
    if re.search(r'\b(?:batch|lot|mfd|mfg|pkd|exp|lic|pin|pincode|phone|tel|mob)\b', val, re.IGNORECASE) and not has_explicit_currency:
        return ""

    # Strip existing currency prefixes, asterisks, colons, spaces
    val_clean = re.sub(r'^(?:M\.?R\.?P\.?|Maximum\s*Retail\s*Price|Retail\s*Price|MRPR)?[\s.:₹RsINR\/\-*~#\'\"\=]*', '', val, flags=re.IGNORECASE).strip()
    # Remove trailing /- or tax qualifiers
    val_clean = re.sub(r'\s*(?:/\-|\(.*\)|incl.*|all\s*taxes).*$', '', val_clean, flags=re.IGNORECASE).strip()
    # Replace comma decimal with period (e.g. 299,00 -> 299.00)
    val_clean = re.sub(r'(\d+),(\d{2})\b', r'\1.\2', val_clean)

    # Reject obvious corrupted non-numeric symbols
    if any(c in val_clean for c in ['■', '█', '▲', '▼', '★', '♦']):
        return ""

    # Check for clean decimal or integer price number e.g. 10, 10.00, 60.00, 499, 1499, 2499.00
    m_clean = re.search(r'(\d{1,5}(?:\.\d{1,2})?)', val_clean)
    if m_clean:
        try:
            num_val = float(m_clean.group(1))
            if 1.0 <= num_val <= 50000.0:
                return f"₹{m_clean.group(1)}"
        except ValueError:
            pass

    return ""

def repair_date(val: str) -> str:
    """
    Contextual date repair for MM/YYYY, DD/MM/YYYY, DD/MM/YY, and relative shelf life strings.
    Repairs letters 'O'/'o', 'I'/'l' substituted for digits inside date tokens.
    """
    if not val:
        return ""

    val = val.strip()
    # Replace common OCR letter substitutions in suspected date sequences
    # (e.g., 07/2O26 -> 07/2026, O8/2026 -> 08/2026, 29/O1/26 -> 29/01/26)
    m_date = re.search(r'\b([0-9OlI]{1,2})[./\-]([0-9OlI]{1,2})?[./\-]?([0-9OlI]{2,4})\b', val)
    if m_date:
        part1 = m_date.group(1).translate(str.maketrans('OlI', '011'))
        part2 = m_date.group(2).translate(str.maketrans('OlI', '011')) if m_date.group(2) else None
        part3 = m_date.group(3).translate(str.maketrans('OlI', '011'))

        if part2:
            return f"{part1}/{part2}/{part3}"
        else:
            return f"{part1}/{part3}"

    # Standard clean representation
    cleaned = re.sub(r'\s+', ' ', val).strip()
    return cleaned

def repair_batch_number(val: str) -> str:
    """
    Contextual batch number repair.
    Preserves valid alphanumeric lot identifiers and strips leading/trailing delimiter noise.
    Strictly filters out English statutory words and packaging instructions.
    Rejects purely alphabetic statutory terms.
    """
    if not val:
        return ""

    val = val.strip()
    val = re.sub(r'^(?:Batch\s*(?:No\.?|Number)?|Lot\s*(?:No\.?|Number)?|B\.?\s*No\.?|BATCH|LOT)[\s.:\-]*', '', val, flags=re.IGNORECASE).strip()
    
    tokens = [t.strip('.,:-_/# ') for t in val.split() if t.strip('.,:-_/# ')]
    if not tokens:
        return ""

    # Filter out pure instructional and statutory words
    valid_tokens = [t for t in tokens if t.upper() not in STATUTORY_BATCH_REJECT_TERMS and t.upper() not in INSTRUCTION_TERMS]
    if not valid_tokens:
        return ""

    cand = " ".join(valid_tokens)
    m = re.search(r'([A-Za-z0-9\-_\/]{2,30})', cand)
    if m:
        res = m.group(1).strip()
        # Reject purely alphabetic statutory terms
        if res.upper() in STATUTORY_BATCH_REJECT_TERMS or res.upper() in INSTRUCTION_TERMS:
            return ""
        # If purely alphabetic without digits, reject if in reject terms or short English fragment
        if res.isalpha() and (len(res) < 2 or res.upper() in STATUTORY_BATCH_REJECT_TERMS or res.upper() in INSTRUCTION_TERMS):
            return ""
        return res
    return ""
