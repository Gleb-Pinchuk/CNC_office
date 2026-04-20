"""Быстрая диагностика SectionTable: структура content и листы."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from bot_api.sheet_utils import get_workbook_sheets
from sections.models import SectionTable


class Command(BaseCommand):
    help = "Показывает структуру content у SectionTable (листы, количество строк и т.п.)."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Username владельца (по умолчанию из CNC_BOT_TABLE_OWNER_USERNAME).")
        parser.add_argument("--title", help="Фрагмент title (по умолчанию из CNC_TABLE_TITLE_FRAGMENT).")
        parser.add_argument("--id", type=int, help="Явный id SectionTable.")

    def handle(self, *args, **options):
        qs = SectionTable.objects.all()
        table_id = options.get("id")
        if table_id:
            qs = qs.filter(id=table_id)
        else:
            owner_username = options.get("owner") or os.getenv("CNC_BOT_TABLE_OWNER_USERNAME", "")
            title_fragment = options.get("title") or os.getenv("CNC_TABLE_TITLE_FRAGMENT", "")
            if owner_username:
                User = get_user_model()
                user = User.objects.filter(username=owner_username).first()
                if not user:
                    self.stdout.write(self.style.ERROR(f"Пользователь '{owner_username}' не найден"))
                    return
                qs = qs.filter(owner=user)
            if title_fragment:
                qs = qs.filter(title__icontains=title_fragment)

        if not qs.exists():
            self.stdout.write(self.style.WARNING("Таблицы не найдены"))
            return

        for t in qs.order_by("-updated_at"):
            content = t.content or {}
            sheets, ai = get_workbook_sheets(content)
            keys = list(content.keys()) if isinstance(content, dict) else []
            self.stdout.write(self.style.SUCCESS(f"\nid={t.id} title={t.title!r} owner={t.owner.username}"))
            self.stdout.write(f"  ключи content: {keys}")
            self.stdout.write(f"  листов распознано: {len(sheets)}, active_index={ai}")
            for i, sh in enumerate(sheets):
                name = sh.get("name") or f"Лист{i+1}"
                data = sh.get("data") if isinstance(sh, dict) else None
                rows = len(data) if isinstance(data, list) else 0
                cols = max((len(r) for r in data if isinstance(r, list)), default=0) if isinstance(data, list) else 0
                self.stdout.write(f"    [{i}] {name}  rows={rows}  cols={cols}")
            if not sheets:
                self.stdout.write(self.style.WARNING("  ⚠️  content не содержит распознаваемой структуры листов"))
                if isinstance(content, dict):
                    cs = content.get("custom_sheet")
                    if isinstance(cs, dict):
                        self.stdout.write(f"    custom_sheet keys: {list(cs.keys())}")
