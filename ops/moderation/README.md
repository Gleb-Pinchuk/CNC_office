# Отдельный проект AI-модерации (VM)

Этот compose-файл предназначен для запуска AI-модерации в отдельной VM, чтобы не нагружать основной сервер приложения.

## Что запускается

- `moderation_worker` — исполняет Celery-задачи модерации.
- `moderation_beat` — планировщик периодических запусков.

## Запуск

1. Скопируйте корневой `.env` и заполните настройки БД/Redis.
2. Включите переменные:
   - `SOCIAL_MODERATION_ENABLED=True`
   - `SOCIAL_MODERATION_SCHEDULE_MINUTES=180` (или чаще/реже)
   - `SOCIAL_MOD_MAX_STUDENTS_PER_RUN=50`
3. Запустите:

```bash
docker compose -f ops/moderation/docker-compose.yml up -d --build
```

## Ручной запуск dry-run

```bash
docker compose -f docker-compose.yml exec web python manage.py run_social_moderation --max-students 20
```

## Ручной запуск с записью в таблицу

```bash
docker compose -f docker-compose.yml exec web python manage.py run_social_moderation --apply --max-students 20
```

## Обучение правил

Добавить keyword:

```bash
docker compose -f docker-compose.yml exec web python manage.py train_social_moderation --add-keyword "новое_слово"
```

Добавить hash запрещенного изображения:

```bash
docker compose -f docker-compose.yml exec web python manage.py train_social_moderation --label blocked --image /app/path/to/file.jpg
```

