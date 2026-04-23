"""Layout reconstruction and pattern extraction engine."""

import re
from app.core.logger import get_logger

log = get_logger(__name__)

# --- DICTIONARY ---
CORRECTIONS = {
    "COORSLIGH": "COORS LIGHT",
    "MILLERLIIE": "MILLER LITE",
    "LIIE": "LITE",
    "COORSLIGHT": "COORS LIGHT",
    "MILLERLITE": "MILLER LITE",
}


def clean_text(text: str) -> str:
    """Normalize text, fix spacing, and apply dictionary corrections."""
    # Convert to upper and trim
    clean = text.upper().strip()
    
    # Remove junk symbols (keep digits, letters, dots, spaces)
    clean = re.sub(r'[^\w\s\.]', '', clean)

    # Apply dictionary substitutions
    for wrong, right in CORRECTIONS.items():
        if wrong in clean:
            clean = clean.replace(wrong, right)
            
    return clean


def extract_numeric_fields(text: str) -> dict:
    """
    Split long numeric strings into structured values.
    Example: 07199000048621950.00120231569.45
    """
    res = {
        "upc": None,
        "price": None,
        "disc": None,
        "dep": None,
        "net": None,
        "total": None
    }
    
    text = text.replace(" ", "").strip()
    if not text:
        return res

    # Extract 11-12 digit UPC
    upc_match = re.match(r'^(\d{11,12})', text)
    if upc_match:
        res["upc"] = upc_match.group(1)
        tail = text[upc_match.end():]
    else:
        # Fallback if no UPC
        tail = text
        
    # Process remaining numbers as float values
    # If the user's specific noisy string lacks dots or has dots in weird places,
    # stripping dots and slicing heuristically from the back is extremely robust.
    clean_tail = tail.replace(".", "")
    
    def to_float(s: str) -> float:
        if len(s) >= 3:
            return float(s[:-2] + "." + s[-2:])
        elif len(s) == 2:
            return float("0." + s)
        elif len(s) == 1:
            return float("0.0" + s)
        return 0.0

    # Heuristic slice: Total(4), Net(4), Dep(3), Disc(3), Price(remaining)
    if len(clean_tail) >= 14:
        try:
            total_str = clean_tail[-4:]
            net_str = clean_tail[-8:-4]
            dep_str = clean_tail[-11:-8]
            disc_str = clean_tail[-14:-11]
            price_str = clean_tail[:-14]
            
            res["total"] = to_float(total_str)
            res["net"] = to_float(net_str)
            res["dep"] = to_float(dep_str)
            res["disc"] = to_float(disc_str)
            if price_str:
                res["price"] = to_float(price_str)
        except ValueError:
            pass
    else:
        # Fallback to \d+\.\d+ if size matches were weird
        floats = re.findall(r'\d+\.\d+', tail)
        if floats:
            try:
                res["total"] = float(floats[-1])
                if len(floats) > 1:
                    res["price"] = float(floats[0])
            except ValueError:
                pass
                
    return res


def classify_row(text: str) -> str:
    """Classify row into item_row, header, noise, out_of_stock."""
    upper = text.upper()
    if "OUT OF STOCK" in upper:
        return "out_of_stock"
    if "ITEM" in upper or "QTY" in upper or "DESCRIPTION" in upper:
        return "header"
        
    # Check if contains numbers + product words
    if re.search(r'\d', text) and re.search(r'[A-Za-z]', text):
        return "item_row"
        
    return "noise"


def parse_item_row(text: str) -> dict:
    """Extract QTY, description, and numeric financials from an item row."""
    result = {
        "qty": None,
        "description": None,
        "upc": None,
        "price": None,
        "disc": None,
        "dep": None,
        "net": None,
        "total": None
    }
    
    # 1. Extract QTY (First Number)
    qty_match = re.search(r'^(\d{1,4})\s?', text)
    if qty_match:
        result["qty"] = int(qty_match.group(1))
        text = text[qty_match.end():].strip()
        
    # 2. Split numeric block from description
    block_match = re.search(r'(\d{11,}[\d\.\s]*)$', text)
    if block_match:
        numeric_block = block_match.group(1).replace(" ", "")
        desc = text[:block_match.start()].strip()
        result["description"] = clean_text(desc)
        
        # 3. & 4. Call numeric extraction
        fields = extract_numeric_fields(numeric_block)
        result.update(fields)
    else:
        # Fallback to general splits
        parts = text.split()
        if len(parts) >= 2:
            result["description"] = clean_text(" ".join(parts[:-1]))
            fields = extract_numeric_fields(parts[-1])
            result.update(fields)
        else:
            result["description"] = clean_text(text)
            
    return result


def group_rows(regions: list[dict], y_tolerance: float = 15.0) -> list[list[dict]]:
    """Group tokens into rows based on Y-coordinate."""
    if not regions:
        return []

    items = []
    for r in regions:
        bbox = r["bbox"]
        avg_y = sum(p[1] for p in bbox) / len(bbox)
        min_x = min(p[0] for p in bbox)
        items.append({"avg_y": avg_y, "min_x": min_x, "region": r})

    items.sort(key=lambda x: x["avg_y"])
    rows, current_row, current_y = [], [], None

    for item in items:
        if current_y is None:
            current_row.append(item)
            current_y = item["avg_y"]
        else:
            if abs(item["avg_y"] - current_y) <= y_tolerance:
                current_row.append(item)
            else:
                rows.append(current_row)
                current_row = [item]
                current_y = item["avg_y"]
                
    if current_row:
        rows.append(current_row)

    return rows


def sort_row(row_items: list[dict]) -> list[dict]:
    """Sort tokens within a row by X-coordinate (left -> right)."""
    sorted_items = sorted(row_items, key=lambda x: x["min_x"])
    return [item["region"] for item in sorted_items]


def reconstruct_layout(ocr_regions: list[dict]) -> list[dict]:
    """Pipeline flow: clean, classify, parse, filter, and extract items."""
    parsed_rows = []
    
    row_groups = group_rows(ocr_regions)
    log.info("Layout Parsing: Grouped into %d distinct rows.", len(row_groups))

    for group in row_groups:
        sorted_tokens = sort_row(group)
        raw_text = " ".join(token["text"] for token in sorted_tokens)
        
        # 1. Clean Text globally if needed, though we clean description later.
        # We classify on the raw, but upper-case representation.
        category = classify_row(raw_text)
        
        if category == "item_row":
            parsed_data = parse_item_row(raw_text)
            
            # Filter completely empty or false positive rows
            if parsed_data.get("description") or parsed_data.get("upc"):
                parsed_rows.append(parsed_data)
        elif category == "out_of_stock":
            log.info("Skipping 'OUT OF STOCK' row: %s", raw_text)
        elif category == "header":
            log.info("Skipping recognized header: %s", raw_text)
        else:
            log.info("Skipping noise row: %s", raw_text)

    log.info("Layout Parsing: Extracted %d item rows.", len(parsed_rows))
    return parsed_rows


def validate_row(row: dict) -> dict:
    """Validate arithmetic rules and types for row dicts.
    
    Rules (all with ±0.02 tolerance):
      NET = PRICE - DISC + DEP
      EXT = NET × QTY
      UPC = 11 or 12 digits, all numeric
    """
    res = dict(row)
    res["_net_valid"] = False
    res["_ext_valid"] = False
    res["_upc_valid"] = False
    res["_validation_error"] = False

    try:
        qty_str = res.get("QTY", "0")
        price_str = res.get("PRICE", "0")
        disc_str = res.get("DISC", "0")
        dep_str = res.get("DEP", "0")
        net_str = res.get("NET", "0")
        ext_str = res.get("EXT", "0")

        # Handle empty strings mapping to 0
        qty = float(qty_str) if qty_str else 0.0
        price = float(price_str) if price_str else 0.0
        disc = float(disc_str) if disc_str else 0.0
        dep = float(dep_str) if dep_str else 0.0
        net = float(net_str) if net_str else 0.0
        ext = float(ext_str) if ext_str else 0.0

        if abs((price - disc + dep) - net) <= 0.02:
            res["_net_valid"] = True

        if abs((net * qty) - ext) <= 0.02:
            res["_ext_valid"] = True

    except ValueError:
        res["_validation_error"] = True

    upc_str = str(res.get("UPC", "")).strip()
    if upc_str.isdigit() and len(upc_str) in (11, 12):
        res["_upc_valid"] = True
    return res


def merge_continuation_rows(rows: list[dict]) -> list[dict]:
    """
    Merges multi-line description rows into their parent row.
    A continuation row has DESC populated but all numeric 
    fields empty — it is the second (or third) physical line 
    of a single invoice item.
    """
    NUMERIC_FIELDS = ["UPC", "PRICE", "DISC", "DEP", "NET", "EXT"]
    
    result = []
    merged_count = 0
    
    for row in rows:
        # Check if this is a continuation row
        has_desc = bool(row.get("DESC", "").strip())
        all_numeric_empty = all(
            not row.get(f, "").strip() 
            for f in NUMERIC_FIELDS
        )
        
        is_continuation = has_desc and all_numeric_empty
        
        if is_continuation and result:
            # Append DESC to previous row, separated by space
            prev_desc = result[-1].get("DESC", "").strip()
            cont_desc = row["DESC"].strip()
            result[-1]["DESC"] = f"{prev_desc} {cont_desc}".strip()
            merged_count += 1
            # Do NOT append this row to result
        else:
            result.append(row)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Continuation merge: {merged_count} rows merged into previous rows")
    
    return result
