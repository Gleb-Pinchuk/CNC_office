"""Блокировка ИИ-скана по направлению (table_id + sheet), общая для всех VK-пользователей."""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

LOCK_TTL_SEC = int(getattr(settings, "SOCIAL_MOD_LOCK_TTL_SEC", 7200) or 7200)


def _lock_key(table_id: int, sheet_name: str) -> str:
    sheet = " ".join(str(sheet_name or "").split()).strip().lower()
    return f"social_mod:lock:{int(table_id)}:{sheet}"


def _redis():
    import redis

    url = getattr(settings, "CELERY_BROKER_URL", None) or "redis://127.0.0.1:6379/0"
    return redis.from_url(url, decode_responses=True)


def try_acquire_direction_lock(table_id: int, sheet_name: str) -> bool:
    """True если лок взят. False если направление уже сканируется."""
    key = _lock_key(table_id, sheet_name)
    try:
        r = _redis()
        ok = bool(r.set(key, "1", nx=True, ex=LOCK_TTL_SEC))
        if not ok:
            logger.info("Social mod lock busy: %s", key)
        return ok
    except Exception:
        logger.exception("Redis lock acquire failed; allowing scan without lock")
        return True


def release_direction_lock(table_id: int, sheet_name: str) -> None:
    key = _lock_key(table_id, sheet_name)
    try:
        _redis().delete(key)
    except Exception:
        logger.exception("Redis lock release failed: %s", key)


def direction_lock_held(table_id: int, sheet_name: str) -> bool:
    key = _lock_key(table_id, sheet_name)
    try:
        return bool(_redis().exists(key))
    except Exception:
        return False
