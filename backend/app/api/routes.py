"""API route definitions."""

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from io import BytesIO
import cv2

from app.config import COLUMN_RANGES_PCT as COLUMN_RANGES
from app.core.logger import get_logger
from app.models.schema import ExtractionResponse
from app.services.preprocess import preprocess_image
from app.services.ocr import extract_text, extract_table, debug_visualize
from app.services.parser import reconstruct_layout
from app.services.exporter import export_rows
from app.utils.helpers import validate_image_file

log = get_logger(__name__)
router = APIRouter()


@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Accept an invoice/bill image and return structured OCR results."""

    # ── Validate ──
    contents = await file.read()
    error = validate_image_file(file.filename or "unknown", len(contents))
    if error:
        raise HTTPException(status_code=400, detail=error)

    log.info("Processing file: %s (%d bytes)", file.filename, len(contents))

    # ── Preprocess ──
    try:
        processed = preprocess_image(contents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Preprocessing failed")
        raise HTTPException(status_code=500, detail="Image preprocessing failed")

    # ── Table Extraction ──
    try:
        rows = extract_table(processed)
    except Exception as e:
        log.exception("Table extraction failed")
        raise HTTPException(status_code=500, detail=str(e))

    corrections_made = sum(len(r.get("_corrections", {})) for r in rows)

    return {
        "status": "success",
        "rows": rows,
        "row_count": len(rows),
        "corrections_made": corrections_made
    }


@router.post("/debug")
async def debug(file: UploadFile = File(...), show_validation: bool = Query(False)):
    """Run extraction and return a visualization image."""
    contents = await file.read()
    error = validate_image_file(file.filename or "unknown", len(contents))
    if error:
        raise HTTPException(status_code=400, detail=error)

    try:
        processed = preprocess_image(contents)
    except Exception as e:
        log.exception("Preprocessing failed")
        raise HTTPException(status_code=500, detail="Image preprocessing failed")

    try:
        rows = extract_table(processed)
    except Exception as e:
        log.exception("Table extraction failed")
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Resolve percentage column ranges to pixel values for the processed image
        img_width = processed.shape[1]
        column_ranges_px = {
            col: (int(x1 * img_width), int(x2 * img_width))
            for col, (x1, x2) in COLUMN_RANGES.items()
        }
        annotated_img = debug_visualize(processed, rows, column_ranges_px, show_validation=show_validation)
        success, encoded_image = cv2.imencode(".jpg", annotated_img)
        if not success:
            raise ValueError("CV2 encoding failed")
    except Exception as e:
        log.exception("Visualization failed")
        raise HTTPException(status_code=500, detail="Visualization failed")

    return StreamingResponse(BytesIO(encoded_image.tobytes()), media_type="image/jpeg")


@router.post("/export")
async def export(file: UploadFile = File(...), format: str = Query("json")):
    """Preprocess, extract, and export rows in the requested format."""
    contents = await file.read()
    error = validate_image_file(file.filename or "unknown", len(contents))
    if error:
        raise HTTPException(status_code=400, detail=error)

    log.info("Export request: file=%s, format=%s", file.filename, format)

    try:
        processed = preprocess_image(contents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Preprocessing failed")
        raise HTTPException(status_code=500, detail="Image preprocessing failed")

    try:
        rows = extract_table(processed)
    except Exception as e:
        log.exception("Table extraction failed")
        raise HTTPException(status_code=500, detail=str(e))

    try:
        content, media_type = export_rows(rows, fmt=format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Export formatting failed")
        raise HTTPException(status_code=500, detail="Export failed")

    headers = {}
    if format.lower() == "csv":
        headers["Content-Disposition"] = "attachment; filename=\"invoice_export.csv\""
    elif format.lower() == "edi":
        headers["Content-Disposition"] = "attachment; filename=\"invoice_export.edi\""

    return Response(content=content, media_type=media_type, headers=headers)
