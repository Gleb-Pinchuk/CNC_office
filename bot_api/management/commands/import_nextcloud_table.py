import os
import sys
import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from sections.models import SectionTable
import requests
from requests.auth import HTTPBasicAuth
import urllib.parse
import json

# Попытка импорта openpyxl для работы с Excel
try:
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Импортирует таблицу из Nextcloud (прямой доступ через WebDAV без поиска API)"

    def handle(self, *args, **options):
        nc_base = os.getenv("NEXTCLOUD_BASE_URL", "").rstrip("/")
        nc_user = os.getenv("NEXTCLOUD_USERNAME", "")
        nc_pass = os.getenv("NEXTCLOUD_PASSWORD", "") or os.getenv("NEXTCLOUD_APP_TOKEN", "")

        owner_username = os.getenv("CNC_BOT_TABLE_OWNER_USERNAME", "")
        table_title = os.getenv("CNC_TABLE_TITLE_FRAGMENT", "")
        section_type = os.getenv("CNC_SECTION_TYPE", "rangers")

        if not nc_base or not nc_user or not nc_pass:
            raise CommandError(
                "Не заданы NEXTCLOUD_BASE_URL, NEXTCLOUD_USERNAME и NEXTCLOUD_PASSWORD/TOKEN в окружении.")

        if not owner_username or not table_title:
            raise CommandError("Не заданы CNC_BOT_TABLE_OWNER_USERNAME или CNC_TABLE_TITLE_FRAGMENT в окружении.")

        self.stdout.write(f"🔍 Прямой поиск файла '{table_title}' для пользователя '{owner_username}' в Nextcloud...")

        # 1. Находим или создаем пользователя в БД
        User = get_user_model()
        try:
            owner = User.objects.get(username=owner_username)
            self.stdout.write(self.style.SUCCESS(f"✅ Пользователь '{owner_username}' найден в БД (ID: {owner.id})"))
        except User.DoesNotExist:
            owner = User.objects.create_user(username=owner_username, password="unused")
            self.stdout.write(self.style.WARNING(f"⚠️ Пользователь '{owner_username}' создан в БД (ID: {owner.id})"))

        # 2. Проверяем, есть ли уже такая таблица в БД
        existing_table = SectionTable.objects.filter(owner=owner, section_type=section_type).filter(
            title__icontains=table_title).first()
        if existing_table:
            self.stdout.write(self.style.WARNING(
                f"ℹ️ Таблица '{existing_table.title}' уже существует в БД (ID: {existing_table.id}). Обновление контента..."))
            # Можно добавить логику обновления, если нужно
            return

        # 3. Формируем URL для WebDAV
        # Кодируем имя файла для URL, но не весь путь целиком, чтобы избежать двойного кодирования
        safe_filename = urllib.parse.quote(f"{table_title}.xlsx")
        # Путь WebDAV: /remote.php/dav/files/{USER}/{FILENAME}
        dav_path = f"/remote.php/dav/files/{owner_username}/{safe_filename}"
        file_url = f"{nc_base}{dav_path}"

        self.stdout.write(f"📥 Скачивание файла по URL: {file_url}")

        session = requests.Session()
        session.auth = HTTPBasicAuth(nc_user, nc_pass)
        # Отключаем редиректы для отладки, если нужно, но обычно они полезны
        session.allow_redirects = True

        try:
            response = session.get(file_url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                self.stdout.write(self.style.ERROR(f"❌ Файл не найден по адресу: {file_url}"))
                self.stdout.write(self.style.WARNING("💡 Проверьте точное имя файла в Nextcloud (регистр важен!)."))
                self.stdout.write(self.style.WARNING(
                    "💡 Попробуйте создать таблицу вручную через Django shell, если файл называется иначе."))

                # Создаем пустую таблицу-заглушку, чтобы бот мог запуститься
                self._create_empty_table(owner, section_type, table_title)
                return
            else:
                raise CommandError(f"Ошибка доступа к файлу ({response.status_code}): {e}")
        except requests.exceptions.RequestException as e:
            raise CommandError(f"Ошибка подключения к Nextcloud: {e}")

        file_content = response.content
        self.stdout.write(self.style.SUCCESS(f"✅ Файл успешно скачан ({len(file_content)} байт)"))

        # 4. Парсим Excel и конвертируем в формат SectionTable
        sheet_data = self._parse_excel(file_content, table_title)

        if not sheet_data:
            self.stdout.write(self.style.ERROR("❌ Не удалось распарсить Excel файл или он пуст."))
            self._create_empty_table(owner, section_type, table_title)
            return

        # 5. Сохраняем в БД
        table_obj = SectionTable(
            owner=owner,
            section_type=section_type,
            title=table_title,
            content=sheet_data
        )
        table_obj.save()

        self.stdout.write(
            self.style.SUCCESS(f"🎉 Таблица '{table_title}' успешно импортирована в БД (ID: {table_obj.id})!"))
        self.stdout.write(self.style.SUCCESS("🚀 Теперь можно перезапустить vk_bot."))

    def _parse_excel(self, content, title_hint):
        if not HAS_OPENPYXL:
            self.stdout.write(self.style.ERROR("❌ Модуль openpyxl не установлен. Невозможно распарсить .xlsx"))
            self.stdout.write(self.style.WARNING("💡 Установите его: pip install openpyxl"))
            return None

        try:
            wb = openpyxl.load_workbook(content, data_only=True)
            sheets_data = {"sheets": []}

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = []
                for row in ws.iter_rows(values_only=True):
                    # Преобразуем кортеж в список и обрабатываем None
                    clean_row = ["" if cell is None else str(cell) for cell in row]
                    rows.append(clean_row)

                sheets_data["sheets"].append({
                    "name": sheet_name,
                    "data": rows
                })

            self.stdout.write(f"📊 Распарсено листов: {len(sheets_data['sheets'])}")
            return sheets_data

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка парсинга Excel: {e}"))
            return None

    def _create_empty_table(self, owner, section_type, title):
        """Создает пустую таблицу-заглушку с ожидаемыми листами, если файл не найден"""
        self.stdout.write(self.style.WARNING("⚠️ Создание таблицы-заглушки с пустыми листами..."))

        default_sheets = os.getenv("CNC_DIRECTION_SHEETS", "ЧПУ,РОБО,Аэро,микро").split(",")
        content = {"sheets": []}

        for sheet_name in default_sheets:
            name = sheet_name.strip()
            if name:
                # Заголовки + 10 пустых строк
                header = ["ФИО", "Группа", "Статус", "Замечания"]
                empty_rows = [["", "", "", ""] for _ in range(10)]
                content["sheets"].append({
                    "name": name,
                    "data": [header] + empty_rows
                })

        table_obj = SectionTable(
            owner=owner,
            section_type=section_type,
            title=title,
            content=content
        )
        table_obj.save()
        self.stdout.write(self.style.SUCCESS(
            f"✅ Таблица-заглушка '{title}' создана (ID: {table_obj.id}). Заполните её данными вручную или загрузите файл позже."))