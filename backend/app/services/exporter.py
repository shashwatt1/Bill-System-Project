"""Export layer — converts validated row dicts to CSV, EDI, or JSON."""

import csv
import json
from datetime import datetime
from io import StringIO

from app.core.logger import get_logger

log = get_logger(__name__)

EXPORT_COLUMNS = ["ITEM", "QTY", "DESC", "UPC", "PRICE", "DISC", "DEP", "NET", "EXT"]


def _clean_rows(rows: list[dict]) -> list[dict]:
    """Strip all internal metadata keys (starting with '_') from rows."""
    return [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]


def to_csv(rows: list[dict]) -> str:
    """Convert validated rows to a CSV string."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=EXPORT_COLUMNS,
        extrasaction="ignore",
        lineterminator="\n"
    )
    writer.writeheader()

    for i, row in enumerate(rows):
        try:
            cleaned = {col: (row.get(col) or "") for col in EXPORT_COLUMNS}
            writer.writerow(cleaned)
        except Exception as e:
            log.warning("to_csv: skipping bad row %d: %s", i, e)
            continue

    return output.getvalue()


def to_edi(rows: list[dict]) -> str:
    """Convert validated rows to a flat pipe-delimited EDI-like string."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    count = len(rows)
    lines = [f"HDR|INVOICE|{timestamp}|ROWS={count}"]

    total_ext = 0.0

    for i, row in enumerate(rows):
        try:
            fields = [str(row.get(col) or "") for col in EXPORT_COLUMNS]
            lines.append("ITM|" + "|".join(fields))

            ext_val = row.get("EXT", "")
            try:
                total_ext += float(ext_val)
            except (ValueError, TypeError):
                pass  # skip non-numeric EXT in total
        except Exception as e:
            log.warning("to_edi: skipping bad row %d: %s", i, e)
            continue

    lines.append(f"FTR|TOTAL_ROWS={count}|TOTAL_EXT={round(total_ext, 2):.2f}")
    return "\n".join(lines)


def export_rows(rows: list[dict], fmt: str = "json") -> tuple[str, str]:
    """Dispatch rows to the requested export format.

    Returns (content: str, media_type: str).
    """
    fmt = fmt.lower()

    if fmt == "json":
        cleaned = _clean_rows(rows)
        return json.dumps(cleaned, indent=2), "application/json"
    elif fmt == "csv":
        return to_csv(rows), "text/csv"
    elif fmt == "edi":
        return to_edi(rows), "text/plain"
    else:
        raise ValueError(f"Unsupported export format: '{fmt}'. Choose from: json, csv, edi")
