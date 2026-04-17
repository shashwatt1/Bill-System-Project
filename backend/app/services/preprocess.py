"""Image preprocessing using OpenCV."""

import cv2
import numpy as np

from app.core.logger import get_logger

log = get_logger(__name__)


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

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive thresholding — works well across varying lighting
    processed = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    log.info("Preprocessing complete")
    return processed
