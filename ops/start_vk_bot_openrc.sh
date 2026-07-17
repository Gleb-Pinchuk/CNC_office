#!/usr/bin/env bash
# Обёртка OpenRC: при любом выходе bot.py перезапускаем (crash / hard watchdog exit).
set -uo pipefail

ENV_FILE="${ENV_FILE:-/etc/cnc-office/app.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PROJECT_DIR="${PROJECT_DIR:-/opt/cnc_office}"
cd "$PROJECT_DIR/vk_student_bot"

while true; do
  set +e
  "$PROJECT_DIR/.venv/bin/python" -u bot.py
  code=$?
  set -e
  echo "$(date -Iseconds 2>/dev/null || date) cnc-vk-bot exited with code ${code}; restart in 5s" >&2
  sleep 5
done
