# Dockerfile
FROM python:3.12-slim-bookworm

# ✅ Настройка pip: используем стандартный PyPI + таймауты
RUN pip config set global.timeout 100 && \
    pip config set global.retries 10

# ✅ Установка системных пакетов с повторными попытками
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        postgresql-client \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ✅ Рабочая директория
WORKDIR /app

# ✅ Копируем requirements первым — для кэширования
COPY requirements.txt .

# ✅ Установка Python зависимостей с повторными попытками
RUN pip install --no-cache-dir --retries 10 --timeout 100 -r requirements.txt

# ✅ Копируем код проекта
COPY . .

# ✅ Копируем скрипт запуска и делаем исполняемым
COPY start /start
RUN chmod +x /start

# ✅ Создаём необходимые папки
RUN mkdir -p /app/media /app/staticfiles /app/logs && \
    chmod 755 /app/media /app/staticfiles /app/logs

# ✅ Открываем порт
EXPOSE 8000

# ✅ Запускаем через /start скрипт
CMD ["/start"]
