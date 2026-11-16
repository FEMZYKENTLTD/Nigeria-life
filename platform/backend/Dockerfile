# Nigeria Life Intelligence Engine — backend container
#
# Build from the repository root:
#   docker build -f platform/backend/Dockerfile -t rice-engine .
#
# Run (full multi-user mode against Supabase):
#   docker run -d -p 8787:8787 \
#     -e RICE_DB_URL="postgresql+asyncpg://postgres:***@db.x.supabase.co/postgres" \
#     -e RICE_SUPABASE_URL="https://x.supabase.co" \
#     -e RICE_SUPABASE_JWT_SECRET="***" \
#     -e RICE_ADMIN_EMAILS="you@example.com" \
#     -e RICE_DATA_DIR=/data \
#     -v rice-data:/data \
#     rice-engine
#
# Evidence files / screenshots / backups live under RICE_DATA_DIR — mount a
# persistent volume there. The DB itself lives in Supabase Postgres.

FROM python:3.11-slim AS runtime

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY platform/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY platform/backend/app ./app

# Browser binaries are optional: the engine degrades honestly to manual
# evidence import when they are absent. Enable real browser capture with:
#   docker build --build-arg INSTALL_BROWSERS=1 ...
ARG INSTALL_BROWSERS=0
RUN if [ "$INSTALL_BROWSERS" = "1" ]; then \
      playwright install --with-deps chromium; \
    else \
      echo "browser binaries skipped (set --build-arg INSTALL_BROWSERS=1 to include)"; \
    fi

ENV RICE_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
