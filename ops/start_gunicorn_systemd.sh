#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/cnc_office}"
DJANGO_BIND="${DJANGO_BIND:-127.0.0.1:8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/staticfiles" "$PROJECT_DIR/media"

exec "$PROJECT_DIR/.venv/bin/gunicorn" config.wsgi:application \
  --bind "$DJANGO_BIND" \
  --workers "$GUNICORN_WORKERS" \
  --threads "$GUNICORN_THREADS" \
  --worker-class sync \
  --timeout "$GUNICORN_TIMEOUT" \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
