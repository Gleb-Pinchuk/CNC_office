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
def run_social_moderation_scan_task(
    self,
    force=False,
    max_students=None,
    table_id=None,
    sheet_name=None,
    peer_id=None,
    lock_held=False,
):
    """
    Обход соцсетей.
    Из бота: force=True + table_id + sheet_name + peer_id (прогресс в VK).
    lock_held=True — лок уже взят в API; задача только отпускает в finally.
    Beat: без sheet_name — вся таблица (если SOCIAL_MODERATION_ENABLED).
    """
    if not force and not getattr(settings, "SOCIAL_MODERATION_ENABLED", False):
        logger.info("Social moderation is disabled; skip")
        return None

    from bot_api.moderation.locks import release_direction_lock, try_acquire_direction_lock
    from bot_api.moderation.service import run_social_moderation_scan
    from bot_api.moderation.vk_notify import make_progress_notifier, send_vk_message

    limit = max_students
    if limit is None:
        limit = getattr(settings, "SOCIAL_MOD_MAX_STUDENTS_PER_RUN", 0) or None

    owns_lock = bool(lock_held)
    if table_id and sheet_name and not owns_lock:
        if not try_acquire_direction_lock(int(table_id), str(sheet_name)):
            if peer_id:
                send_vk_message(
                    int(peer_id),
                    f"⏳ Проверка направления «{sheet_name}» уже выполняется. "
                    "Дождитесь окончания или выберите другое направление.",
                )
            return {"status": "busy", "sheet_name": sheet_name}
        owns_lock = True

    progress = None
    if peer_id and sheet_name:
        progress = make_progress_notifier(int(peer_id), sheet_name=str(sheet_name))

    try:
        stats = run_social_moderation_scan(
            dry_run=False,
            max_students=limit,
            save_evidence=True,
            table_id=int(table_id) if table_id else None,
            sheet_name=str(sheet_name) if sheet_name else None,
            progress_callback=progress,
        )
    except Exception as exc:
        logger.exception("Social moderation task failed")
        if peer_id:
            send_vk_message(int(peer_id), f"❌ Ошибка проверки ИИ: {exc}")
        raise
    finally:
        if owns_lock and table_id and sheet_name:
            release_direction_lock(int(table_id), str(sheet_name))

    logger.info(
        "Social moderation done: checked=%s flagged=%s updated=%s evidence=%s sheet=%s",
        stats.checked_students,
        stats.flagged_students,
        stats.updated_cells,
        stats.evidence_saved,
        sheet_name,
    )
    return {
        "checked": stats.checked_students,
        "flagged": stats.flagged_students,
        "updated": stats.updated_cells,
        "evidence": stats.evidence_saved,
        "sheet_name": sheet_name,
    }
