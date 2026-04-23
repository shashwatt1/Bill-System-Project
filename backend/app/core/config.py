"""Application configuration."""

import os
from pathlib import Path

# ================================
# Project paths
# ================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure directories exist
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ================================
# File validation
# ================================

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
MAX_FILE_SIZE_MB = 10

# ================================
# OCR settings
# ================================

OCR_LANG = os.getenv("OCR_LANG", "en")
OCR_USE_GPU = os.getenv("OCR_USE_GPU", "false").lower() == "true"

# ================================
# Column Configuration
# ================================

# Legacy absolute ranges — kept for reference only
# COLUMN_RANGES = {
#     "ITEM":  (0,   80),
#     "QTY":   (80,  140),
#     "DESC":  (140, 450),
#     "UPC":   (450, 620),
#     "PRICE": (620, 700),
#     "DISC":  (700, 770),
#     "DEP":   (770, 840),
#     "NET":   (840, 910),
#     "EXT":   (910, 1000),
# }

# Relative column ranges (percentage-based)
COLUMN_RANGES_PCT = {
    "ITEM":  (0.000, 0.080),
    "QTY":   (0.080, 0.140),
    "DESC":  (0.140, 0.450),
    "UPC":   (0.450, 0.620),
    "PRICE": (0.620, 0.700),
    "DISC":  (0.700, 0.770),
    "DEP":   (0.770, 0.840),
    "NET":   (0.840, 0.910),
    "EXT":   (0.910, 1.000),
}

# Backward compatibility for existing imports
COLUMN_RANGES = COLUMN_RANGES_PCT

# Row detection threshold
ROW_GAP_THRESHOLD = 8

# ================================
# Correction Layer Config
# ================================

FUZZY_MATCH_CUTOFF = 0.65

NUMERIC_FIELDS = ["PRICE", "DISC", "DEP", "NET", "EXT", "QTY", "ITEM"]
DESCRIPTION_FIELDS = ["DESC"]

# ================================
# Validation Config
# ================================

VALIDATION_TOLERANCE = 0.05