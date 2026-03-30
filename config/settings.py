"""
Django settings for config project.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-k+6l5pe((b=%)u1kzr5do+sch9#iker1i5=t+7++yuim=+_+^d')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS_ENV = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(',') if h.strip()] if ALLOWED_HOSTS_ENV else ['*']

# ✅ Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',

    # Local apps
    'files',
    'users',
    'documents',
    'sections',
    'bot_api',
]

# Токен для VK-бота (заголовок X-CNC-Bot-Token) и пользователь-владелец таблиц разделов
CNC_BOT_API_SECRET = os.getenv('CNC_BOT_API_SECRET', '')
CNC_BOT_TABLE_OWNER_USERNAME = os.getenv('CNC_BOT_TABLE_OWNER_USERNAME', '')

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ✅ Templates: index.html для SPA
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ✅ Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'cnc_office'),
        'USER': os.getenv('POSTGRES_USER', 'cnc_user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'cnc_password'),
        'HOST': os.getenv('DB_HOST', 'db'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# ✅ Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ✅ Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# ✅ Static files (для SPA + vendor)
STATICFILES_DIRS = [
    BASE_DIR / 'frontend',
    BASE_DIR / 'frontend/vendor',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'

# ✅ Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ✅ CORS (разрешаем все для разработки)
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ✅ REST Framework
# 🔧 ИСПРАВЛЕНО: Убран SessionAuthentication — он требует CSRF для POST-запросов
# Для API с токенами достаточно TokenAuthentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        # ✅ SessionAuthentication убран — не требует CSRF для API
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    },
}

# ✅ File upload settings (100MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ✅ Redirects
LOGIN_REDIRECT_URL = '/api/'
LOGOUT_REDIRECT_URL = '/api/'

# ✅ CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://192.168.0.104:8000',
    'http://83.166.236.188:8002',
    'http://83.166.236.188',
]

# ✅ Content Security Policy (разрешаем CDN для handsontable)
CSP_DEFAULT_SRC = ("'self'", 'https:', 'http:', "'unsafe-inline'", "'unsafe-eval'")
CSP_SCRIPT_SRC = ("'self'", 'https:', 'http:', "'unsafe-inline'", "'unsafe-eval'",
                  'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'fonts.googleapis.com')
CSP_STYLE_SRC = ("'self'", 'https:', 'http:', "'unsafe-inline'",
                 'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'fonts.googleapis.com')
CSP_CONNECT_SRC = ("'self'", 'https:', 'http:')
CSP_IMG_SRC = ("'self'", 'https:', 'http:', 'data:', 'blob:')
CSP_FONT_SRC = ("'self'", 'https:', 'http:', 'data:', 'fonts.gstatic.com')
CSP_FRAME_SRC = ("'self'", 'https:', 'http:')

# ✅ X-Frame-Options
X_FRAME_OPTIONS = 'SAMEORIGIN'

# ✅ Логирование
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'WARNING',
            'propagate': False,
        },
        'files': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'sections': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# ✅ ПРОДАКШЕН НАСТРОЙКИ (когда DEBUG=False)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

    # ✅ Куки: пока нет HTTPS — оставляем False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    # ✅ HSTS: пока нет HTTPS — отключаем
    SECURE_HSTS_SECONDS = 0

    MEDIA_ROOT = BASE_DIR / 'media'
    STATIC_ROOT = BASE_DIR / 'staticfiles'
