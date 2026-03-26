# ✅ Python + System Dependencies
FROM python:3.12-slim-bookworm

# ✅ Рабочая директория
WORKDIR /app

# ✅ Установка системных пакетов (ОБЯЗАТЕЛЬНО перед pip install!)
# 🔧 psycopg2 требует libpq-dev, build-essential для компиляции
RUN set -ex; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        postgresql-client \
        curl \
        git \
        wget \
        pkg-config \
        libffi-dev \
        libssl-dev \
    ; \
    rm -rf /var/lib/apt/lists/*; \
    apt-get clean;

# ✅ Обновление pip и установка зависимостей с повторными попытками
# 🔧 --no-cache-dir экономит место, --retries и --timeout для стабильности
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
        --retries 10 \
        --timeout 100 \
        --default-timeout 100 \
        -r requirements.txt || \
    pip install --no-cache-dir \
        --retries 10 \
        --timeout 100 \
        --default-timeout 100 \
        -r requirements.txt

# ✅ Копируем код проекта
COPY . .

# ✅ Создаём папки для статики, медиа и логов
RUN mkdir -p /app/staticfiles /app/media /app/logs

# ✅ Скрипт запуска
COPY docker-entrypoint.sh /start
RUN chmod +x /start

# ✅ Порт
EXPOSE 8000

# ✅ Команда по умолчанию
CMD ["/start"]