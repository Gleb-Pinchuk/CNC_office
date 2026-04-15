"""
Django settings for config project.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_SECRET_KEY = "django-insecure-k+6l5pe((b=%)u1kzr5do+sch9#iker1i5=t+7++yuim=+_+^d"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]
for local_host in ("localhost", "127.0.0.1", "[::1]"):
    if local_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(local_host)
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured('In production set ALLOWED_HOSTS without "*"')
if not DEBUG and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured("In production set SECRET_KEY to a unique random value")

# ✅ Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_filters",
    # Local apps
    "files",
    "users",
    "documents",
    "sections",
    "bot_api",
]

# Токен для VK-бота (заголовок X-CNC-Bot-Token) и пользователь-владелец таблиц разделов
CNC_BOT_API_SECRET = os.getenv("CNC_BOT_API_SECRET", "")
CNC_BOT_TABLE_OWNER_USERNAME = os.getenv("CNC_BOT_TABLE_OWNER_USERNAME", "")

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ✅ Templates: index.html для SPA
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ✅ Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "cnc_office"),
        "USER": os.getenv("POSTGRES_USER", "cnc_user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "cnc_password"),
        "HOST": os.getenv("DB_HOST", "db"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# ✅ Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ✅ Internationalization
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# ✅ Static files (для SPA + vendor)
STATICFILES_DIRS = [
    BASE_DIR / "frontend",
    BASE_DIR / "frontend/vendor",
]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"

# ✅ Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ✅ CORS (разрешаем все для разработки)
CORS_ALLOW_ALL_ORIGINS = os.getenv(
    "CORS_ALLOW_ALL_ORIGINS", "True" if DEBUG else "False"
).lower() in ("true", "1", "yes")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "False").lower() in (
    "true",
    "1",
    "yes",
)
CORS_ALLOWED_ORIGINS_ENV = os.getenv("CORS_ALLOWED_ORIGINS", "")
if CORS_ALLOWED_ORIGINS_ENV:
    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in CORS_ALLOWED_ORIGINS_ENV.split(",") if o.strip()
    ]

# ✅ REST Framework
# 🔧 ИСПРАВЛЕНО: Убран SessionAuthentication — он требует CSRF для POST-запросов
# Для API с токенами достаточно TokenAuthentication
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/day", "user": "1000/day"},
}

# ✅ File upload settings (100MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ✅ Redirects
LOGIN_REDIRECT_URL = "/api/"
LOGOUT_REDIRECT_URL = "/api/"

# ✅ CSRF trusted origins
CSRF_TRUSTED_ORIGINS_ENV = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in CSRF_TRUSTED_ORIGINS_ENV.split(",") if o.strip()
]
if DEBUG and not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

# ✅ Trusted proxy / HTTPS (enable behind nginx when using TLS termination)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE", "False" if DEBUG else "True"
).lower() in ("true", "1", "yes")
CSRF_COOKIE_SECURE = os.getenv(
    "CSRF_COOKIE_SECURE", "False" if DEBUG else "True"
).lower() in ("true", "1", "yes")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_HTTPONLY = os.getenv("CSRF_COOKIE_HTTPONLY", "True").lower() in (
    "true",
    "1",
    "yes",
)
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
SECURE_HSTS_SECONDS = int(
    os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", "False"
).lower() in ("true", "1", "yes")
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "False").lower() in (
    "true",
    "1",
    "yes",
)
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False" if DEBUG else "True").lower() in (
    "true",
    "1",
    "yes",
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv(
    "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
)
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.getenv(
    "SECURE_CROSS_ORIGIN_OPENER_POLICY", "same-origin"
)

# ✅ Content Security Policy (разрешаем CDN для handsontable)
CSP_DEFAULT_SRC = ("'self'", "https:", "http:", "'unsafe-inline'", "'unsafe-eval'")
CSP_SCRIPT_SRC = (
    "'self'",
    "https:",
    "http:",
    "'unsafe-inline'",
    "'unsafe-eval'",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "fonts.googleapis.com",
)
CSP_STYLE_SRC = (
    "'self'",
    "https:",
    "http:",
    "'unsafe-inline'",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "fonts.googleapis.com",
)
CSP_CONNECT_SRC = ("'self'", "https:", "http:")
CSP_IMG_SRC = ("'self'", "https:", "http:", "data:", "blob:")
CSP_FONT_SRC = ("'self'", "https:", "http:", "data:", "fonts.gstatic.com")
CSP_FRAME_SRC = ("'self'", "https:", "http:")

# ✅ X-Frame-Options
X_FRAME_OPTIONS = "SAMEORIGIN"

# Ensure log directory exists (CI/local runs)
LOG_DIR = BASE_DIR / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # If the filesystem is read-only, fallback to console-only logging below.
    LOG_DIR = None

# ✅ Логирование
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": (
                (BASE_DIR / "logs" / "django.log") if LOG_DIR else "/tmp/django.log"
            ),
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "WARNING",
            "propagate": False,
        },
        "files": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "sections": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}

# ✅ Production hardening (when DEBUG=False)
if not DEBUG:
    X_FRAME_OPTIONS = "DENY"
    SECURE_BROWSER_XSS_FILTER = True
