import os
import json
import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from sections.models import SectionTable
import requests
from urllib.parse import quote, urlparse, unquote

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Импортирует таблицу из Nextcloud (OnlyOffice) в базу данных Django"

    def handle(self, *args, **options):
        nc_base = os.getenv("NEXTCLOUD_BASE_URL", "").rstrip("/")
        nc_user = os.getenv("NEXTCLOUD_USERNAME")
        nc_pass = os.getenv("NEXTCLOUD_PASSWORD")
        nc_token = os.getenv("NEXTCLOUD_APP_TOKEN")

        owner_username = os.getenv("CNC_BOT_TABLE_OWNER_USERNAME")
        table_title_fragment = os.getenv("CNC_TABLE_TITLE_FRAGMENT", "")
        section_type = os.getenv("CNC_SECTION_TYPE", "rangers")

        if not nc_base or not nc_user or (not nc_pass and not nc_token):
            raise CommandError("Не заданы NEXTCLOUD_USERNAME и NEXTCLOUD_PASSWORD (или APP_TOKEN) в окружении.")

        if not owner_username:
            raise CommandError("Не задан CNC_BOT_TABLE_OWNER_USERNAME в окружении.")

        auth = (nc_user, nc_token) if nc_token else (nc_user, nc_pass)
        headers = {"OCS-APIRequest": "true"}

        self.stdout.write(
            f"🔍 Поиск таблицы '{table_title_fragment}' для пользователя '{owner_username}' в Nextcloud...")

        # 1. Находим пользователя в БД
        User = get_user_model()
        try:
            owner = User.objects.get(username=owner_username)
            self.stdout.write(f"✅ Пользователь '{owner_username}' найден в БД (ID: {owner.id})")
        except User.DoesNotExist:
            owner = User.objects.create_user(username=owner_username, password="unused")
            self.stdout.write(f"⚠️ Пользователь '{owner_username}' создан в БД (ID: {owner.id})")

        # 2. Ищем файл через Nextcloud Search API
        search_url = f"{nc_base}/ocs/v2.php/search/providers/file/search?term={quote(table_title_fragment)}&limit=10"

        try:
            resp = requests.get(search_url, auth=auth, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            entries = data.get("ocs", {}).get("data", {}).get("entries", [])
            if not entries:
                # Пробуем альтернативный формат ответа
                entries = data.get("ocs", {}).get("data", [])

            file_entry = None
            for entry in entries:
                title = entry.get("title", "")
                # Ищем точное совпадение или содержащее фрагмент
                if table_title_fragment.lower() in title.lower() and title.endswith(".xlsx"):
                    file_entry = entry
                    break

            if not file_entry:
                # Если точное не нашли, берем первое xlsx
                for entry in entries:
                    if entry.get("title", "").endswith(".xlsx"):
                        file_entry = entry
                        break

            if not file_entry:
                raise CommandError(
                    f"Файл таблицы '{table_title_fragment}' не найден в Nextcloud у пользователя {nc_user}. Доступные файлы: {[e.get('title') for e in entries[:5]]}")

            file_title = file_entry.get("title")
            file_id = file_entry.get("id")  # Это обычно внутренний ID файла
            path = file_entry.get("path", "")  # Путь относительно корня пользователя

            self.stdout.write(f"🎯 Найден файл: {file_title} (ID: {file_id}, Path: {path})")

            # 3. Формируем правильный URL для скачивания
            # Путь от API часто начинается с '/', но для WebDAV нам нужен путь относительно пользователя
            # Формат WebDAV: {base}/remote.php/dav/files/{username}/{path_without_leading_slash}
            clean_path = path.lstrip("/")
            dav_url = f"{nc_base}/remote.php/dav/files/{nc_user}/{quote(clean_path, safe='/')}"

            self.stdout.write(f"📥 Скачивание по URL: {dav_url}")

            r_file = requests.get(dav_url, auth=auth, timeout=30)
            r_file.raise_for_status()

            file_content = r_file.content

            # 4. Парсим Excel (простая эмуляция структуры для бота)
            # Так как у нас нет openpyxl в легковесном контейнере, мы создадим пустую структуру
            # и предложим пользователю заполнить её вручную или установим openpyxl
            try:
                import openpyxl
                from io import BytesIO

                wb = openpyxl.load_workbook(BytesIO(file_content))
                sheets_data = []

                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    data = []
                    for row in ws.iter_rows(values_only=True):
                        # Преобразуем кортеж в список, заменяем None на пустые строки
                        clean_row = [str(cell) if cell is not None else "" for cell in row]
                        data.append(clean_row)
                    sheets_data.append({
                        "name": sheet_name,
                        "data": data
                    })

                content_json = {"sheets": sheets_data}
                self.stdout.write(f"✅ Успешно распарсен Excel: {len(sheets_data)} листов")

            except ImportError:
                self.stdout.write("⚠️ Модуль openpyxl не найден. Создаю пустую структуру таблицы.")
                self.stdout.write("💡 Совет: установите openpyxl в requirements.txt для полного импорта данных.")
                content_json = {
                    "sheets": [
                        {"name": "Лист1", "data": [["Заголовок", "Данные"], ["", ""]]}
                    ]
                }

            # 5. Сохраняем в БД
            table, created = SectionTable.objects.update_or_create(
                owner=owner,
                section_type=section_type,
                defaults={
                    "title": file_title.replace(".xlsx", ""),
                    "content": content_json,
                }
            )

            if created:
                self.stdout.write(f"✅ Таблица создана в БД: ID={table.id}, Title='{table.title}'")
            else:
                self.stdout.write(f"🔄 Таблица обновлена в БД: ID={table.id}, Title='{table.title}'")

            self.stdout.write(self.style.SUCCESS("🎉 Импорт завершен! Теперь можно перезапустить бота."))

        except requests.exceptions.RequestException as e:
            raise CommandError(f"Ошибка подключения к Nextcloud: {e}")
        except Exception as e:
            raise CommandError(f"Критическая ошибка импорта: {e}")