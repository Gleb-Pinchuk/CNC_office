import os
import json
import logging
import requests
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from sections.models import SectionTable

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Импортирует таблицу из Nextcloud OnlyOffice в базу данных Django для работы бота."

    def add_arguments(self, parser):
        parser.add_argument('--owner', type=str, default=os.getenv('CNC_BOT_TABLE_OWNER_USERNAME'),
                            help='Username владельца таблицы в Django (по умолчанию из CNC_BOT_TABLE_OWNER_USERNAME)')
        parser.add_argument('--title-fragment', type=str, default=os.getenv('CNC_TABLE_TITLE_FRAGMENT'),
                            help='Фрагмент названия таблицы для поиска (по умолчанию из CNC_TABLE_TITLE_FRAGMENT)')
        parser.add_argument('--section-type', type=str, default=os.getenv('CNC_SECTION_TYPE', 'rangers'),
                            help='Тип секции (по умолчанию rangers)')

    def handle(self, *args, **options):
        owner_username = options['owner']
        title_fragment = options['title_fragment']
        section_type = options['section_type']

        if not owner_username:
            raise CommandError("Не указан владелец. Задайте CNC_BOT_TABLE_OWNER_USERNAME или используйте --owner")
        if not title_fragment:
            raise CommandError(
                "Не указано название таблицы. Задайте CNC_TABLE_TITLE_FRAGMENT или используйте --title-fragment")

        # Настройки Nextcloud
        nc_base = os.getenv('NEXTCLOUD_BASE_URL', 'https://cloud.tassadara.ru').rstrip('/')
        nc_user = os.getenv('NEXTCLOUD_USERNAME')
        nc_pass = os.getenv('NEXTCLOUD_PASSWORD') or os.getenv('NEXTCLOUD_APP_TOKEN')

        if not nc_user or not nc_pass:
            raise CommandError("Не заданы NEXTCLOUD_USERNAME и NEXTCLOUD_PASSWORD (или APP_TOKEN) в окружении.")

        self.stdout.write(f"🔍 Поиск таблицы '{title_fragment}' для пользователя '{owner_username}' в Nextcloud...")

        # 1. Получаем или создаем пользователя в Django
        User = get_user_model()
        try:
            owner = User.objects.get(username=owner_username)
            self.stdout.write(f"✅ Пользователь '{owner_username}' найден в БД (ID: {owner.id})")
        except User.DoesNotExist:
            owner = User.objects.create_user(username=owner_username, password="unused")
            self.stdout.write(f"🆕 Пользователь '{owner_username}' создан в БД (ID: {owner.id})")

        # 2. Ищем файл в Nextcloud через WebDAV API
        # Используем поиск по файлам (PROPFIND с фильтром или просто перебор, если API сложное)
        # Самый надежный способ без сложного XML - попробовать угадать путь или использовать search API,
        # но стандартный WebDAV поиск требует XML. Попробуем простой подход: список файлов в корне или папке Documents.

        # Путь по умолчанию, где OnlyOffice обычно хранит файлы
        search_path = f"/remote.php/dav/files/{nc_user}/"

        headers = {
            "Depth": "infinity",  # Рекурсивный поиск
            "Content-Type": "application/xml; charset=utf-8",
        }
        # XML запрос для поиска всех файлов с расширением .docx, .xlsx, .odt и т.д.
        # Но нам нужно найти конкретное имя.
        # Упрощение: получим список всех файлов и отфильтруем локально, так надежнее для скрипта.

        xml_body = """<?xml version="1.0"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop>
                <d:displayname/>
                <d:getcontenttype/>
                <d:resourcetype/>
                <d:getcontentlength/>
                <oc:fileid/>
                <oc:permissions/>
            </d:prop>
        </d:propfind>"""

        try:
            response = requests.request(
                "PROPFIND",
                f"{nc_base}/remote.php/dav/files/{nc_user}/",
                auth=(nc_user, nc_pass),
                headers=headers,
                data=xml_body,
                timeout=30
            )
            response.raise_for_status()
        except Exception as e:
            raise CommandError(f"Ошибка подключения к Nextcloud WebDAV: {e}")

        # Парсим XML ответ (простой парсинг без тяжелых библиотек для надежности)
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(response.content)
            ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}

            found_file_path = None
            found_file_id = None

            for resp in root.findall('.//d:response', ns):
                href = resp.find('d:href', ns)
                prop = resp.find('d:propstat/d:prop', ns)
                if href is None or prop is None:
                    continue

                path = href.text
                display_name_elem = prop.find('d:displayname', ns)
                res_type = prop.find('d:resourcetype', ns)

                # Пропускаем папки
                if res_type is not None and res_type.find('d:collection', ns) is not None:
                    continue

                display_name = display_name_elem.text if display_name_elem is not None else path.split('/')[-1]

                # Проверка имени
                if title_fragment.lower() in display_name.lower():
                    found_file_path = path
                    # Пытаемся получить ID файла
                    file_id_elem = prop.find('oc:fileid', ns)
                    found_file_id = file_id_elem.text if file_id_elem is not None else None
                    self.stdout.write(f"🎯 Найден файл: {display_name} (Path: {path}, ID: {found_file_id})")
                    break

            if not found_file_path:
                raise CommandError(
                    f"Файл с названием '{title_fragment}' не найден в Nextcloud у пользователя {nc_user}. Проверьте имя и права доступа.")

        except ET.ParseError as e:
            raise CommandError(f"Ошибка парсинга ответа Nextcloud (XML): {e}. Ответ: {response.content[:200]}")

        # 3. Скачиваем содержимое файла (только для .json или экспортированного onlyoffice формата?)
        # Проблема: OnlyOffice хранит данные в бинарном формате (.docx/.xlsx) внутри Nextcloud.
        # Django бот ожидает JSON структуру в поле content.
        # Решение: Если файл уже создан через UI OnlyOffice, он может быть в бинарном формате.
        # НО: В предыдущих версиях проекта CNC Office, возможно, использовался JSON-формат напрямую.
        # Проверим расширение. Если это .json, читаем напрямую. Если .xlsx/.docx - нам нужен конвертер или
        # мы должны считать, что файл был создан через API проекта ранее.

        file_url = f"{nc_base}{found_file_path}"
        # Кодирование пути для URL
        from urllib.parse import quote
        file_url = f"{nc_base}/remote.php/dav/files/{nc_user}/{quote(found_file_path.lstrip('/'))}"

        # Попытка скачать
        r_file = requests.get(file_url, auth=(nc_user, nc_pass), timeout=30)
        r_file.raise_for_status()

        content_data = None
        filename_lower = found_file_path.lower()

        if filename_lower.endswith('.json'):
            try:
                content_data = r_file.json()
                self.stdout.write("✅ Файл распознан как JSON. Загружаем напрямую.")
            except json.JSONDecodeError:
                raise CommandError("Файл имеет расширение .json, но не является валидным JSON.")
        elif filename_lower.endswith(('.xlsx', '.xls')):
            # Если это Excel, нам нужно спарсить его в структуру Sheets
            # Для этого используем openpyxl, если он установлен, или вернем ошибку с инструкцией
            try:
                import openpyxl
                from io import BytesIO
                wb = openpyxl.load_workbook(BytesIO(r_file.content), data_only=True)
                sheets_data = []
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    data = []
                    for row in ws.iter_rows(values_only=True):
                        # Преобразуем кортеж в список, заменяем None на пустую строку
                        clean_row = [str(cell) if cell is not None else "" for cell in row]
                        data.append(clean_row)
                    sheets_data.append({"name": sheet_name, "data": data})

                content_data = {"sheets": sheets_data}
                self.stdout.write(f"✅ Файл Excel распарсен. Найдено листов: {len(sheets_data)}")
            except ImportError:
                raise CommandError(
                    "Файл Excel, но библиотека openpyxl не установлена. Установите: pip install openpyxl")
            except Exception as e:
                raise CommandError(f"Ошибка парсинга Excel: {e}")
        else:
            # Попытка прочитать как JSON anyway (иногда файлы сохраняются без расширения или как текст)
            try:
                content_data = r_file.json()
                self.stdout.write("✅ Файл распознан как JSON (без расширения).")
            except:
                raise CommandError(f"Неподдерживаемый формат файла '{found_file_path}'. Ожидался .json или .xlsx")

        # 4. Сохраняем в БД
        table, created = SectionTable.objects.update_or_create(
            owner=owner,
            section_type=section_type,
            defaults={
                'title': title_fragment,  # Или можно взять точное имя из файла
                'content': content_data,
                'onlyoffice_file_id': found_file_id,  # Если есть поле, иначе игнор
                'onlyoffice_url': file_url  # Для справки
            }
        )

        # Примечание: если в модели SectionTable нет полей onlyoffice_file_id/url, они будут проигнорированы или вызовут ошибку.
        # Адаптируем под стандартную модель (обычно там только owner, title, section_type, content).

        # Повторное сохранение только безопасных полей
        table.title = title_fragment  # Можно обновить на полное имя файла если нужно
        table.content = content_data
        table.save()

        status_msg = "создана" if created else "обновлена"
        self.stdout.write(self.style.SUCCESS(f"✅ Таблица успешно {status_msg} в БД!"))
        self.stdout.write(f"   ID: {table.id}")
        self.stdout.write(f"   Владелец: {owner.username}")
        self.stdout.write(f"   Листов: {len(content_data.get('sheets', []))}")
        self.stdout.write("\n🚀 Теперь перезапустите бота: docker compose restart vk_bot")
