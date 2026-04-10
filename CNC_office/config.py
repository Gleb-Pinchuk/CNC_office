import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials (получить на https://my.telegram.org)
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

# TikTok settings
TIKTOK_SESSION = os.getenv("TIKTOK_SESSION", "")

# Proxy для доступа к зарубежным серверам
PROXY_URL = os.getenv("PROXY_URL", "")  # например: http://user:pass@proxy_ip:port

# Пути к данным
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TRAINING_DATA_DIR = os.path.join(DATA_DIR, "training_data")

# Файл со студентами
STUDENTS_FILE = os.path.join(DATA_DIR, "students.csv")

# Настройки модели
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(MODELS_DIR, "content_model.pth"))
import torch
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Категории запрещенного контента
FORBIDDEN_CATEGORIES = [
    "violence",      # насилие
    "adult",         # контент 18+
    "drugs",         # наркотики
    "hate_speech",   # разжигание ненависти
    "self_harm"      # причинение вреда себе
]

# Порог уверенности модели (0.0 - 1.0)
CONFIDENCE_THRESHOLD = 0.75

# Таймауты
REQUEST_TIMEOUT = 30
VIDEO_DOWNLOAD_TIMEOUT = 60
