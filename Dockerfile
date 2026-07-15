FROM python:3.11-slim

# Tesseract is required for the OCR ingestion path (OCR_BACKEND=tesseract).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/data/uploads

EXPOSE 8000

# Most free host-your-container platforms (Koyeb, Hugging Face Spaces,
# Railway, ...) inject a $PORT env var and expect the app to bind to it
# rather than a hardcoded port - default to 8000 for local `docker run` /
# docker-compose where nothing sets $PORT.
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8000)}/health')" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
