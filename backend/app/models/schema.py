"""Pydantic response models."""

from pydantic import BaseModel


class OCRRegion(BaseModel):
    text: str
    confidence: float
    bbox: list


class ExtractionResponse(BaseModel):
    filename: str
    num_regions: int
    regions: list[OCRRegion]
