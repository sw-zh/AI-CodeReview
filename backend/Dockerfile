FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y \
    git libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
    poppler-utils tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install --upgrade pip && pip install .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
