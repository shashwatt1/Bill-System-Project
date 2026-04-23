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
#     "EXT":   (910, 1000)
# }

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
ROW_GAP_THRESHOLD = 8  # minimum pixel gap between rows

# Correction layer config
FUZZY_MATCH_CUTOFF = 0.65     # difflib cutoff for description matching
NUMERIC_FIELDS = ["PRICE", "DISC", "DEP", "NET", "EXT", "QTY", "ITEM"]
DESCRIPTION_FIELDS = ["DESC"]

VALIDATION_TOLERANCE = 0.05

ROW_MIN_HEIGHT = 10
MAX_ROW_HEIGHT = 80
