import logging
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from requests.auth import HTTPBasicAuth
import requests

from bot_api.nextcloud_webdav import build_user_file_path
from bot_api.xlsx_sync import build_custom_sheet_v2, excel_bytes_to_content
from sections.models import SectionTable

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Импортирует .xlsx из Nextcloud (WebDAV) в SectionTable в формате custom_sheet v2"

    def handle(self, *args, **options):
        nc_base = os.getenv("NEXTCLOUD_BASE_URL", "").rstrip("/")
        nc_user = os.getenv("NEXTCLOUD_USERNAME", "")
        nc_pass = os.getenv("NEXTCLOUD_PASSWORD", "") or os.getenv("NEXTCLOUD_APP_TOKEN", "")
        nc_rel = os.getenv("NEXTCLOUD_FILE_PATH", "") or os.getenv("NEXTCLOUD_XLSX_RELATIVE_PATH", "")

        owner_username = os.getenv("CNC_BOT_TABLE_OWNER_USERNAME", "")
        table_title = os.getenv("CNC_TABLE_TITLE_FRAGMENT", "")
        section_type = os.getenv("CNC_SECTION_TYPE", "rangers")

        if not nc_base or not nc_user or not nc_pass:
            raise CommandError(
                "Не заданы NEXTCLOUD_BASE_URL, NEXTCLOUD_USERNAME и NEXTCLOUD_PASSWORD/TOKEN."
            )
        if not nc_rel:
            raise CommandError(
                "Задайте NEXTCLOUD_FILE_PATH — путь к .xlsx относительно домашнего каталога "
                "пользователя Nextcloud (например Students/table.xlsx)."
            )
        if not owner_username or not table_title:
            raise CommandError("Не заданы CNC_BOT_TABLE_OWNER_USERNAME или CNC_TABLE_TITLE_FRAGMENT.")

        self.stdout.write(
            f"Загрузка '{nc_rel}' из Nextcloud → SectionTable (владелец БД: {owner_username})…"
        )

        User = get_user_model()
        try:
            owner = User.objects.get(username=owner_username)
            self.stdout.write(self.style.SUCCESS(f"Пользователь '{owner_username}' найден (id={owner.id})"))
        except User.DoesNotExist:
            owner = User.objects.create_user(username=owner_username, password="unused")
            self.stdout.write(self.style.WARNING(f"Создан пользователь '{owner_username}' (id={owner.id})"))

        search_term = table_title.strip().lower()
        existing_table = (
            SectionTable.objects.filter(owner=owner, section_type=section_type)
            .filter(title__icontains=search_term)
            .order_by("-updated_at")
            .first()
        )
        if existing_table:
            self.stdout.write(
                self.style.WARNING(
                    f"Таблица уже есть: id={existing_table.id} «{existing_table.title}». "
                    f"Удалите запись или смените CNC_TABLE_TITLE_FRAGMENT."
                )
            )
            return

        webdav_path = build_user_file_path(nc_user, nc_rel)
        file_url = f"{nc_base}{webdav_path}"
        self.stdout.write(f"GET {file_url}")

        session = requests.Session()
        session.auth = HTTPBasicAuth(nc_user, nc_pass)
        session.headers["OCS-APIRequest"] = "true"

        try:
            response = session.get(file_url, timeout=60)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                self.stdout.write(self.style.ERROR(f"Файл не найден: {file_url}"))
                self._create_empty_table(owner, section_type, table_title)
                return
            raise CommandError(f"Ошибка доступа ({response.status_code}): {e}") from e
        except requests.exceptions.RequestException as e:
            raise CommandError(f"Ошибка подключения к Nextcloud: {e}") from e

        file_content = response.content
        self.stdout.write(self.style.SUCCESS(f"Скачано {len(file_content)} байт"))

        try:
            content = excel_bytes_to_content(file_content)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Не удалось разобрать Excel: {e}"))
            self._create_empty_table(owner, section_type, table_title)
            return

        table_obj = SectionTable(
            owner=owner,
            section_type=section_type,
            title=table_title,
            content=content,
            needs_nextcloud_push=False,
        )
        table_obj.save()
        self.stdout.write(
            self.style.SUCCESS(f"Импорт завершён: SectionTable id={table_obj.id}")
        )

    def _create_empty_table(self, owner, section_type, title):
        self.stdout.write(self.style.WARNING("Создаётся пустая таблица-заглушка…"))
        default_sheets = os.getenv("CNC_DIRECTION_SHEETS", "ЧПУ,РОБО,Аэро,микро").split(",")
        sheets_payload = []
        for sheet_name in default_sheets:
            name = sheet_name.strip()
            if not name:
                continue
            header = ["ФИО", "Группа", "Статус", "Замечания"]
            empty_rows = [["", "", "", ""] for _ in range(10)]
            sheets_payload.append({"name": name, "data": [header] + empty_rows})

        content = build_custom_sheet_v2(sheets_payload)
        t = SectionTable(
            owner=owner,
            section_type=section_type,
            title=title,
            content=content,
            needs_nextcloud_push=True,
        )
        t.save()
        self.stdout.write(self.style.SUCCESS(f"Заглушка создана: id={t.id}"))
