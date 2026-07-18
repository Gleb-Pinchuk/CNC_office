# Отдельный проект AI-модерации (VM)

Этот compose-файл предназначен для запуска AI-модерации в отдельной VM, чтобы не нагружать основной сервер приложения.

## Что запускается

- `moderation_worker` — исполняет Celery-задачи модерации.
- `moderation_beat` — планировщик периодических запусков.

Контейнеры подключаются к внешним Docker-сетям основного проекта:

- `cnc_office_app` (для `redis`)
- `cnc_office_db_internal` (для `db`)

## Запуск

1. Скопируйте корневой `.env` и заполните настройки БД/Redis.
2. Включите переменные:
   - `SOCIAL_MODERATION_ENABLED=True`
   - `SOCIAL_MODERATION_SCHEDULE_MINUTES=180` (или чаще/реже)
   - `SOCIAL_MOD_MAX_STUDENTS_PER_RUN=50`
   - при блокировках сети: `SOCIAL_MOD_PROXY_URL=http://user:pass@host:port`
   - по умолчанию только VK: `SOCIAL_MOD_SKIP_TG=True` и `SOCIAL_MOD_SKIP_TIKTOK=True`
   - **обязательно** user-токен: `SOCIAL_MOD_VK_USER_TOKEN=...` (токен сообщества `VK_TOKEN` не читает чужие стены — error 27)
   - запретные сообщества: `bot_api/moderation_data/banned_vk_groups.json`

### Токен для модерации VK

`VK_TOKEN` сообщества оставь для бота (сообщения). Для скана нужен отдельный **user access token** с правами примерно: `wall`, `groups`, `offline`.

1. Создай Standalone-приложение на [vk.com/apps?act=manage](https://vk.com/apps?act=manage).
2. Получи токен пользователя (служебный аккаунт организации, не личный педагога).
3. Пропиши в `/etc/cnc-office/app.env`:
   ```bash
   SOCIAL_MOD_VK_USER_TOKEN=vk1.a....
   ```
4. `rc-service cnc-office-celery-worker restart`
3. Запустите:

```bash
docker compose -f ops/moderation/docker-compose.yml up -d --build
```

## Ручной запуск dry-run

```bash
docker compose -f ops/moderation/docker-compose.yml exec moderation_worker python manage.py run_social_moderation --max-students 20
```

## Ручной запуск с записью в таблицу

```bash
docker compose -f ops/moderation/docker-compose.yml exec moderation_worker python manage.py run_social_moderation --apply --max-students 20
```

## Обучение правил

Добавить keyword:

```bash
docker compose -f ops/moderation/docker-compose.yml exec moderation_worker python manage.py train_social_moderation --add-keyword "новое_слово"
```

Добавить hash запрещенного изображения:

```bash
docker compose -f ops/moderation/docker-compose.yml exec moderation_worker python manage.py train_social_moderation --label blocked --image /app/path/to/file.jpg
```

