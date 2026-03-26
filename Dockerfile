# ✅ Python + System Dependencies
FROM python:3.12-slim-bookworm

# ✅ Рабочая директория
WORKDIR /app

# ✅ 1. Сначала копируем requirements.txt (для кэширования слоя pip)
COPY requirements.txt .

# ✅ 2. Установка системных пакетов (ОБЯЗАТЕЛЬНО перед pip install!)
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

# ✅ 3. Обновление pip и установка зависимостей
# 🔧 Используем зеркало для стабильности в РФ
RUN pip install --upgrade pip setuptools wheel && \
    pip config set global.index-url https://pypi.org/simple && \
    pip install --no-cache-dir \
        --retries 10 \
        --timeout 100 \
        --default-timeout 100 \
        -r requirements.txt

# ✅ 4. Копируем ВЕСЬ код проекта (после pip install!)
COPY . .

# ✅ 5. Создаём папки для статики, медиа и логов
RUN mkdir -p /app/staticfiles /app/media /app/logs

# ✅ 6. Скрипт запуска
COPY docker-entrypoint.sh /start
RUN chmod +x /start

# ✅ Порт
EXPOSE 8000

# ✅ Команда по умолчанию
CMD ["/start"]