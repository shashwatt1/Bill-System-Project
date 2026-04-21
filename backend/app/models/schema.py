"""Pydantic response models."""

from typing import Optional
from pydantic import BaseModel


class OCRRegion(BaseModel):
    text: str
    confidence: float
    bbox: list


class ParsedRow(BaseModel):
    item_code: Optional[str] = None
    qty: Optional[int] = None
    description: Optional[str] = None
    upc: Optional[str] = None
    price: Optional[float] = None
    disc: Optional[float] = None
    dep: Optional[float] = None
    net: Optional[float] = None
    total: Optional[float] = None


class ExtractionResponse(BaseModel):
    filename: str
    num_regions: int
    regions: list[OCRRegion]
    parsed_rows: Optional[list[ParsedRow]] = None
