"""FastAPI application entry point."""

from fastapi import FastAPI
from app.api.routes import router
from app.core.logger import get_logger

log = get_logger(__name__)

app = FastAPI(
    title="Document OCR API",
    description="Extract structured text from invoice and bill images.",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1", tags=["extraction"])


@app.get("/health")
async def health():
    return {"status": "ok"}
