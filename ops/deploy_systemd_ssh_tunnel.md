# Перенос CNC Office без Docker: Alpine/OpenRC + SSH tunnel

Целевая схема:

- `ssh -p 2222 root@92.255.253.148` - сервер приложения, Django, Celery, Redis, VK-бот.
- `ssh -p 2223 root@92.255.253.148` - сервер PostgreSQL.
- PostgreSQL не публикуется наружу. App-сервер подключается к нему через локальный SSH-туннель `127.0.0.1:15432 -> 127.0.0.1:5432`.
- Веб-интерфейс наружу не открывается. Django слушает только `127.0.0.1:8000`, VK-бот ходит в `http://127.0.0.1:8000/api`.
- Серверы определены как Alpine Linux, поэтому используются `apk` и OpenRC: `rc-service`, `rc-update`.

## 1. Подготовить DB-сервер

Подключиться:

```bash
ssh -p 2223 root@92.255.253.148
```

Установить PostgreSQL:

```bash
apk update
apk add postgresql16 postgresql16-client
/etc/init.d/postgresql setup
rc-update add postgresql default
rc-service postgresql start
```

Создать пользователя и БД. Замените пароль на реальный сильный пароль:

```bash
su postgres -c psql
```

```sql
CREATE USER cnc_user WITH PASSWORD 'CHANGE_ME_STRONG_DB_PASSWORD';
CREATE DATABASE cnc_office OWNER cnc_user;
GRANT ALL PRIVILEGES ON DATABASE cnc_office TO cnc_user;
\q
```

Оставить PostgreSQL доступным только локально:

```bash
PG_CONF="$(ls /var/lib/postgresql/*/data/postgresql.conf | head -n 1)"
grep -n "listen_addresses" "$PG_CONF"
sed -i "s/^#listen_addresses.*/listen_addresses = 'localhost'/" "$PG_CONF"
rc-service postgresql restart
netstat -lntp | grep 5432
```

Ожидаемо: PostgreSQL слушает `127.0.0.1:5432`.

## 2. Подготовить app-сервер

Подключиться:

```bash
ssh -p 2222 root@92.255.253.148
```

Установить пакеты:

```bash
apk update
apk add bash python3 py3-pip python3-dev build-base postgresql-dev postgresql16-client redis git curl openssh-client rsync
rc-update add redis default
rc-service redis start
```

Создать сервисного пользователя и директории:

```bash
adduser -S -D -h /home/cnc -s /bin/bash cnc || true
mkdir -p /opt/cnc_office /etc/cnc-office
chown -R cnc:cnc /opt/cnc_office /etc/cnc-office
```

Загрузить код. Если используете git:

```bash
su cnc -c "git clone https://github.com/Gleb-Pinchuk/CNC_office.git /opt/cnc_office"
cd /opt/cnc_office
su cnc -c "cd /opt/cnc_office && git checkout main"
```

Если переносите текущую рабочую папку вручную, используйте `rsync` с локальной машины:

```bash
rsync -av --exclude .git --exclude .venv --exclude __pycache__ -e "ssh -p 2222" ./ root@92.255.253.148:/opt/cnc_office/
ssh -p 2222 root@92.255.253.148 "chown -R cnc:cnc /opt/cnc_office"
```

Создать виртуальное окружение и поставить зависимости:

```bash
cd /opt/cnc_office
su cnc -c "cd /opt/cnc_office && python3 -m venv .venv"
su cnc -c "cd /opt/cnc_office && .venv/bin/pip install --upgrade pip"
su cnc -c "cd /opt/cnc_office && .venv/bin/pip install -r requirements.txt"
su cnc -c "cd /opt/cnc_office && .venv/bin/pip install -r vk_student_bot/requirements.txt"
chmod +x /opt/cnc_office/ops/start_gunicorn_systemd.sh
chmod +x /opt/cnc_office/ops/start_web_openrc.sh
```

## 3. Настроить SSH-туннель к БД

На app-сервере создать ключ:

```bash
su cnc -c "mkdir -p /home/cnc/.ssh"
su cnc -c "chmod 700 /home/cnc/.ssh"
su cnc -c "ssh-keygen -t ed25519 -f /home/cnc/.ssh/cnc_db_tunnel -N ''"
su cnc -c "cat /home/cnc/.ssh/cnc_db_tunnel.pub"
```

Скопировать выведенный публичный ключ на DB-сервер в `/root/.ssh/authorized_keys`:

```bash
ssh -p 2223 root@92.255.253.148
mkdir -p /root/.ssh
chmod 700 /root/.ssh
nano /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

Проверить вход с app-сервера:

```bash
su cnc -c "ssh -i /home/cnc/.ssh/cnc_db_tunnel -p 2223 root@92.255.253.148 'echo tunnel-ok'"
```

## 4. Создать env-файл

На app-сервере:

```bash
cp /opt/cnc_office/ops/app.env.example /etc/cnc-office/app.env
nano /etc/cnc-office/app.env
chmod 600 /etc/cnc-office/app.env
chown root:root /etc/cnc-office/app.env
```

Минимально обязательно заменить:

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `VK_TOKEN`
- `VK_GROUP_ID`
- `CNC_BOT_API_SECRET` и `CNC_BOT_SECRET` на одинаковое значение
- `NEXTCLOUD_BASE_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_APP_TOKEN` или `NEXTCLOUD_PASSWORD`, `NEXTCLOUD_FILE_PATH`
- `CNC_BOT_TABLE_OWNER_USERNAME`
- `CNC_DIRECTION_SHEETS`, если названия листов отличаются

Для выбранной схемы должны остаться:

```env
DB_HOST=127.0.0.1
DB_PORT=15432
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
CNC_API_BASE=http://127.0.0.1:8000/api
DB_TUNNEL_HOST=92.255.253.148
DB_TUNNEL_SSH_PORT=2223
```

## 5. Установить OpenRC-сервисы

На app-сервере:

```bash
cp /opt/cnc_office/ops/openrc/* /etc/init.d/
chmod +x /etc/init.d/cnc-*
rc-update add cnc-db-tunnel default
rc-service cnc-db-tunnel start
```

Проверить туннель:

```bash
rc-service cnc-db-tunnel status
pg_isready -h 127.0.0.1 -p 15432 -U cnc_user -d cnc_office
```

Если `pg_isready` пишет `accepting connections`, можно запускать приложение:

```bash
rc-update add cnc-office-web default
rc-update add cnc-office-celery-worker default
rc-update add cnc-office-celery-beat default
rc-update add cnc-vk-bot default
rc-service cnc-office-web start
rc-service cnc-office-celery-worker start
rc-service cnc-office-celery-beat start
rc-service cnc-vk-bot start
```

## 6. Первичная инициализация

Миграции и статика запускаются в `cnc-office-web` перед Gunicorn. Если нужно выполнить вручную:

```bash
cd /opt/cnc_office
set -a
. /etc/cnc-office/app.env
set +a
su cnc -c "cd /opt/cnc_office && .venv/bin/python manage.py migrate --noinput"
su cnc -c "cd /opt/cnc_office && .venv/bin/python manage.py collectstatic --noinput --clear"
```

Первично импортировать таблицу из Nextcloud:

```bash
cd /opt/cnc_office
set -a
. /etc/cnc-office/app.env
set +a
su cnc -c "cd /opt/cnc_office && .venv/bin/python manage.py import_nextcloud_table --force"
su cnc -c "cd /opt/cnc_office && .venv/bin/python manage.py inspect_section_table"
```

## 7. Проверки

На app-сервере:

```bash
set -a
. /etc/cnc-office/app.env
set +a
curl -s http://127.0.0.1:8000/api/ | head
curl -s -H "X-CNC-Bot-Token: $CNC_BOT_API_SECRET" http://127.0.0.1:8000/api/bot/health/
rc-service cnc-office-web status
rc-service cnc-office-celery-worker status
rc-service cnc-office-celery-beat status
rc-service cnc-vk-bot status
tail -f /var/log/cnc-office/cnc-vk-bot.log
```

С локального компьютера, если нужно открыть интерфейс в браузере:

```bash
ssh -p 2222 -L 8000:127.0.0.1:8000 root@92.255.253.148
```

После этого открыть `http://127.0.0.1:8000` на локальном компьютере.

## 8. Перенос данных из старого Docker-окружения

Если старый проект ещё работает в Docker, сделать дамп:

```bash
docker compose exec -T db sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > cnc_office.sql
```

Загрузить дамп на DB-сервер:

```bash
scp -P 2223 cnc_office.sql root@92.255.253.148:/root/cnc_office.sql
ssh -p 2223 root@92.255.253.148
su postgres -c "psql -d cnc_office -f /root/cnc_office.sql"
```

Если переносите `media`, скопировать на app-сервер:

```bash
rsync -av -e "ssh -p 2222" ./media/ root@92.255.253.148:/opt/cnc_office/media/
ssh -p 2222 root@92.255.253.148 "chown -R cnc:cnc /opt/cnc_office/media"
```

## 9. Обновление кода

```bash
ssh -p 2222 root@92.255.253.148
cd /opt/cnc_office
su cnc -c "cd /opt/cnc_office && git pull"
su cnc -c "cd /opt/cnc_office && .venv/bin/pip install -r requirements.txt"
su cnc -c "cd /opt/cnc_office && .venv/bin/pip install -r vk_student_bot/requirements.txt"
rc-service cnc-office-web restart
rc-service cnc-office-celery-worker restart
rc-service cnc-office-celery-beat restart
rc-service cnc-vk-bot restart
```

## 10. Диагностика

Логи:

```bash
tail -n 100 /var/log/cnc-office/cnc-db-tunnel.log
tail -n 100 /var/log/cnc-office/cnc-office-web.log
tail -n 100 /var/log/cnc-office/cnc-office-celery-worker.log
tail -n 100 /var/log/cnc-office/cnc-office-celery-beat.log
tail -n 100 /var/log/cnc-office/cnc-vk-bot.log
```

Ручная синхронизация Nextcloud:

```bash
cd /opt/cnc_office
set -a
. /etc/cnc-office/app.env
set +a
su cnc -c "cd /opt/cnc_office && .venv/bin/python manage.py sync_nextcloud_sheet --pull"
su cnc -c "cd /opt/cnc_office && .venv/bin/python manage.py sync_nextcloud_sheet --push --force-push"
```

Если Django не стартует из-за `documents`, значит на сервер попала версия кода без приложения `documents`. В этой ветке проект умеет стартовать без него, но раздел документов в веб-интерфейсе будет недоступен до восстановления приложения.
