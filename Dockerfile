# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Security: run as non-root user
RUN useradd -m appuser

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
