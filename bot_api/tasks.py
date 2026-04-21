import logging

from django.conf import settings
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def push_pending_nextcloud(self):
    """Раз в 5 мин (beat): отправить несинхронизированные изменения в Nextcloud."""
    from bot_api.services.nextcloud_sync import (
        load_nextcloud_sync_config_from_env,
        push_to_nextcloud,
    )

    cfg = load_nextcloud_sync_config_from_env()
    if not cfg:
        logger.warning("Nextcloud sync: неполная конфигурация окружения, пропуск")
        return None
    try:
        return push_to_nextcloud(cfg, force=False)
    except Exception:
        logger.exception("Nextcloud sync push failed")
        raise


@shared_task(bind=True, ignore_result=True)
def run_social_moderation_scan_task(self):
    """Периодический авто-обход соцсетей студентов и запись AI-замечаний."""
    if not getattr(settings, "SOCIAL_MODERATION_ENABLED", False):
        logger.info("Social moderation is disabled; skip")
        return None
    from bot_api.moderation.service import run_social_moderation_scan

    stats = run_social_moderation_scan(
        dry_run=False,
        max_students=getattr(settings, "SOCIAL_MOD_MAX_STUDENTS_PER_RUN", 0) or None,
    )
    logger.info(
        "Social moderation done: checked=%s flagged=%s updated=%s",
        stats.checked_students,
        stats.flagged_students,
        stats.updated_cells,
    )
    return {
        "checked": stats.checked_students,
        "flagged": stats.flagged_students,
        "updated": stats.updated_cells,
    }
