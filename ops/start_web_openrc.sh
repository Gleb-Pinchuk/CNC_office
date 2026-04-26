#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/cnc-office/app.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PROJECT_DIR="${PROJECT_DIR:-/opt/cnc_office}"
cd "$PROJECT_DIR"

"$PROJECT_DIR/.venv/bin/python" manage.py migrate --noinput
"$PROJECT_DIR/.venv/bin/python" manage.py collectstatic --noinput --clear

exec "$PROJECT_DIR/ops/start_gunicorn_systemd.sh"
