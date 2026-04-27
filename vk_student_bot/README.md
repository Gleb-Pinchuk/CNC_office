# VK-бот для таблиц CNC Office (раздел «Кибер-рейнджеры»)

Бот читает и меняет ячейки в **таблице раздела** (`SectionTable`) через HTTP API проекта CNC Office, **без Google Sheets**.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `VK_TOKEN` | Ключ сообщества VK (сохраняйте только в `.env`, не коммитьте). |
| `VK_GROUP_ID` | ID группы VK для long poll. |
| `CNC_API_BASE` | Базовый URL API: без Docker/systemd — `http://127.0.0.1:8000/api`; в Compose — `http://web:8000/api`. |
| `CNC_BOT_SECRET` | Тот же секрет, что `CNC_BOT_API_SECRET` в `.env` Django. |
| `CNC_SECTION_TYPE` | Код раздела: `rangers` (кибер-рейнджеры), `attendance`, `statements`. |
| `CNC_TABLE_TITLE_FRAGMENT` | Уникальный фрагмент названия таблицы (поиск `icontains`). |
| `CNC_DIRECTION_SHEETS` | Список имён листов-направлений через запятую. |
| `TIMEZONE` | Часовой пояс для определения «текущей недели» в заголовках (`Europe/Moscow`). |

## Настройка Django

В `.env` **веб-приложения** добавьте:

```
CNC_BOT_API_SECRET=длинный_случайный_секрет
CNC_BOT_TABLE_OWNER_USERNAME=логин_пользователя_владельца_таблицы
```

Владелец — тот аккаунт, под которым в CNC Office создана таблица «киберрейнджеры…».

## Запуск вместе с Docker Compose

В корне проекта CNC_office в `docker-compose.yml` уже может быть сервис `vk_bot`. После `docker compose up -d`:

1. Убедитесь, что в общем `.env` заданы `CNC_BOT_API_SECRET`, `CNC_BOT_TABLE_OWNER_USERNAME`, а также переменные `vk_student_bot` (или продублируйте их в `environment` сервиса).
2. Бот обращается к `http://web:8000/api/bot/gateway/` внутри сети Compose.

## Запуск через systemd без Docker

Для переноса на два сервера используйте инструкцию `ops/deploy_systemd_ssh_tunnel.md`. В этом режиме бот запускается сервисом `cnc-vk-bot.service` и обращается к локальному API:

```bash
CNC_API_BASE=http://127.0.0.1:8000/api
```

Проверка:

```bash
curl -s -H "X-CNC-Bot-Token: ВАШ_СЕКРЕТ" "http://127.0.0.1:8000/api/bot/health/"
```

## Локальный запуск без Docker

```bash
cd vk_student_bot
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
set CNC_API_BASE=http://127.0.0.1:8000/api
set CNC_BOT_SECRET=...
set VK_TOKEN=...
python bot.py
```

## API бота (для отладки)

`POST /api/bot/gateway/` с заголовком `X-CNC-Bot-Token` и телом JSON:

- `{"action": "lookup_table", "section_type": "rangers", "title_contains": "кибер"}`
- `{"action": "list_sheets", "table_id": 1}`
- `{"action": "get_sheet_data", "table_id": 1, "sheet_name": "ЧПУ"}`
- `{"action": "set_cell", "table_id": 1, "sheet_name": "ЧПУ", "row": 1, "col": 5, "value": "текст"}`

Индексы `row` и `col` **с нуля** (строка 0 — заголовки, как в редакторе).

## Безопасность

Не публикуйте `VK_TOKEN` и `CNC_BOT_SECRET`. Если ключ попал в чат или git — отзовите и выпустите новые.
