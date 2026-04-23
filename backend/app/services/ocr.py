"""OCR extraction using PaddleOCR — model loaded once at module level."""

from paddleocr import PaddleOCR
import numpy as np
import cv2

from app.core.config import OCR_LANG, OCR_USE_GPU
from app.config import COLUMN_RANGES_PCT, ROW_GAP_THRESHOLD
from app.core.logger import get_logger
from app.services.parser import validate_row
from app.services.corrector import correct_row

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


def extract_table(image: np.ndarray) -> list[dict]:
    """Extract table rows and cells using row projection."""
    # Convert image to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Horizontal projection: sum pixel values across each row (after binarization)
    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    projection = np.sum(binary, axis=1)

    # A "row gap" is where projection value is below a threshold
    row_bands = []
    in_row = False
    start_y = 0
    
    for y, val in enumerate(projection):
        if val > ROW_GAP_THRESHOLD:
            if not in_row:
                in_row = True
                start_y = y
        else:
            if in_row:
                in_row = False
                end_y = y
                if end_y - start_y >= 10:  # Minimum row height: 10px
                    row_bands.append((start_y, end_y))
                    
    if in_row:
        end_y = len(projection)
        if end_y - start_y >= 10:
            row_bands.append((start_y, end_y))

    log.info("Detected %d rows", len(row_bands))

    img_width = image.shape[1]
    column_ranges_px = {
        col: (int(x1 * img_width), int(x2 * img_width))
        for col, (x1, x2) in COLUMN_RANGES_PCT.items()
    }
    log.info("Image width: %dpx — column ranges resolved", img_width)

    extracted_rows = []
    for y1, y2 in row_bands:
        row_dict = {}
        
        for col_name, (x1, x2) in column_ranges_px.items():
            crop = image[y1:y2, x1:x2]
            
            if crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
                row_dict[col_name] = ""
                continue
                
            try:
                result = _ocr_engine.ocr(crop, cls=False)
                # extract text: result[0][0][1][0] if result and result[0] else ""
                text = result[0][0][1][0] if result and result[0] else ""
                row_dict[col_name] = text
                log.debug("Cell [%s] dimensions: %sx%s, OCR: '%s'", col_name, crop.shape[1], crop.shape[0], text)
            except Exception as e:
                log.error("OCR failed for cell %s: %s", col_name, e)
                row_dict[col_name] = ""
                
        # Skip if all fields are empty
        if not any(v.strip() for v in row_dict.values() if isinstance(v, str)):
            continue

        # Skip if more than 6 of 9 fields are empty
        if sum(1 for v in row_dict.values() if isinstance(v, str) and not v.strip()) > 6:
            continue
            
        row_dict["_y1"] = y1
        row_dict["_y2"] = y2
        
        corrected_row = correct_row(row_dict)
        validated_row = validate_row(corrected_row)
        extracted_rows.append(validated_row)

    return extracted_rows


def debug_visualize(image: np.ndarray, row_bands: list, col_ranges: dict, show_validation: bool = False) -> np.ndarray:
    """Draw debug lines and labels on the image for validation."""
    img_copy = image.copy()
    if len(img_copy.shape) == 2:
        img_copy = cv2.cvtColor(img_copy, cv2.COLOR_GRAY2BGR)

    # Blue vertical lines at each column x1, x2
    for col_name, (x1, x2) in col_ranges.items():
        cv2.line(img_copy, (x1, 0), (x1, img_copy.shape[0]), (255, 0, 0), 1)
        cv2.line(img_copy, (x2, 0), (x2, img_copy.shape[0]), (255, 0, 0), 1)
        # White column name labels above first line
        cv2.putText(img_copy, col_name, (x1 + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Horizontal lines at each row band y1, y2
    for r in row_bands:
        y1, y2 = r.get("_y1"), r.get("_y2")
        if y1 is None or y2 is None:
            continue
            
        color = (0, 255, 0)  # Green by default
        
        if show_validation:
            # RED if any valid flag is False, GREEN if all True
            # (only checking the strictly required arithmetic/upc fields which we validated)
            if not (r.get("_net_valid", False) and r.get("_ext_valid", False) and r.get("_upc_valid", False)) or r.get("_validation_error", False):
                color = (0, 0, 255)  # Red (BGR)

        cv2.line(img_copy, (0, y1), (img_copy.shape[1], y1), color, 1)
        cv2.line(img_copy, (0, y2), (img_copy.shape[1], y2), color, 1)

    return img_copy


