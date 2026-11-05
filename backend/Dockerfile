FROM python:3.11-slim

# Install system dependencies for PDF/OCR processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir poetry || pip install --no-cache-dir \
    fastapi uvicorn pydantic pydantic-settings supabase python-multipart \
    pypdf python-docx pytesseract pdf2image Pillow python-jose[cryptography] \
    passlib[bcrypt] structlog python-dotenv httpx tenacity numpy celery redis

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
