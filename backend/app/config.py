COLUMN_RANGES = {
    "ITEM":  (0,   80),
    "QTY":   (80,  140),
    "DESC":  (140, 450),
    "UPC":   (450, 620),
    "PRICE": (620, 700),
    "DISC":  (700, 770),
    "DEP":   (770, 840),
    "NET":   (840, 910),
    "EXT":   (910, 1000)
}
ROW_GAP_THRESHOLD = 8  # minimum pixel gap between rows

# ⚠️ NOTE: These X-ranges are calibration placeholders.
# They must be adjusted to match the actual invoice pixel width.

# Correction layer config
FUZZY_MATCH_CUTOFF = 0.75     # difflib cutoff for description matching
NUMERIC_FIELDS = ["PRICE", "DISC", "DEP", "NET", "EXT", "QTY", "ITEM"]
DESCRIPTION_FIELDS = ["DESC"]
