# CNC_office

CNC_office - это Django-проект для хранения файлов и документов с REST API, веб-интерфейсом, PostgreSQL, Nginx и VK-ботом.

## Стек

- Django + DRF
- PostgreSQL
- Docker Compose
- Nginx
- VK bot
- pytest, flake8, black

## Быстрый старт

```bash
git clone https://github.com/Gleb-Pinchuk/CNC_office.git
cd CNC_office
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

После запуска:

- Админка: `http://localhost:8002/admin/`
- API: `http://localhost:8002/api/`
- Веб-интерфейс: `http://localhost:8002/`

## Развертывание на сервере

Установка Docker:

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

Первый запуск:

```bash
git clone https://github.com/Gleb-Pinchuk/CNC_office.git
cd CNC_office
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

Обновление проекта:

```bash
cd ~/cnc_office_v2
git pull origin develop
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

Если настроен GitHub Actions, деплой может выполняться автоматически после пуша в `develop`.

## Полезные команды

Проверка flake8:

```bash
docker compose exec web sh -lc "flake8 api bot_api config documents files sections users vk_student_bot manage.py conftest.py --jobs 1"
```

Форматирование black:

```bash
docker compose exec web sh -lc "black manage.py vk_student_bot/bot.py"
```

Тесты:

```bash
docker compose exec web pytest
```

Логи:

```bash
docker compose logs -f web
docker compose logs -f nginx
docker compose logs -f vk_bot
```

## Переменные окружения

Основные переменные в `.env`:

- `SECRET_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `VK_TOKEN`
- `VK_GROUP_ID`
- `CNC_BOT_API_SECRET`

## Доступ на сервере

- Админка: `http://<IP_СЕРВЕРА>:8002/admin/`
- API: `http://<IP_СЕРВЕРА>:8002/api/`
- Веб-интерфейс: `http://<IP_СЕРВЕРА>:8002/`

Пример рабочего адреса:

- `http://83.166.236.188:8081/admin/login/?next=/admin/`

## Лицензия

Проект создан в учебных целях. Использование кода допускается с указанием авторства.
