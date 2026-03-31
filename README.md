## CNC_office

Облачное хранилище “как Synology” с онлайн‑редактором таблиц (мульти‑листы, стили, фильтры) и VK‑ботом для работы с таблицей внутри системы.

### Соответствие критериям
- **Доверенные домены/IP**: используются `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` через `.env` (см. `.env.example`).
- **Удалённый Git репозиторий**: проект ведётся в GitHub (push в `develop`, деплой через Actions на VM).
- **ORM без SQL**: Django ORM + PostgreSQL.
- **Сериализаторы**: DRF serializers.
- **PostgreSQL**: основной storage в `docker-compose.yml`.
- **DRF базовые классы**: ViewSet’ы (`ModelViewSet`, `ReadOnlyModelViewSet`) и actions.
- **django-filter**: подключён в `INSTALLED_APPS` (готов к использованию; для новых списков можно добавлять `filterset_fields`).
- **Docker / docker-compose**: `Dockerfile` + `docker-compose.yml` (web/db/nginx/vk_bot).
- **Тесты >75%**: pytest + pytest-django + pytest-cov (`pytest.ini`).

### Быстрый старт (локально)
1) Скопируйте пример окружения:

```bash
copy .env.example .env
```

2) Запуск:

```bash
docker compose up -d --build
```

3) Проверка:
- **UI**: `http://localhost:8002/`
- **API**: `http://localhost:8002/api/`

### Деплой на VM (Ubuntu, docker)
После push в `develop` (GitHub Actions) обычно достаточно:

```bash
cd ~/cnc_office_v2
git pull
docker compose up -d --build
docker compose logs web --tail=200
docker compose ps
```

### HTTPS (чтобы браузер показывал "Безопасно")
- Для IP `http://213.165.214.241:8002` браузер будет показывать "небезопасно". Нужен домен и TLS-сертификат.
- Выпустите сертификат Let's Encrypt для домена (например, `app.example.com`), затем используйте HTTPS-конфиг из репозитория.

1. Привяжите домен к серверу:
```bash
# DNS A-record
app.example.com -> 213.165.214.241
```

2. Получите сертификат на сервере:
```bash
sudo apt update
sudo apt install -y certbot
sudo certbot certonly --standalone -d app.example.com
```

3. В файле `nginx/nginx.https.conf` замените `YOUR_DOMAIN` на ваш домен.

4. Запускайте проект с HTTPS override:
```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
```

5. В `.env` для production включите HTTPS-настройки:
```env
ALLOWED_HOSTS=app.example.com,213.165.214.241,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=https://app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

### Управление общим доступом (read/write + revoke)
- **Выдать доступ**: в UI “Поделиться” → ввод username → выбрать режим (confirm) → `read` или `write`.
- **Снять доступ**: вкладка “Общий доступ” → кнопка `✖` у нужного элемента.
- **Сменить read/write**: вкладка “Общий доступ” → кнопка `👁️/✏️`.

### VK bot
Сервис `vk_bot` запускается в `docker-compose.yml` и ходит в API `web` по `CNC_API_BASE=http://web:8000/api`.

Ключевые переменные:
- `VK_TOKEN`, `VK_GROUP_ID`
- `CNC_BOT_API_SECRET` (заголовок `X-CNC-Bot-Token`)
- `CNC_BOT_TABLE_OWNER_USERNAME`
- `CNC_SECTION_TYPE`, `CNC_TABLE_TITLE_FRAGMENT`, `CNC_DIRECTION_SHEETS`

### Тесты и покрытие

```bash
pytest
```

Покрытие считается автоматически через `pytest.ini` (`pytest-cov`).
