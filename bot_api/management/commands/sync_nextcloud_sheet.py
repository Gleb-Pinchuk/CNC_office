"""
Синхронизация таблицы раздела с файлом .xlsx в Nextcloud (WebDAV).

- --pull: скачать файл → обновить SectionTable в БД (источник — файл в облаке)
- --push: если needs_nextcloud_push, собрать .xlsx из БД и загрузить в Nextcloud
- --loop --interval 300: периодически выполнять push (и опционально pull)
"""

import logging
import os
import time
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone as dj_tz

from bot_api.nextcloud_webdav import build_user_file_path, webdav_get, webdav_put
from bot_api.xlsx_sync import content_to_excel_bytes, excel_bytes_to_content
from sections.models import SectionTable

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


class Command(BaseCommand):
    help = "Синхронизация SectionTable с .xlsx в Nextcloud по WebDAV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pull",
            action="store_true",
            help="Скачать .xlsx из Nextcloud и обновить БД",
        )
        parser.add_argument(
            "--push",
            action="store_true",
            help="Отправить изменения из БД в Nextcloud (если needs_nextcloud_push)",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Бесконечный цикл (удобно для отдельного контейнера)",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=300,
            help="Интервал в секундах для --loop (по умолчанию 300)",
        )
        parser.add_argument(
            "--force-push",
            action="store_true",
            help="Отправить файл в Nextcloud даже если флаг needs_nextcloud_push сброшен",
        )

    def handle(self, *args, **options):
        nc_base = _env("NEXTCLOUD_BASE_URL")
        nc_user = _env("NEXTCLOUD_USERNAME")
        nc_pass = _env("NEXTCLOUD_PASSWORD") or _env("NEXTCLOUD_APP_TOKEN")
        nc_rel = _env("NEXTCLOUD_FILE_PATH", _env("NEXTCLOUD_XLSX_RELATIVE_PATH"))

        owner_username = _env("CNC_BOT_TABLE_OWNER_USERNAME")
        section_type = _env("CNC_SECTION_TYPE", "rangers")
        title_contains = _env("CNC_TABLE_TITLE_FRAGMENT", "")

        if not nc_base or not nc_user or not nc_pass:
            raise CommandError(
                "Задайте NEXTCLOUD_BASE_URL, NEXTCLOUD_USERNAME и "
                "NEXTCLOUD_PASSWORD или NEXTCLOUD_APP_TOKEN"
            )
        if not nc_rel:
            raise CommandError(
                "Задайте NEXTCLOUD_FILE_PATH — путь к .xlsx в каталоге пользователя "
                "Nextcloud (например Students/table.xlsx)"
            )
        if not owner_username:
            raise CommandError("Задайте CNC_BOT_TABLE_OWNER_USERNAME (владелец SectionTable в БД)")

        webdav_path = build_user_file_path(nc_user, nc_rel)

        def run_once():
            if options["pull"]:
                self._pull(
                    nc_base,
                    webdav_path,
                    nc_user,
                    nc_pass,
                    owner_username,
                    section_type,
                    title_contains,
                )
            if options["push"] or options["force_push"]:
                self._push(
                    nc_base,
                    webdav_path,
                    nc_user,
                    nc_pass,
                    owner_username,
                    section_type,
                    title_contains,
                    force=options["force_push"],
                )

        if options["loop"]:
            if not options["pull"] and not options["push"] and not options["force_push"]:
                options["push"] = True
            interval = max(30, int(options["interval"] or 300))
            self.stdout.write(
                self.style.NOTICE(f"Цикл синхронизации каждые {interval} с (Ctrl+C для выхода)")
            )
            while True:
                try:
                    run_once()
                except Exception as e:
                    logger.exception("sync_nextcloud_sheet: %s", e)
                    self.stdout.write(self.style.ERROR(str(e)))
                time.sleep(interval)
        else:
            if not options["pull"] and not options["push"] and not options["force_push"]:
                raise CommandError("Укажите --pull и/или --push (или --force-push), либо --loop")
            run_once()

    def _find_table(self, owner_username: str, section_type: str, title_contains: str):
        User = get_user_model()
        owner = User.objects.filter(username=owner_username).first()
        if not owner:
            raise CommandError(f"Пользователь '{owner_username}' не найден в БД")
        qs = SectionTable.objects.filter(owner=owner, section_type=section_type)
        if title_contains:
            search_term = title_contains.strip().lower()
            qs = qs.filter(title__icontains=search_term)
        table = qs.order_by("-updated_at").first()
        if not table and title_contains:
            table = (
                SectionTable.objects.filter(owner=owner, section_type=section_type)
                .order_by("-updated_at")
                .first()
            )
        return table

    def _pull(
        self,
        nc_base: str,
        webdav_path: str,
        nc_user: str,
        nc_pass: str,
        owner_username: str,
        section_type: str,
        title_contains: str,
    ):
        self.stdout.write("⬇️  Загрузка файла из Nextcloud…")
        raw, _etag = webdav_get(nc_base, webdav_path, nc_user, nc_pass)
        new_content = excel_bytes_to_content(raw)
        table = self._find_table(owner_username, section_type, title_contains)
        if not table:
            raise CommandError(
                "Таблица SectionTable не найдена. Сначала создайте запись "
                "(например import_nextcloud_table) или проверьте CNC_TABLE_TITLE_FRAGMENT."
            )
        with transaction.atomic():
            st = SectionTable.objects.select_for_update().get(pk=table.pk)
            st.content = new_content
            st.needs_nextcloud_push = False
            st.save(update_fields=["content", "needs_nextcloud_push", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"✅ БД обновлена из Nextcloud (table id={table.pk})"))

    def _push(
        self,
        nc_base: str,
        webdav_path: str,
        nc_user: str,
        nc_pass: str,
        owner_username: str,
        section_type: str,
        title_contains: str,
        *,
        force: bool,
    ):
        table = self._find_table(owner_username, section_type, title_contains)
        if not table:
            raise CommandError("Таблица SectionTable не найдена.")
        if not force and not table.needs_nextcloud_push:
            self.stdout.write("Нет изменений для отправки (needs_nextcloud_push=False).")
            return

        self.stdout.write("⬆️  Отправка .xlsx в Nextcloud…")
        table.refresh_from_db()
        blob = content_to_excel_bytes(table.content or {})
        webdav_put(nc_base, webdav_path, nc_user, nc_pass, blob)
        now = dj_tz.now()
        SectionTable.objects.filter(pk=table.pk).update(
            needs_nextcloud_push=False,
            last_nextcloud_push_at=now,
            updated_at=now,
        )
        self.stdout.write(self.style.SUCCESS(f"✅ Файл обновлён в Nextcloud (table id={table.pk})"))
