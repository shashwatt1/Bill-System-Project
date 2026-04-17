"""OCR extraction using PaddleOCR — model loaded once at module level."""

from paddleocr import PaddleOCR
import numpy as np

from app.core.config import OCR_LANG, OCR_USE_GPU
from app.core.logger import get_logger

log = get_logger(__name__)

# ── Global model instance — loaded once on import, reused across requests ──
log.info("Loading PaddleOCR model (lang=%s, gpu=%s)...", OCR_LANG, OCR_USE_GPU)
_ocr_engine = PaddleOCR(use_angle_cls=True, lang=OCR_LANG, use_gpu=OCR_USE_GPU, show_log=False)
log.info("PaddleOCR model ready")


def extract_text(image: np.ndarray) -> list[dict]:
    """Run OCR on a preprocessed image and return structured results.

    Returns a list of dicts with keys: text, confidence, bbox.
    """
    result = _ocr_engine.ocr(image, cls=True)

    if not result or not result[0]:
        log.warning("OCR returned no results")
        return []

    extracted = []
    for line in result[0]:
        bbox, (text, confidence) = line
        extracted.append({
            "text": text,
            "confidence": round(float(confidence), 4),
            "bbox": bbox,
        })

    log.info("Extracted %d text regions", len(extracted))
    return extracted
