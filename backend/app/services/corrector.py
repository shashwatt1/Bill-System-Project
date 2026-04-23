"""Post-OCR Correction Layer (Rule-Based)."""

import re
from difflib import get_close_matches

from app.core.logger import get_logger
from app.config import FUZZY_MATCH_CUTOFF, NUMERIC_FIELDS, DESCRIPTION_FIELDS

log = get_logger(__name__)

# HOW TO EXTEND:
# Add new canonical product name as key (exact, uppercase preferred)
# Add known OCR variants as list values
# The system auto-builds the alias lookup at startup
# Fuzzy matching handles variants not explicitly listed
PRODUCT_MASTER = {
    "COORS LIGHT": ["COORSLIGH", "COORSLIGHT", "COORS LGT", 
                    "COORS LT", "COORSLIGH T"],
    "MILLER LITE": ["MILLERLIIE", "MILLER LIT", "MILLERLITE", 
                    "MILLER LTE", "MLLERLIT", 
                    "M1LLER L1TE", "MILLER L1TE", "M1LLER LITE"],
    "BUD LIGHT":   ["BUDLIGH", "BUD LIGH", "BUD LGT", "BUDLIGHT"],
    "BUDWEISER":   ["BUDWEIZER", "BUDWISER", "BUDWIESER"],
    "MICHELOB ULTRA": ["MICHELOB ULT", "MICHULTRA", "MICH ULTRA",
                       "M1CH U1TRA", "MICH UL TRA", "MICHELOB UL", "MICHULTR"],
    "CORONA EXTRA":   ["CORONA EXT", "CORONAEXTR", "CORONA XTR"],
}

_ALIAS_MAP = {}
for canonical, aliases in PRODUCT_MASTER.items():
    for alias in aliases:
        _ALIAS_MAP[alias.upper()] = canonical


def clean_numeric(raw: str) -> str:
    """Apply character substitution map to fix OCR misreads in numeric fields."""
    if not isinstance(raw, str) or not raw:
        return raw

    # Gate: if raw is already a valid float or int, return immediately
    try:
        float(raw.strip())
        log.debug("clean_numeric: '%s' already valid — skipped substitution", raw)
        return raw.strip()
    except ValueError:
        pass  # proceed with correction

    SUBSTITUTION_MAP = {
        'S': '5', 's': '5',
        'I': '1', 'i': '1', 'l': '1',
        'O': '0', 'o': '0',
        'Z': '2', 'z': '2',
    }

    # Apply substitution map
    substituted = "".join(SUBSTITUTION_MAP.get(c, c) for c in raw)

    # Strip characters except digits, '.', and '-'
    cleaned = re.sub(r'[^\d\.\-]', '', substituted)

    # Check if result is a valid float string
    if not cleaned:
        return raw

    try:
        float(cleaned)
        log.debug("clean_numeric: '%s' -> '%s' via substitution", raw, cleaned)
        return cleaned
    except ValueError:
        return raw


def correct_description(raw: str) -> str:
    """Correct product description using exact alias match then fuzzy match."""
    if not isinstance(raw, str) or not raw:
        return raw

    raw_upper = raw.upper()

    # Step 1 — Exact alias match
    if raw_upper in _ALIAS_MAP:
        return _ALIAS_MAP[raw_upper]
    
    # Also check if it already matches a canonical name exactly
    if raw_upper in PRODUCT_MASTER:
        return raw_upper

    # Step 2 — Fuzzy match using difflib
    candidates = list(_ALIAS_MAP.keys()) + list(PRODUCT_MASTER.keys())
    matches = get_close_matches(raw_upper, candidates, n=1, cutoff=FUZZY_MATCH_CUTOFF)
    
    if matches:
        matched = matches[0]
        # resolve through alias map or direct
        return _ALIAS_MAP.get(matched, matched)

    # Step 3 — No match
    return raw


def correct_row(row: dict) -> dict:
    """Apply post-OCR corrections to a row dict."""
    corrected = row.copy()
    corrections_metadata = {}

    try:
        for field, value in row.items():
            if field.startswith("_") or field == "UPC":
                continue

            after_val = value

            if field in NUMERIC_FIELDS:
                if isinstance(value, str):
                    after_val = clean_numeric(value)
            elif field in DESCRIPTION_FIELDS:
                if isinstance(value, str):
                    after_val = correct_description(value)

            if after_val != value:
                corrections_metadata[field] = {"before": value, "after": after_val}
                corrected[field] = after_val
                log.debug("Corrected [%s]: '%s' -> '%s'", field, value, after_val)

        corrected["_corrections"] = corrections_metadata
    except Exception as e:
        log.error("Failed to correct row: %s", e)
        # return original row unchanged if anything fails
        row_copy = row.copy()
        row_copy["_corrections"] = {}
        return row_copy

    return corrected
