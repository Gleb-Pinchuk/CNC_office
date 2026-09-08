"""Импорт локального .xlsx в SectionTable (custom_sheet v2) — для замены списков без Nextcloud."""

from __future__ import annotations

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from bot_api.xlsx_sync import excel_bytes_to_content
from sections.models import SectionTable


class Command(BaseCommand):
    help = (
        "Загружает локальный .xlsx в SectionTable. "
        "Нужно, когда данные в Nextcloud удалены/устарели, а бот всё ещё читает старый content из БД."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Путь к .xlsx (например data/Рейнджеры_производственная_группа.xlsx)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перезаписать существующую таблицу.",
        )
        parser.add_argument(
            "--owner",
            default="",
            help="Владелец таблицы (по умолчанию CNC_BOT_TABLE_OWNER_USERNAME).",
        )
        parser.add_argument(
            "--title",
            default="",
            help="Название/фрагмент таблицы (по умолчанию CNC_TABLE_TITLE_FRAGMENT).",
        )
        parser.add_argument(
            "--section-type",
            default="",
            help="section_type (по умолчанию CNC_SECTION_TYPE или rangers).",
        )
        parser.add_argument(
            "--mark-push",
            action="store_true",
            help="Поставить needs_nextcloud_push=True, чтобы Celery выгрузил файл в Nextcloud.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"]).expanduser()
        if not path.is_file():
            raise CommandError(f"Файл не найден: {path}")

        owner_username = (options["owner"] or os.getenv("CNC_BOT_TABLE_OWNER_USERNAME") or "").strip()
        table_title = (options["title"] or os.getenv("CNC_TABLE_TITLE_FRAGMENT") or "").strip()
        section_type = (
            options["section_type"] or os.getenv("CNC_SECTION_TYPE") or "rangers"
        ).strip()
        force = bool(options.get("force"))
        mark_push = bool(options.get("mark_push"))

        if not owner_username:
            raise CommandError("Задайте --owner или CNC_BOT_TABLE_OWNER_USERNAME")
        if not table_title:
            raise CommandError("Задайте --title или CNC_TABLE_TITLE_FRAGMENT")

        raw = path.read_bytes()
        try:
            content = excel_bytes_to_content(raw)
        except Exception as exc:
            raise CommandError(f"Не удалось разобрать Excel: {exc}") from exc

        sheets = (content.get("custom_sheet") or {}).get("sheets") or []
        self.stdout.write(f"Файл: {path} ({len(raw)} байт), листов: {len(sheets)}")
        for sh in sheets:
            data = sh.get("data") or []
            self.stdout.write(f"  - {sh.get('name')}: строк={len(data)}")

        User = get_user_model()
        owner = User.objects.filter(username=owner_username).first()
        if not owner:
            owner = User.objects.create_user(username=owner_username, password="unused")
            self.stdout.write(self.style.WARNING(f"Создан пользователь {owner_username}"))

        search = table_title.lower()
        existing = (
            SectionTable.objects.filter(owner=owner, section_type=section_type)
            .filter(title__icontains=search)
            .order_by("-updated_at")
            .first()
        )

        if existing and not force:
            raise CommandError(
                f"Таблица уже есть: id={existing.id} «{existing.title}». Укажите --force."
            )

        push_flag = bool(mark_push)
        if existing and force:
            existing.content = content
            existing.title = existing.title or table_title
            existing.needs_nextcloud_push = push_flag
            existing.save(
                update_fields=["content", "title", "needs_nextcloud_push", "updated_at"]
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Обновлено: id={existing.id} «{existing.title}», "
                    f"needs_nextcloud_push={push_flag}"
                )
            )
            return

        obj = SectionTable.objects.create(
            owner=owner,
            section_type=section_type,
            title=table_title,
            content=content,
            needs_nextcloud_push=push_flag,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Создано: id={obj.id} «{obj.title}», needs_nextcloud_push={push_flag}"
            )
        )
