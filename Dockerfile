# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim

WORKDIR /app

# LibreOffice headless — server-side .doc -> .docx conversion (Phase 13,
# src/services/doc_tai_lieu.py::_chuyen_doc_sang_docx). `libreoffice-writer`
# pulls the Writer component and its core deps, not the ~600 MB `libreoffice`
# metapackage (Calc/Impress/Draw are dead weight for a service that only ever
# converts Word documents). Metric-compatible stand-ins so a form's layout
# doesn't reflow just because the exact font isn't installed:
# `fonts-liberation` for Times New Roman/Arial/Courier New,
# `fonts-crosextra-carlito`/`-caladea` for Calibri/Cambria.
# soffice runs with its proxy pointed at the dead port 127.0.0.1:9 so linked
# content in uploads is never fetched: nothing in this image may listen there.
# `poppler-utils` (pdftoppm) renders page images; `tesseract-ocr` +
# `tesseract-ocr-vie` read scanned pages (decision 2026-09-26, khuôn gốc).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer fonts-liberation \
        fonts-crosextra-carlito fonts-crosextra-caladea \
        poppler-utils tesseract-ocr tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

# Security: run as non-root user. Create it BEFORE copying the packages so the
# user-site install lands in appuser's own home: pip --user in the builder wrote
# to /root/.local, which is 0700 and unreadable once USER switches — the
# container then dies with "exec /root/.local/bin/uvicorn: Permission denied".
RUN useradd -m appuser

# Copy installed packages from builder into appuser's user-site
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Copy application code
COPY . .

# Create data directory with correct ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# --no-proxy-headers: uvicorn defaults to proxy_headers=True with
# forwarded_allow_ips="127.0.0.1", so ProxyHeadersMiddleware replaces
# scope["client"] with the caller-supplied X-Forwarded-For value BEFORE any
# line of src/ runs. That silently defeats bao_ve.ip_goi's do-not-trust
# policy one layer below it, turning per-IP rate limiting into decoration.
# Re-enable only behind a real reverse proxy, and then via
# KLAW_TIN_PROXY_HEADER + KLAW_SO_HOP_PROXY_TIN_CAY so one place decides.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
