"""Common utility functions."""

from pathlib import Path

from app.core.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB


def validate_image_file(filename: str, size_bytes: int) -> str | None:
    """Return an error message if the file is invalid, else None."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        return f"File too large ({size_bytes / 1024 / 1024:.1f} MB). Max allowed: {MAX_FILE_SIZE_MB} MB"

    return None
