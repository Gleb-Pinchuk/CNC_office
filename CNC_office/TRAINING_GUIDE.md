# Руководство по обучению ИИ-модератора

## Структура данных для обучения

```
data/training_data/
├── allowed/           # Безопасный контент (примеры одобренных фото/видео)
│   ├── image1.jpg
│   └── image2.png
└── forbidden/         # Запрещенный контент по категориям
    ├── violence/      # Насилие
    ├── adult/         # Контент 18+
    ├── drugs/         # Наркотики
    ├── hate_speech/   # Разжигание ненависти
    └── self_harm/     # Причинение вреда себе
```

## Шаг 1: Сбор данных

### Для запрещенного контента:
1. Соберите примеры изображений/кадров из видео для каждой категории
2. Поместите файлы в соответствующие папки `data/training_data/forbidden/{category}/`

### Для безопасного контента:
1. Соберите примеры разрешенных изображений
2. Поместите в `data/training_data/allowed/`

## Шаг 2: Добавление размеченных данных

```bash
# Добавить примеры насилия
python main.py --add-labeled --path /path/to/violence/images --category violence

# Добавить примеры контента 18+
python main.py --add-labeled --path /path/to/adult/images --category adult

# Добавить безопасные изображения
python main.py --add-labeled --path /path/to/safe/images --category any --allowed
```

## Шаг 3: Обучение модели

```bash
# Базовое обучение
python main.py --train --data data/training_data/ --epochs 10 --batch-size 16

# Расширенное обучение с валидацией
python -c "
from modules.trainer import ContentTrainer
trainer = ContentTrainer()
trainer.train(
    train_dir='data/training_data/',
    val_dir='data/validation_data/',  # опционально
    epochs=20,
    batch_size=32,
    learning_rate=0.001
)
"
```

## Шаг 4: Проверка качества модели

```bash
# Тестирование на примерах
python -c "
from modules.content_analyzer import ContentAnalyzer
analyzer = ContentAnalyzer()

# Проверить тестовое изображение
result = analyzer.analyze_image('test_image.jpg')
print(result)
"
```

## Рекомендации по обучению

### Минимальный набор данных:
- **50-100 изображений** на каждую категорию запрещенного контента
- **200-500 изображений** безопасного контента

### Для лучшего качества:
- **500+ изображений** на категорию
- Разнообразные примеры (разное освещение, ракурсы, качество)
- Сбалансированный датасет

### Аугментация данных:
Для увеличения датасета можно использовать аугментацию:
- Повороты, отражения
- Изменение яркости/контраста
- Кадрирование
- Добавление шума

## Дообучение модели

Можно дообучать модель на новых данных без полного переобучения:

```bash
# Добавить новые данные
python main.py --add-labeled --path new_samples/violence/ --category violence

# Дообучить (меньше эпох)
python main.py --train --data data/training_data/ --epochs 5
```

## Мониторинг качества

После обучения проверяйте:
1. **Precision** - сколько найденных нарушений действительно являются нарушениями
2. **Recall** - сколько реальных нарушений было найдено
3. **F1-score** - баланс между precision и recall

При необходимости:
- Увеличьте датасет
- Настройте `CONFIDENCE_THRESHOLD` в config.py
- Добавьте больше разнообразных примеров
