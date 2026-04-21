# CNC Office v2 (VK bot + Nextcloud + DB Sync)

Этот проект — система учёта студентов с VK-ботом, где:

- бот работает по кнопкам (направления -> группы -> студенты -> действия),
- данные читаются/пишутся в PostgreSQL,
- таблица `.xlsx` синхронизируется с Nextcloud по WebDAV,
- изменения из БД отправляются обратно в Nextcloud через Celery (раз в 5 минут),
- есть nightly backup (БД + экспорт `.xlsx`) с ротацией, чтобы не забивать диск.

---

## 1) Архитектура простыми словами

1. Пользователь нажимает кнопки в VK-боте.
2. Бот обращается к Django API (`/api/bot/gateway/`) с секретом.
3. API меняет данные в `SectionTable.content` в PostgreSQL.
4. При изменении ставится флаг `needs_nextcloud_push=True`.
5. `celery_beat` раз в 5 минут запускает `push_pending_nextcloud`.
6. `celery_worker` пушит изменения в Nextcloud `.xlsx` через WebDAV.
7. Пуш идёт в режиме merge: сохраняются формат, ширины столбцов и «чужие» листы.

---

## 2) Что нужно на новом сервере

- Ubuntu/Debian сервер
- доступ по SSH
- Docker + Docker Compose plugin
- домен или IP
- рабочий Nextcloud WebDAV доступ к `.xlsx`
- VK group token + group id

---

## 3) Установка Docker (один раз)

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

---

## 4) Клонирование проекта

```bash
cd ~
git clone https://github.com/Gleb-Pinchuk/CNC_office.git cnc_office_v2
cd ~/cnc_office_v2
```

Если деплоите не `main`, а рабочую ветку:

```bash
git fetch --all
git checkout feature/student-monitoring-vk-celery
git pull
```

---

## 5) Настройка `.env`

```bash
cp .env.example .env
nano .env
```

Минимально важные переменные:

- Django/security:
  - `DEBUG=False`
  - `SECRET_KEY=<длинный-случайный>`
  - `ALLOWED_HOSTS=<IP или домен>,localhost,127.0.0.1,web`
- DB:
  - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- VK:
  - `VK_TOKEN`, `VK_GROUP_ID`
  - `CNC_BOT_API_SECRET`
  - `CNC_BOT_TABLE_OWNER_USERNAME`
  - `CNC_SECTION_TYPE=rangers`
  - `CNC_TABLE_TITLE_FRAGMENT=киберрейнджеры`
  - `CNC_DIRECTION_SHEETS=ЧПУ,РОБО,Аэро,микро`
- Таблица/колонки:
  - `BOT_SHEET_FIO_COL`
  - `BOT_SHEET_GROUP_COL`
  - `BOT_SHEET_STATUS_COL`
  - `BOT_SHEET_REMARK_COL`
  - `BOT_SHEET_SOCIAL_COLS`
- Nextcloud WebDAV:
  - `NEXTCLOUD_BASE_URL=https://...`
  - `NEXTCLOUD_USERNAME=...`
  - `NEXTCLOUD_PASSWORD=...`
  - `NEXTCLOUD_FILE_PATH=Киберрейнджеры_Производственная_группа.xlsx`
- Celery/Redis:
  - `CELERY_BROKER_URL=redis://redis:6379/0`
  - `CELERY_RESULT_BACKEND=redis://redis:6379/0`

### Проверка WebDAV перед запуском

```bash
curl -i --user 'LOGIN:PASSWORD' \
  -X PROPFIND -H 'Depth: 1' \
  'https://YOUR_CLOUD/remote.php/dav/files/LOGIN/'
```

Успех = `HTTP/2 207`.

---

## 6) Первый запуск проекта

```bash
cd ~/cnc_office_v2
docker compose up -d --build
docker compose ps
```

Проверить, что сервисы `Up`:

- `db`
- `redis`
- `web`
- `celery_worker`
- `celery_beat`
- `vk_bot`

Прогнать миграции:

```bash
docker compose exec web python manage.py migrate
```

---

## 7) Импорт таблицы из Nextcloud в БД

Первичная загрузка `.xlsx` в `SectionTable`:

```bash
docker compose exec web python manage.py import_nextcloud_table --force
```

Проверка, что листы распознаны:

```bash
docker compose exec web python manage.py inspect_section_table
```

Ожидаемо: 4 листа (направления) и реальные `rows/cols` (не заглушка 11x4).

---

## 8) Перезапуск бота после настройки

```bash
docker compose restart vk_bot
docker compose logs -f vk_bot
```

Быстрый UX-тест в VK:

1. `🎓 Направления`
2. выбрать направление
3. `📋 Группы`
4. выбрать группу
5. `👤 Студент`
6. открыть карточку студента
7. действия: замечание / замечаний нет / статус / выбор даты

---

## 9) Как работает запись замечаний

- Замечание пишется в колонку недели, определяемую по дате (автовыбор).
- В ячейке хранится **только текст замечания** или `замечаний нет`.
- Дата не добавляется в текст ячейки (дата определяется самой недельной колонкой).

---

## 10) Синхронизация с Nextcloud

### Автоматически

- `celery_beat` каждые 5 минут запускает push pending изменений.

### Вручную

```bash
# Принудительно отправить изменения из БД в Nextcloud
docker compose exec web python manage.py sync_nextcloud_sheet --push --force-push

# Принудительно подтянуть актуальный файл из Nextcloud в БД
docker compose exec web python manage.py sync_nextcloud_sheet --pull
```

---

## 10.1) Как забрать `.xlsx` из БД, если Nextcloud недоступен

Экспорт из БД в файл на сервере:

```bash
docker compose exec web python manage.py export_section_table_xlsx --output /app/backups/manual_export.xlsx
```

Файл появится на сервере в:

```bash
~/cnc_office_v2/backups/manual_export.xlsx
```

Скачать файл на свой компьютер (выполнять у себя локально):

```bash
scp utond1@<SERVER_IP>:/home/utond1/cnc_office_v2/backups/manual_export.xlsx .
```

---

## 11) Nightly backup (чтобы не потерять данные)

Скрипт: `ops/nightly_backup.sh`

Что делает:

1. Дамп PostgreSQL в `db_YYYY-MM-DD_HH-MM-SS.sql.gz`
2. Экспорт `SectionTable` в `section_table_YYYY-MM-DD_HH-MM-SS.xlsx`
3. Опциональный upload в S3
4. Удаление старых backup-файлов (`RETENTION_DAYS`, по умолчанию 14)

### Ручной запуск

```bash
cd ~/cnc_office_v2
chmod +x ops/nightly_backup.sh
./ops/nightly_backup.sh
```

### Автозапуск по cron (каждую ночь в 02:30)

```bash
crontab -e
```

Добавьте строку:

```cron
30 2 * * * cd /home/utond1/cnc_office_v2 && /bin/bash ./ops/nightly_backup.sh >> /home/utond1/cnc_office_v2/logs/nightly_backup.log 2>&1
```

### Параметры скрипта (опционально)

- `RETENTION_DAYS=14`
- `S3_BUCKET=your-bucket`
- `S3_PREFIX=cnc-office/nightly`

Если `S3_BUCKET` не задан или нет `aws` cli, upload пропускается.

---

## 12) OIDC (простыми словами)

OIDC = вход через внешний провайдер (единая авторизация), вместо локальных паролей в проекте.

Включить:

1. В `.env` поставить `ENABLE_OIDC=true`
2. Заполнить:
   - `OIDC_RP_CLIENT_ID`
   - `OIDC_RP_CLIENT_SECRET`
   - `OIDC_OP_AUTHORIZATION_ENDPOINT`
   - `OIDC_OP_TOKEN_ENDPOINT`
   - `OIDC_OP_USER_ENDPOINT`
3. Перезапустить `web`:

```bash
docker compose up -d --force-recreate web
```

---

## 13) Обновление проекта на сервере

```bash
cd ~/cnc_office_v2
git pull
docker compose up -d --build
docker compose exec web python manage.py migrate
```

После изменений в bot/web/sync обычно достаточно:

```bash
docker compose up -d --force-recreate web celery_worker celery_beat vk_bot
```

---

## 14) Диагностика проблем

### Бот не видит направления

```bash
docker compose exec web python manage.py inspect_section_table
```

Если листов 0 — проблема с импортом/структурой таблицы.

### WebDAV ошибка 401

Проверить логин/пароль curl-командой (`PROPFIND`). Должно быть `207`.

### Изменения не доходят в Nextcloud

```bash
docker compose logs --tail=120 celery_worker
docker compose logs --tail=80 celery_beat
docker compose exec web python manage.py sync_nextcloud_sheet --push --force-push
```

### Формат таблицы «ломается»

Используйте актуальную версию кода: push теперь делает merge в существующий workbook (с сохранением формата).

---

## 15) Безопасность (обязательно)

- `DEBUG=False`
- сильный `SECRET_KEY`
- не хранить секреты в git
- ограничить `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`
- включить secure cookies + HSTS в production
- использовать отдельного сервисного пользователя Nextcloud
- регулярно ротировать:
  - `VK_TOKEN`
  - `CNC_BOT_API_SECRET`
  - `NEXTCLOUD_PASSWORD`
- хранить nightly backups + желательно копию в S3

---

## 16) Полезные команды

```bash
# Статус контейнеров
docker compose ps

# Логи
docker compose logs -f web
docker compose logs -f vk_bot
docker compose logs -f celery_worker
docker compose logs -f celery_beat

# Поиск файла в Nextcloud
docker compose exec web python manage.py list_nextcloud_files --depth 4

# Инспекция таблицы в БД
docker compose exec web python manage.py inspect_section_table
```

---
Итог по безопасности
Вход снаружи в базовом compose отключен: порты не публикуются.
Прямой доступ к БД/Redis/Web из интернета: нет.
Исходящий интернет: есть у сервисов в app-network (включая vk_bot, web, celery).
Проект ориентирован на надежную работу даже при проблемах Nextcloud: данные продолжают жить в PostgreSQL, а синхронизация догоняет после восстановления облака.
