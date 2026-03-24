# Dockerfile
FROM python:3.12-slim

# ✅ Настройка pip: зеркало + таймауты + отключение кэша
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.timeout 1000 && \
    pip config set global.retries 10

# ✅ Установка системных пакетов с очисткой
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ✅ Рабочая директория
WORKDIR /app

# ✅ Копируем requirements первым — для кэширования слоя pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

# ✅ Запускаем через /start скрипт (вместо прямого gunicorn)
CMD ["/start"]
