import logging

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
