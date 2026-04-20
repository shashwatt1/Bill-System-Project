"""API route definitions."""

from fastapi import APIRouter, File, UploadFile, HTTPException

from app.core.logger import get_logger
from app.models.schema import ExtractionResponse
from app.services.preprocess import preprocess_image
from app.services.ocr import extract_text
from app.services.parser import reconstruct_layout
from app.utils.helpers import validate_image_file

log = get_logger(__name__)
router = APIRouter()


@router.post("/extract", response_model=ExtractionResponse)
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

    # ── OCR ──
    try:
        regions = extract_text(processed)
    except Exception as e:
        log.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail="OCR extraction failed")

    # ── Parsed Layout ──
    try:
        parsed_rows = reconstruct_layout(regions)
    except Exception as e:
        log.exception("Layout parsing failed")
        raise HTTPException(status_code=500, detail="Layout parsing failed")

    return ExtractionResponse(
        filename=file.filename or "unknown",
        num_regions=len(regions),
        regions=regions,
        parsed_rows=parsed_rows,
    )
