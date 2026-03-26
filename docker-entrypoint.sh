#!/bin/bash
# docker-entrypoint.sh - Точка входа для Docker контейнера

set -e

echo "🚀 Starting CNC Office..."

# Применяем миграции (если не применены)
echo "📦 Applying migrations..."
python manage.py migrate --noinput

# Собираем статику
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Запускаем Gunicorn
echo "🔥 Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info