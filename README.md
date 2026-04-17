# Document OCR API

Extract structured text from invoice and bill images using PaddleOCR.

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
cd backend
python run.py
```

Server starts at `http://localhost:8000`.  
Docs at `http://localhost:8000/docs`.

## Test

```bash
curl -X POST http://localhost:8000/api/v1/extract \
  -F "file=@/path/to/invoice.jpg"
```

## Project Status

| Module      | Status          |
|-------------|-----------------|
| Preprocess  | ✅ Implemented  |
| OCR         | ✅ Implemented  |
| Parser      | ⬜ Placeholder  |
| LLM         | ⬜ Placeholder  |
| Validator   | ⬜ Placeholder  |
| Formatter   | ⬜ Placeholder  |
