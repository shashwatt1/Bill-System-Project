"""Layout reconstruction and parsing layer."""

import re
from app.core.logger import get_logger

log = get_logger(__name__)


def group_rows(regions: list[dict], y_tolerance: float = 15.0) -> list[list[dict]]:
    """Group tokens into rows based on Y-coordinate."""
    if not regions:
        return []

    # Calculate average Y and min X for each region
    items = []
    for r in regions:
        bbox = r["bbox"]
        avg_y = sum(p[1] for p in bbox) / len(bbox)
        min_x = min(p[0] for p in bbox)
        items.append({"avg_y": avg_y, "min_x": min_x, "region": r})

    # Sort strictly by vertical position
    items.sort(key=lambda x: x["avg_y"])

    rows = []
    current_row = []
    current_y = None

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


def parse_row(text: str) -> dict:
    """Smart split logic for a single reconstructed line."""
    result = {
        "item_code": None,
        "qty": None,
        "description": None,
        "upc": None,
        "price": None,
        "total": None
    }
    
    # Fast path: ignore short irrelevant lines
    if len(text) < 5:
        return result

    # Standardize string for merged token cases
    clean_text = text.replace(" ", "")

    # Look for the specific merged pattern: QTY + DESC + UPC(11-12) + FINANCIALS
    # e.g. "3COORSLIGHT07199000486219500020231569.4"
    match = re.match(r'^(\d{1,4})?([A-Za-z]+)(\d{11,12})(\d*[\d\.]*)$', clean_text)
    
    if match:
        qty_str = match.group(1)
        desc_str = match.group(2)
        upc_str = match.group(3)
        tail_str = match.group(4)
        
        if qty_str:
            result["qty"] = int(qty_str)
        result["description"] = desc_str
        
        # Assume first 11 digits of the block are UPC
        result["upc"] = upc_str[:11]
        
        # Re-attach the rest of the UPC block to the tail for financial heuristics
        rem = upc_str[11:] + tail_str
        rem_clean = rem.replace(".", "")
        
        # Price heuristic: 4 chars (e.g. 2195 -> 21.95)
        if len(rem_clean) >= 4:
            try:
                result["price"] = float(rem_clean[:2] + "." + rem_clean[2:4])
            except ValueError:
                pass
        
        # Total heuristic
        if "." in tail_str:
            m = re.search(r'(\d{1,4}\.\d{1,2})$', tail_str)
            if m:
                try:
                    result["total"] = float(m.group(1))
                except ValueError:
                    pass
        else:
            if len(rem_clean[-4:]) == 4:
                try:
                    result["total"] = float(rem_clean[-4:-2] + "." + rem_clean[-2:])
                except ValueError:
                    pass

    else:
        # Fallback: Just parse space-separated texts (standard case)
        parts = text.split()
        if len(parts) > 2:
            try:
                # Try to extract Qty and Total from first and last parts
                if parts[0].isdigit():
                    result["qty"] = int(parts[0])
                
                clean_last = parts[-1].replace('$', '').replace(',', '')
                if clean_last.replace('.', '').isdigit():
                    result["total"] = float(clean_last)
                
                # Assume everything between might be description & UPC
                mid = parts[1:-1]
                if mid and mid[-1].isdigit() and len(mid[-1]) >= 8:
                    result["upc"] = mid[-1]
                    result["description"] = " ".join(mid[:-1])
                else:
                    result["description"] = " ".join(mid)
            except ValueError:
                pass

    return result


def reconstruct_layout(ocr_regions: list[dict]) -> list[dict]:
    """Main pipeline: group rows, sort columns, combine strings, parse details."""
    parsed_rows = []
    
    # 1. Group rows based on Y-coordinate proximity
    row_groups = group_rows(ocr_regions)
    log.info("Layout Parsing: Grouped into %d distinct rows.", len(row_groups))

    # 2. Process each row
    for group in row_groups:
        sorted_tokens = sort_row(group)
        full_text = " ".join(token["text"] for token in sorted_tokens)
        
        # Extract structured details using regex and heuristics
        parsed_data = parse_row(full_text)
        
        # Filter valid items
        if parsed_data.get("description") or parsed_data.get("upc") or parsed_data.get("qty"):
            parsed_rows.append(parsed_data)

    log.info("Layout Parsing: Successfully structured %d line items.", len(parsed_rows))
    return parsed_rows
