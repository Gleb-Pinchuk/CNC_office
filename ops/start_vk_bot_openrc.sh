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

# Сироты после rc-service stop / ручных запусков → тройные ответы в VK
pkill -f "${PROJECT_DIR}/vk_student_bot/bot.py" 2>/dev/null || true
pkill -f '[p]ython -u bot.py' 2>/dev/null || true
sleep 1

while true; do
  set +e
  "$PROJECT_DIR/.venv/bin/python" -u bot.py
  code=$?
  set -e
  if [ "${code}" -eq 99 ]; then
    echo "$(date -Iseconds 2>/dev/null || date) cnc-vk-bot: lock busy (another instance); retry in 30s" >&2
    sleep 30
    continue
  fi
  echo "$(date -Iseconds 2>/dev/null || date) cnc-vk-bot exited with code ${code}; restart in 5s" >&2
  sleep 5
done
