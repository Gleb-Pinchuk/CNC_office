"""
Синхронизация SectionTable с .xlsx в Nextcloud (WebDAV).
Логика в bot_api.services.nextcloud_sync; Celery вызывает push через tasks.
"""

import logging
import os
import time

from django.core.management.base import BaseCommand, CommandError

from bot_api.services.nextcloud_sync import (
    load_nextcloud_sync_config_from_env,
    pull_from_nextcloud,
    push_to_nextcloud,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Синхронизация SectionTable с .xlsx в Nextcloud по WebDAV"

    def add_arguments(self, parser):
        parser.add_argument("--pull", action="store_true")
        parser.add_argument("--push", action="store_true")
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=300)
        parser.add_argument("--force-push", action="store_true")

    def handle(self, *args, **options):
        cfg = load_nextcloud_sync_config_from_env()
        if not cfg:
            raise CommandError(
                "Задайте NEXTCLOUD_BASE_URL, NEXTCLOUD_USERNAME, пароль/токен, "
                "NEXTCLOUD_FILE_PATH и CNC_BOT_TABLE_OWNER_USERNAME"
            )

        def run_once():
            if options["pull"]:
                r = pull_from_nextcloud(cfg)
                if not r.get("ok"):
                    raise CommandError(r.get("error", "pull failed"))
                self.stdout.write(self.style.SUCCESS(f"Pull OK table_id={r.get('table_id')}"))
            if options["push"] or options["force_push"]:
                r = push_to_nextcloud(cfg, force=options["force_push"])
                if not r.get("ok"):
                    raise CommandError(r.get("error", "push failed"))
                if r.get("skipped"):
                    self.stdout.write("Push: нет изменений (needs_nextcloud_push=False)")
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"Push OK table_id={r.get('table_id')}")
                    )

        if options["loop"]:
            if not options["pull"] and not options["push"] and not options["force_push"]:
                options["push"] = True
            interval = max(30, int(options["interval"] or 300))
            self.stdout.write(self.style.NOTICE(f"Цикл каждые {interval} с"))
            while True:
                try:
                    run_once()
                except Exception as e:
                    logger.exception("sync_nextcloud_sheet: %s", e)
                    self.stdout.write(self.style.ERROR(str(e)))
                time.sleep(interval)
        else:
            if not options["pull"] and not options["push"] and not options["force_push"]:
                raise CommandError("Укажите --pull и/или --push, либо --loop")
            run_once()
