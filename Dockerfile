FROM python:3.12-slim

# Установка пакетов с очисткой
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev postgresql-client curl \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

WORKDIR /app

# ✅ Копируем requirements первым — для кэширования слоя pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Копируем код после установки зависимостей
COPY . .

# Создаём папки
RUN mkdir -p /app/media /app/staticfiles && chmod 755 /app/media /app/staticfiles

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
