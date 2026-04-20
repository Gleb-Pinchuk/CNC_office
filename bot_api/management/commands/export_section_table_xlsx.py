"""Экспорт SectionTable.content в .xlsx файл (локально, без Nextcloud)."""

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from bot_api.xlsx_sync import content_to_excel_bytes
from sections.models import SectionTable


class Command(BaseCommand):
    help = "Экспортирует таблицу из БД в .xlsx на диск сервера."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, help="Явный id SectionTable")
        parser.add_argument(
            "--owner",
            help="Username владельца (по умолчанию CNC_BOT_TABLE_OWNER_USERNAME).",
        )
        parser.add_argument(
            "--title",
            help="Фрагмент title (по умолчанию CNC_TABLE_TITLE_FRAGMENT).",
        )
        parser.add_argument(
            "--section-type",
            default=os.getenv("CNC_SECTION_TYPE", "rangers"),
            help="Тип раздела (по умолчанию CNC_SECTION_TYPE).",
        )
        parser.add_argument(
            "--output",
            required=True,
            help="Путь к итоговому xlsx файлу, например /app/backups/table.xlsx",
        )

    def handle(self, *args, **options):
        table = self._pick_table(options)
        if not table:
            raise CommandError("SectionTable не найдена по заданным параметрам")

        blob = content_to_excel_bytes(table.content or {})
        out_path = Path(options["output"]).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(blob)
        self.stdout.write(
            self.style.SUCCESS(
                f"Экспортировано: table_id={table.id} -> {out_path} ({len(blob)} bytes)"
            )
        )

    def _pick_table(self, options):
        table_id = options.get("id")
        if table_id:
            return SectionTable.objects.filter(id=table_id).order_by("-updated_at").first()

        owner_username = (
            options.get("owner") or os.getenv("CNC_BOT_TABLE_OWNER_USERNAME", "")
        ).strip()
        title_fragment = (options.get("title") or os.getenv("CNC_TABLE_TITLE_FRAGMENT", "")).strip()
        section_type = (options.get("section_type") or "rangers").strip()

        qs = SectionTable.objects.filter(section_type=section_type)
        if owner_username:
            user = get_user_model().objects.filter(username=owner_username).first()
            if not user:
                return None
            qs = qs.filter(owner=user)
        if title_fragment:
            qs = qs.filter(title__icontains=title_fragment)
        return qs.order_by("-updated_at").first()
