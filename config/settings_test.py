"""
Настройки для pytest (импортируются до root conftest).
"""

import os

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "pytest-insecure-secret-key-do-not-use-in-production")
os.environ["ENABLE_OIDC"] = "false"

from .settings import *  # noqa: E402, F403, F401

# База — как в config.settings (PostgreSQL). Для pytest задайте DB_HOST/POSTGRES_*,
# например как в CI или через docker compose.

