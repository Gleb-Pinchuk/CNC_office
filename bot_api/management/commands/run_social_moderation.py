from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from bot_api.moderation.service import run_social_moderation_scan


class Command(BaseCommand):
    help = "Обходит соцссылки студентов и ставит AI-замечания при срабатывании правил."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Записывать изменения в таблицу (по умолчанию dry-run).",
        )
        parser.add_argument(
            "--date",
            default="",
            help="Дата проверки в формате YYYY-MM-DD (для выбора недельной колонки).",
        )
        parser.add_argument(
            "--max-students",
            type=int,
            default=0,
            help="Ограничить число проверенных студентов за запуск.",
        )
        parser.add_argument(
            "--no-evidence",
            action="store_true",
            help="Не сохранять превью поста в RemarkEvidence (только текст в ячейку).",
        )
        parser.add_argument("--table-id", type=int, default=0, help="ID SectionTable.")
        parser.add_argument(
            "--sheet",
            default="",
            help="Имя листа/направления (иначе все листы).",
        )

    def handle(self, *args, **options):
        dry_run = not options["apply"]
        parsed_date = None
        if options["date"]:
            try:
                parsed_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("--date должен быть в формате YYYY-MM-DD") from exc

        stats = run_social_moderation_scan(
            scan_date=parsed_date,
            dry_run=dry_run,
            max_students=options["max_students"] or None,
            save_evidence=not options["no_evidence"],
            table_id=options["table_id"] or None,
            sheet_name=(options["sheet"] or "").strip() or None,
        )
        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{mode}] checked={stats.checked_students} "
                f"with_links={stats.students_with_links} "
                f"links_ok={stats.links_ok} links_fail={stats.links_fail} "
                f"posts={stats.posts_fetched} flagged={stats.flagged_students} "
                f"updated={stats.updated_cells} evidence={stats.evidence_saved}"
            )
        )
        for err in (stats.sample_errors or [])[:5]:
            self.stdout.write(self.style.WARNING(f"  err: {err}"))
        for link in (stats.sample_links or [])[:5]:
            self.stdout.write(f"  link: {link}")
