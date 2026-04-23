"""Image preprocessing using OpenCV."""

import cv2
import numpy as np

from app.core.logger import get_logger

log = get_logger(__name__)


def deskew(image: np.ndarray) -> np.ndarray:
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        coords = np.column_stack(np.where(binary > 0))
        if coords.shape[0] == 0:
            log.info("Deskew: skipped (empty image)")
            return image

        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = 90 + angle
        else:
            angle = angle

        if abs(angle) <= 0.5:
            log.info("Deskew: detected angle %.2f°, skipped (below threshold)", angle)
            return image

        center = (image.shape[1] // 2, image.shape[0] // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, 
            (image.shape[1], image.shape[0]),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        log.info("Deskew: detected angle %.2f°, corrected", angle)
        return rotated
    except Exception as e:
        log.error("Deskew processing failed: %s", e)
        return image


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Convert raw image bytes to a cleaned grayscale image ready for OCR.

    Steps: decode → grayscale → adaptive threshold.
    """
    # Decode bytes to numpy array
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Failed to decode image — file may be corrupt or unsupported.")

    log.info("Decoded image: %dx%d", img.shape[1], img.shape[0])

    # Deskew before anything else
    img = deskew(img)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive thresholding — works well across varying lighting
    processed = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    log.info("Preprocessing complete")
    return processed
