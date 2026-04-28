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


@shared_task(bind=True, ignore_result=True)
def rollover_monthly_tables(self):
    """Ежедневно проверяет, нужно ли перекатить таблицу мониторинга на новый месяц."""
    from bot_api.monthly_rollover import rollover_table_if_needed
    from bot_api.services.nextcloud_sync import find_section_table, load_nextcloud_sync_config_from_env

    cfg = load_nextcloud_sync_config_from_env()
    if not cfg:
        logger.warning("Monthly rollover: неполная конфигурация окружения, пропуск")
        return None
    table = find_section_table(cfg)
    if not table:
        logger.warning("Monthly rollover: SectionTable не найдена")
        return None
    try:
        return rollover_table_if_needed(table)
    except Exception:
        logger.exception("Monthly rollover failed")
        raise
