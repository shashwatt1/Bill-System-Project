"""OCR extraction using PaddleOCR — lazy-loaded to prevent startup blocking."""

import math
import time
import threading
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor

from app.core.config import OCR_LANG, OCR_USE_GPU
from app.config import COLUMN_RANGES_PCT, ROW_MIN_HEIGHT, MAX_ROW_HEIGHT
from app.core.logger import get_logger
from app.services.parser import validate_row, merge_continuation_rows
from app.services.corrector import correct_row

log = get_logger(__name__)

# ── Lazy-loaded OCR model (prevents startup blocking) ──
_ocr_engine = None
_ocr_lock = threading.Lock()

def get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_lock:
            if _ocr_engine is None:
                from paddleocr import PaddleOCR
                log.info("Initializing PaddleOCR model (lang=%s, gpu=%s)...", OCR_LANG, OCR_USE_GPU)
                _ocr_engine = PaddleOCR(
                    use_angle_cls=False,   # disabled — faster, sufficient for flat invoices
                    lang=OCR_LANG,
                    use_gpu=OCR_USE_GPU,
                    show_log=False
                )
                log.info("PaddleOCR model ready")
    return _ocr_engine


def extract_text(image: np.ndarray) -> list[dict]:
    """Run OCR on a preprocessed image and return structured results."""
    ocr = get_ocr()
    result = ocr.ocr(image, cls=True)

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
    """Extract table rows using row-level OCR with geometry-driven column assignment."""

    pipeline_start = time.time()

    # ── Step 1: Grayscale + Otsu binarize + invert ──
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    row_detect_start = time.time()

    # ── Step 2: Horizontal projection ──
    projection = np.sum(binary, axis=1).astype(np.float32)

    # ── Step 3: Adaptive gap threshold (5% of max projection) ──
    gap_threshold = np.max(projection) * 0.05

    # ── Step 4: Find contiguous non-gap bands ──
    raw_bands = []
    in_row = False
    start_y = 0

    for y, val in enumerate(projection):
        if val >= gap_threshold:
            if not in_row:
                in_row = True
                start_y = y
        else:
            if in_row:
                in_row = False
                raw_bands.append((start_y, y))

    if in_row:
        raw_bands.append((start_y, len(projection)))

    raw_count = len(raw_bands)

    # ── Step 5: Min height filter + max height deterministic splitting ──
    ROW_MIN_HEIGHT = 30
    height_filtered = []
    for y1, y2 in raw_bands:
        height = y2 - y1
        if height < ROW_MIN_HEIGHT:
            continue
        if height > MAX_ROW_HEIGHT:
            n = math.ceil(height / MAX_ROW_HEIGHT)
            sub_height = height // n
            for i in range(n):
                sub_y1 = y1 + (i * sub_height)
                sub_y2 = sub_y1 + sub_height
                height_filtered.append((sub_y1, sub_y2))
        else:
            height_filtered.append((y1, y2))

    # ── Step 6: Row density filter ──
    density_threshold = gap_threshold * 2
    row_bands = []
    for y1, y2 in height_filtered:
        mean_density = float(np.mean(projection[y1:y2]))
        if mean_density < density_threshold:
            log.debug(
                "Skipped low-density band: y1=%d, y2=%d, mean_density=%.1f, threshold=%.1f",
                y1, y2, mean_density, density_threshold
            )
            continue
        row_bands.append((y1, y2))
        log.debug("Row band: y1=%d, y2=%d, height=%dpx", y1, y2, y2 - y1)

    if row_bands:
        merged_rows = []
        current = list(row_bands[0])

        for y1, y2 in row_bands[1:]:
            gap = y1 - current[1]

            # increase merge threshold even further
            if gap < 40:
                current[1] = y2
            else:
                merged_rows.append(tuple(current))
                current = [y1, y2]

        merged_rows.append(tuple(current))
        row_bands = merged_rows

    row_bands = [
        (y1, y2)
        for y1, y2 in row_bands
        if (y2 - y1) >= 30
    ]

    log.info(
        "Row detection: %d raw bands found, %d after height filtering and density filtering",
        raw_count, len(row_bands)
    )
    log.info("[PERF] ROW_DETECTION_TIME: %.2fs", time.time() - row_detect_start)
    log.info("[PERF] ROW_COUNT: %d", len(row_bands))

    # ── Resolve column pixel ranges from percentage config ──
    img_width = image.shape[1]
    column_ranges_px = {
        col: (int(x1 * img_width), int(x2 * img_width))
        for col, (x1, x2) in COLUMN_RANGES_PCT.items()
    }
    log.info("Image width: %dpx — column ranges resolved", img_width)

    # ── Build row crops for parallel OCR ──
    row_crops = [(y1, y2, image[y1:y2, :]) for (y1, y2) in row_bands]

    def run_ocr(row_data):
        """Worker: runs one OCR call per row crop."""
        y1, y2, row_crop = row_data
        row_start = time.time()
        try:
            # Normalize row height to 48px for consistent, faster inference
            if row_crop.shape[0] != 48:
                row_crop = cv2.resize(row_crop, (row_crop.shape[1], 48), interpolation=cv2.INTER_AREA)
            ocr = get_ocr()
            result = ocr.ocr(row_crop, cls=False)
            log.debug("[PERF] ROW_OCR_TIME y1=%d: %.3fs", y1, time.time() - row_start)
            return (y1, y2, result)
        except Exception as e:
            log.error("OCR failed for row y1=%d: %s", y1, e)
            return (y1, y2, None)

    # ── Parallel OCR across all rows ──
    ocr_start = time.time()
    with ThreadPoolExecutor(max_workers=6) as executor:
        ocr_results = list(executor.map(run_ocr, row_crops))
    log.info("[PERF] OCR_STAGE_TIME: %.2fs", time.time() - ocr_start)
    log.info("Parallel OCR complete: %d rows processed", len(ocr_results))

    # ── Process results: geometry-driven column assignment ──
    extracted_rows = []

    for y1, y2, result in ocr_results:
        log.debug("Processing row band: y1=%d, y2=%d", y1, y2)

        if not result or not result[0]:
            log.debug("Skipping row y1=%d: OCR returned no tokens", y1)
            continue

        # Initialise column buckets
        row_dict = {col: None for col in column_ranges_px}

        for line in result[0]:
            try:
                bbox, (text, conf) = line
                # Use horizontal midpoint of the token bounding box
                bbox_x1 = bbox[0][0]
                bbox_x2 = bbox[2][0]
                x_center = (bbox_x1 + bbox_x2) / 2
                
                assigned_col = None
                for col_name, (x1_col, x2_col) in column_ranges_px.items():
                    if x1_col <= x_center <= x2_col:
                        assigned_col = col_name
                        break
                
                # Gap handling — if x_center falls between two column ranges
                if assigned_col is None:
                    nearest_col = None
                    min_dist = float('inf')
                    for col_name, (x1_col, x2_col) in column_ranges_px.items():
                        col_center = (x1_col + x2_col) / 2
                        dist = abs(x_center - col_center)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_col = col_name
                    assigned_col = nearest_col
                
                # Collision handling — if two tokens map to same column in same row
                if row_dict[assigned_col] is not None:
                    existing_text, existing_conf = row_dict[assigned_col]
                    if conf > existing_conf:
                        log.debug("Column collision [%s]: kept '%s' over '%s' (conf: %.2f vs %.2f)", 
                                  assigned_col, text, existing_text, conf, existing_conf)
                        row_dict[assigned_col] = (text, conf)
                    else:
                        log.debug("Column collision [%s]: kept '%s' over '%s' (conf: %.2f vs %.2f)", 
                                  assigned_col, existing_text, text, existing_conf, conf)
                else:
                    row_dict[assigned_col] = (text, conf)
                    log.debug("Token '%s' (x_center=%.1f) → column [%s]", text, x_center, assigned_col)

            except (IndexError, TypeError, ValueError) as e:
                log.error("Malformed OCR token in row y1=%d: %s", y1, e)
                continue

        # Extract text for downstream
        final_row_dict = {}
        for col in column_ranges_px:
            final_row_dict[col] = row_dict[col][0].strip() if row_dict[col] is not None else ""

        # Guard: ensure all values are strings before calling .strip()
        safe_vals = [v if isinstance(v, str) else "" for v in final_row_dict.values()]

        if not any(v.strip() for v in safe_vals):
            log.debug("Skipping row y1=%d: all fields empty", y1)
            continue

        if sum(1 for v in safe_vals if not v.strip()) > 6:
            log.debug("Skipping row y1=%d: too many empty fields", y1)
            continue

        final_row_dict["_y1"] = y1
        final_row_dict["_y2"] = y2

        corrected_row = correct_row(final_row_dict)
        validated_row = validate_row(corrected_row)
        extracted_rows.append(validated_row)

    extracted_rows = merge_continuation_rows(extracted_rows)

    log.info("extract_table: %d rows returned after extraction", len(extracted_rows))
    log.info("[PERF] TOTAL_PIPELINE_TIME: %.2fs", time.time() - pipeline_start)
    return extracted_rows


def debug_visualize(image: np.ndarray, row_bands: list, col_ranges: dict, show_validation: bool = False) -> np.ndarray:
    """Draw debug lines and labels on the image for validation."""
    img_copy = image.copy()
    if len(img_copy.shape) == 2:
        img_copy = cv2.cvtColor(img_copy, cv2.COLOR_GRAY2BGR)

    for col_name, (x1, x2) in col_ranges.items():
        cv2.line(img_copy, (x1, 0), (x1, img_copy.shape[0]), (255, 0, 0), 1)
        cv2.line(img_copy, (x2, 0), (x2, img_copy.shape[0]), (255, 0, 0), 1)
        cv2.putText(img_copy, col_name, (x1 + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    for r in row_bands:
        y1, y2 = r.get("_y1"), r.get("_y2")
        if y1 is None or y2 is None:
            continue

        color = (0, 255, 0)

        if show_validation:
            if not (r.get("_net_valid", False) and r.get("_ext_valid", False) and r.get("_upc_valid", False)) or r.get("_validation_error", False):
                color = (0, 0, 255)

        cv2.line(img_copy, (0, y1), (img_copy.shape[1], y1), color, 1)
        cv2.line(img_copy, (0, y2), (img_copy.shape[1], y2), color, 1)

    return img_copy