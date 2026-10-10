# Backend API image. NOTE: not built in the development session (no Docker
# daemon was available); see docs/KNOWN_LIMITATIONS.md.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IIOS_STORAGE_DIR=/var/lib/iios/storage

WORKDIR /app
RUN useradd --create-home --uid 10001 iios \
    && mkdir -p /var/lib/iios/storage \
    && chown -R iios /var/lib/iios

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

USER iios
EXPOSE 8000

# Migrations are idempotent; the API only starts if they succeed.
# FORWARDED_ALLOW_IPS must list ONLY the reverse proxy / frontend address.
CMD ["sh", "-c", "python -m app.cli migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
