# FastAPI Starter Template
# A minimal, production-ready Dockerfile for FastAPI services

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for OpenCV, Tesseract OCR, and XCB
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-ita \
    tesseract-ocr-deu \
    tesseract-ocr-por \
    tesseract-ocr-spa \
    tesseract-ocr-chi-sim \
    libgl1 \
    libglib2.0-0t64 \
    libxcb1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE $PORT

# Simple health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:$PORT/health', timeout=2)"

# Run the application
CMD uvicorn app:app --host 0.0.0.0 --port $PORT