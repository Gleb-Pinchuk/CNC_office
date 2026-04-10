# CNC Office - AI Content Moderator

Система автоматической модерации контента студентов из Telegram и TikTok.

## Возможности

- Подключение к Telegram и TikTok через API/прокси
- Проверка фото и видео на запрещенный контент
- Обучение модели на новых данных
- Интеграция с таблицами студентов
- Логирование результатов проверок

## Структура проекта

```
CNC_office/
├── modules/
│   ├── telegram_client.py      # Клиент для Telegram
│   ├── tiktok_client.py        # Клиент для TikTok
│   ├── content_analyzer.py     # Анализ контента (изображения/видео)
│   ├── student_db.py           # Работа с базой студентов
│   └── trainer.py              # Обучение модели
├── data/
│   └── training_data/          # Данные для обучения
├── models/                     # Сохранённые модели
├── logs/                       # Логи работы
├── config.py                   # Конфигурация
├── main.py                     # Главный скрипт
└── requirements.txt            # Зависимости
```

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Создайте файл `.env` с вашими ключами:
```
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TIKTOK_SESSION=session_id
PROXY_URL=http://proxy:port
MODEL_PATH=models/content_model.pth
```

2. Заполните таблицу студентов в `data/students.csv`

## Использование

```bash
# Запуск проверки всех студентов
python main.py --check-all

# Проверка конкретного студента
python main.py --username @student_name

# Обучение модели на новых данных
python main.py --train --data data/training_data/new_samples/

# Добавление размеченных данных
python main.py --add-labeled --path data/training_data/labeled/
```

## Обучение ИИ

Система поддерживает дообучение на новых данных:

1. Соберите примеры контента в `data/training_data/`
2. Разметьте данные (подпапки: `allowed/`, `forbidden/`)
3. Запустите обучение: `python main.py --train`

## Требования

- Python 3.9+
- Прокси для доступа к зарубежным сервисам
- GPU рекомендуется для обучения
