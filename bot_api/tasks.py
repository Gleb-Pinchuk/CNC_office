import logging

from django.conf import settings
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def push_pending_nextcloud(self):
    """Раз в 5 мин (beat): отправить несинхронизированные изменения в Nextcloud."""
    from bot_api.services.nextcloud_sync import (
        load_nextcloud_sync_configs_from_env,
        push_to_nextcloud,
    )

    cfgs = load_nextcloud_sync_configs_from_env()
    if not cfgs:
        logger.warning("Nextcloud sync: неполная конфигурация окружения, пропуск")
        return None
    results = []
    try:
        for cfg in cfgs:
            results.append(push_to_nextcloud(cfg, force=False))
        return results
    except Exception:
        logger.exception("Nextcloud sync push failed")
        raise


@shared_task(bind=True, ignore_result=True)
def pull_nextcloud_updates(self):
    """Раз в 10 мин (beat): подтянуть изменения из Nextcloud в БД для всех групп."""
    from bot_api.services.nextcloud_sync import (
        load_nextcloud_sync_configs_from_env,
        pull_from_nextcloud,
    )

    cfgs = load_nextcloud_sync_configs_from_env()
    if not cfgs:
        logger.warning("Nextcloud pull: неполная конфигурация окружения, пропуск")
        return None
    results = []
    for cfg in cfgs:
        try:
            results.append(pull_from_nextcloud(cfg))
        except Exception:
            logger.exception("Nextcloud pull failed for key=%s", cfg.key)
    return results


@shared_task(bind=True, ignore_result=True)
def rollover_monthly_tables(self):
    """Ежедневно проверяет, нужно ли перекатить таблицу мониторинга на новый месяц."""
    from bot_api.monthly_rollover import rollover_table_if_needed
    from bot_api.services.nextcloud_sync import (
        find_section_table,
        load_nextcloud_sync_configs_from_env,
        push_to_nextcloud,
    )

    cfgs = load_nextcloud_sync_configs_from_env()
    if not cfgs:
        logger.warning("Monthly rollover: неполная конфигурация окружения, пропуск")
        return None
    results = []
    for cfg in cfgs:
        table = find_section_table(cfg)
        if not table:
            logger.warning("Monthly rollover: SectionTable не найдена для key=%s", cfg.key)
            continue
        try:
            result = rollover_table_if_needed(table)
            if result.get("changed"):
                # Сразу пушим обновление нового месяца в Nextcloud,
                # чтобы pull-задача не вернула старые замечания обратно в БД.
                push_to_nextcloud(cfg, force=True)
            results.append(result)
        except Exception:
            logger.exception("Monthly rollover failed for key=%s", cfg.key)
            raise
    return results


@shared_task(bind=True, ignore_result=True)
def purge_expired_student_trash(self):
    """Ежедневно: удалить из корзины записи старше TTL вместе со скринами."""
    from django.utils import timezone

    from bot_api.evidence import delete_all_remark_evidence_for_student
    from bot_api.models import StudentTrash

    now = timezone.now()
    expired = list(StudentTrash.objects.filter(expires_at__lte=now).select_related("table"))
    removed = 0
    for item in expired:
        try:
            delete_all_remark_evidence_for_student(
                table=item.table,
                sheet_name=item.sheet_name,
                student_fio=item.student_fio,
            )
            item.delete()
            removed += 1
        except Exception:
            logger.exception(
                "Trash purge failed id=%s fio=%s", item.id, item.student_fio
            )
    logger.info("Trash purge: removed %s of %s expired", removed, len(expired))
    return {"removed": removed, "candidates": len(expired)}


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
