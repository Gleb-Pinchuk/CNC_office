"""
VK-бот: работа с таблицей CNC Office (SectionTable) через /api/bot/gateway/.
Секреты только из переменных окружения.
"""

from __future__ import annotations

import json
import os
import random
import re
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- env ---
VK_TOKEN = os.getenv("VK_TOKEN", "").strip()
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", "0"))
CNC_API_BASE = os.getenv("CNC_API_BASE", "http://web:8000/api").rstrip("/")
CNC_BOT_SECRET = os.getenv(
    "CNC_BOT_SECRET", os.getenv("CNC_BOT_API_SECRET", "")
).strip()
CNC_SECTION_TYPE = os.getenv("CNC_SECTION_TYPE", "rangers").strip()
CNC_TABLE_TITLE_FRAGMENT = os.getenv(
    "CNC_TABLE_TITLE_FRAGMENT", "киберрейнджеры"
).strip()
DIRS_RAW = os.getenv("CNC_DIRECTION_SHEETS", "ЧПУ,РОБО,Аэро,микро")
SPREADSHEETS = [x.strip() for x in DIRS_RAW.split(",") if x.strip()]
TZ_NAME = os.getenv("TIMEZONE", "Europe/Moscow")

FIO_COL_DEFAULT = 2  # 3-й столбец
GROUP_COL_DEFAULT = 1  # 2-й столбец (Группа)
STATUS_COL_DEFAULT = 11  # 12-й столбец (учится/отчислен)
NO_REMARK_TEXT = "Замечаний нет"

# Проверка обязательных переменных окружения
REQUIRED_ENV = {
    "VK_TOKEN": VK_TOKEN,
    "VK_GROUP_ID": str(VK_GROUP_ID) if VK_GROUP_ID else "",
    "CNC_BOT_SECRET": CNC_BOT_SECRET,
    "CNC_SECTION_TYPE": CNC_SECTION_TYPE,
}

for var_name, var_value in REQUIRED_ENV.items():
    if not var_value:
        logger.error(f"❌ Критическая ошибка: переменная окружения {var_name} не задана!")
        raise ValueError(f"Переменная окружения {var_name} обязательна")

if VK_GROUP_ID == 0:
    logger.error("❌ VK_GROUP_ID должен быть положительным числом (ID группы VK)")
    raise ValueError("VK_GROUP_ID должен быть положительным числом")

logger.info(f"✅ Конфигурация загружена:")
logger.info(f"   VK_GROUP_ID: {VK_GROUP_ID}")
logger.info(f"   CNC_API_BASE: {CNC_API_BASE}")
logger.info(f"   CNC_SECTION_TYPE: {CNC_SECTION_TYPE}")
logger.info(f"   CNC_TABLE_TITLE_FRAGMENT: {CNC_TABLE_TITLE_FRAGMENT}")
logger.info(f"   Направления: {SPREADSHEETS}")


def _tz_now() -> datetime:
    if ZoneInfo:
        return datetime.now(tz=ZoneInfo(TZ_NAME))
    return datetime.now()


def _headers() -> dict:
    return {"Content-Type": "application/json", "X-CNC-Bot-Token": CNC_BOT_SECRET}


class CNCApiError(Exception):
    """Исключение для ошибок CNC API"""
    pass


class CNCApi:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self._table_cache: Optional[dict] = None

    def post(self, action: str, payload: dict, retries: int = 3) -> dict:
        """Отправка запроса к API с повторными попытками при ошибке подключения"""
        body = {"action": action, **payload}
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                logger.debug(f"[Попытка {attempt}/{retries}] POST {action}: {body}")
                r = requests.post(
                    f"{self.base}/bot/gateway/",
                    json=body,
                    headers=_headers(),
                    timeout=30
                )
                logger.debug(f"Ответ API: статус={r.status_code}, тело={r.text[:500]}")

                if r.status_code >= 400:
                    error_detail = r.text or str(r.status_code)
                    if r.status_code == 503:
                        # Сервис недоступен - пробуем снова
                        logger.warning(f"API временно недоступен (503), попытка {attempt}/{retries}")
                        last_error = CNCApiError(f"Сервис временно недоступен: {error_detail}")
                        continue
                    raise CNCApiError(f"Ошибка API ({r.status_code}): {error_detail}")

                return r.json()

            except requests.exceptions.ConnectionError as e:
                last_error = CNCApiError(f"Не удалось подключиться к API ({self.base}): {e}")
                logger.warning(f"Ошибка подключения (попытка {attempt}/{retries}): {last_error}")
                if attempt < retries:
                    time.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                break
            except requests.exceptions.Timeout as e:
                last_error = CNCApiError(f"Таймаут подключения к API: {e}")
                logger.warning(f"Таймаут (попытка {attempt}/{retries}): {last_error}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                break
            except Exception as e:
                raise CNCApiError(f"Неожиданная ошибка: {e}")

        raise last_error

    def lookup_table(self, force_refresh: bool = False) -> dict:
        """Поиск таблицы с кэшированием результата"""
        if self._table_cache and not force_refresh:
            return self._table_cache

        logger.info(f"🔍 Поиск таблицы: section_type={CNC_SECTION_TYPE}, title_contains={CNC_TABLE_TITLE_FRAGMENT}")

        result = self.post(
            "lookup_table",
            {
                "section_type": CNC_SECTION_TYPE,
                "title_contains": CNC_TABLE_TITLE_FRAGMENT,
            },
        )

        self._table_cache = result
        logger.info(f"✅ Таблица найдена: id={result.get('id')}, title={result.get('title')}")
        return result

    def invalidate_cache(self):
        """Сброс кэша таблицы"""
        self._table_cache = None
        logger.info("Кэш таблицы сброшен")

    def get_sheet_data(
            self, table_id: int, sheet_name: Optional[str]
    ) -> List[List[Any]]:
        data = self.post(
            "get_sheet_data",
            {"table_id": table_id, "sheet_name": sheet_name or ""},
        )
        return data.get("data") or []

    def set_cell(
            self, table_id: int, sheet_name: Optional[str], row: int, col: int, value: str
    ) -> None:
        self.post(
            "set_cell",
            {
                "table_id": table_id,
                "sheet_name": sheet_name or "",
                "row": row,
                "col": col,
                "value": value,
            },
        )
        logger.info(f"✏️ Ячейка обновлена: [{sheet_name}] R{row}C{col} = {value}")


class StudentBot:
    def __init__(self):
        if not VK_TOKEN:
            raise ValueError("VK_TOKEN не задан")

        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.long_poll = VkBotLongPoll(self.vk_session, VK_GROUP_ID)
        self.api = CNCApi(CNC_API_BASE)
        self.table_info: Optional[dict] = None

        logger.info("🤖 Бот инициализирован")

    def ensure_table_loaded(self):
        """Гарантирует загрузку информации о таблице"""
        if self.table_info is None:
            try:
                self.table_info = self.api.lookup_table()
            except CNCApiError as e:
                logger.error(f"❌ Не удалось загрузить таблицу: {e}")
                raise

    def get_directions(self) -> List[str]:
        """Получение списка направлений (листов таблицы)"""
        try:
            self.ensure_table_loaded()
            table_id = self.table_info["id"]

            # Получаем список листов из таблицы
            result = self.api.post("list_sheets", {"table_id": table_id})
            sheet_names = result.get("sheet_names", [])

            # Фильтруем только нужные направления
            directions = []
            for sheet in sheet_names:
                sheet_lower = sheet.lower()
                for dir_name in SPREADSHEETS:
                    if dir_name.lower() in sheet_lower:
                        directions.append(sheet)
                        break

            if not directions:
                logger.warning(f"⚠️ Не найдено листов для направлений {SPREADSHEETS}. Доступные листы: {sheet_names}")
                # Возвращаем все листы если ни один не подошел
                directions = sheet_names

            return directions

        except CNCApiError as e:
            logger.error(f"❌ Ошибка получения направлений: {e}")
            raise

    def get_students_for_direction(self, direction: str) -> List[Dict[str, Any]]:
        """Получение списка студентов для направления"""
        try:
            self.ensure_table_loaded()
            table_id = self.table_info["id"]

            data = self.api.get_sheet_data(table_id, direction)
            students = []

            if len(data) < 2:
                logger.warning(f"⚠️ Лист '{direction}' пуст или содержит менее 2 строк")
                return students

            # Предполагаем что первая строка - заголовки, вторая+ - данные
            for row_idx, row in enumerate(data[1:], start=1):
                if not row or all(cell == "" for cell in row):
                    continue

                fio = row[FIO_COL_DEFAULT] if len(row) > FIO_COL_DEFAULT else ""
                group = row[GROUP_COL_DEFAULT] if len(row) > GROUP_COL_DEFAULT else ""
                status = row[STATUS_COL_DEFAULT] if len(row) > STATUS_COL_DEFAULT else ""

                # Пропускаем отчисленных
                if status and "отчислен" in status.lower():
                    continue

                if fio:
                    students.append({
                        "fio": fio,
                        "group": group,
                        "row_index": row_idx,
                        "direction": direction,
                    })

            logger.info(f"📋 Найдено {len(students)} студентов в направлении '{direction}'")
            return students

        except CNCApiError as e:
            logger.error(f"❌ Ошибка получения студентов: {e}")
            raise

    def add_remark(self, student_fio: str, direction: str, remark_text: str) -> bool:
        """Добавление замечания студенту"""
        try:
            self.ensure_table_loaded()
            table_id = self.table_info["id"]

            # Находим студента
            students = self.get_students_for_direction(direction)
            student_row = None

            for student in students:
                if student_fio.lower() in student["fio"].lower() or student["fio"].lower() in student_fio.lower():
                    student_row = student
                    break

            if not student_row:
                logger.warning(f"⚠️ Студент '{student_fio}' не найден в направлении '{direction}'")
                return False

            # Колонка для замечаний (предположим, это 13-я колонка, индекс 12)
            remark_col = 12

            # Получаем текущее замечание
            current_data = self.api.get_sheet_data(table_id, direction)
            if len(current_data) > student_row["row_index"]:
                row_data = current_data[student_row["row_index"]]
                current_remark = row_data[remark_col] if len(row_data) > remark_col else ""

                # Добавляем новое замечание
                timestamp = _tz_now().strftime("%d.%m.%Y %H:%M")
                new_remark = f"{timestamp}: {remark_text}"

                if current_remark and current_remark != NO_REMARK_TEXT:
                    new_remark = f"{current_remark}\n{new_remark}"

                self.api.set_cell(table_id, direction, student_row["row_index"], remark_col, new_remark)
                logger.info(f"✅ Добавлено замечание для {student_fio}: {remark_text}")
                return True

            return False

        except CNCApiError as e:
            logger.error(f"❌ Ошибка добавления замечания: {e}")
            raise

    def run(self):
        """Запуск бота"""
        logger.info("🚀 Запуск VK бота...")

        try:
            # Проверяем подключение к API при старте
            logger.info("🔄 Проверка подключения к CNC API...")
            self.ensure_table_loaded()
            logger.info("✅ Подключение к CNC API успешно")

        except CNCApiError as e:
            logger.error(f"❌ Не удалось подключиться к CNC API при старте: {e}")
            logger.error("💡 Убедитесь что:")
            logger.error("   1. Контейнер 'web' запущен и доступен по адресу http://web:8000")
            logger.error("   2. Переменные окружения CNC_BOT_SECRET и CNC_BOT_TABLE_OWNER_USERNAME заданы корректно")
            logger.error("   3. В базе данных существует таблица SectionTable с правильным владельцем")
            raise

        logger.info("📡 Ожидание сообщений от VK LongPoll...")

        for event in self.long_poll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self._handle_message(event.obj.message)
            except Exception as e:
                logger.error(f"❌ Ошибка обработки события: {e}", exc_info=True)

    def _handle_message(self, message: dict):
        """Обработка входящего сообщения"""
        peer_id = message.get("peer_id")
        text = message.get("text", "").strip().lower()

        logger.info(f"💬 Сообщение от {peer_id}: {text}")

        try:
            if text == "начать" or text == "старт":
                directions = self.get_directions()
                response = "📚 Доступные направления:\n"
                for i, dir_name in enumerate(directions, 1):
                    response += f"{i}. {dir_name}\n"
                response += "\nВыберите направление (номер или название):"
                self._send_message(peer_id, response)

            elif text.isdigit():
                # Выбор направления по номеру
                directions = self.get_directions()
                idx = int(text) - 1
                if 0 <= idx < len(directions):
                    direction = directions[idx]
                    students = self.get_students_for_direction(direction)
                    response = f"👥 Студенты направления '{direction}':\n"
                    for i, student in enumerate(students[:20], 1):  # Максимум 20
                        response += f"{i}. {student['fio']} ({student['group']})\n"
                    if len(students) > 20:
                        response += f"... и ещё {len(students) - 20}"
                    self._send_message(peer_id, response)
                else:
                    self._send_message(peer_id, "❌ Неверный номер направления")

            else:
                # Поиск студента по ФИО
                directions = self.get_directions()
                found_students = []
                for direction in directions:
                    students = self.get_students_for_direction(direction)
                    for student in students:
                        if text in student["fio"].lower():
                            found_students.append(student)

                if found_students:
                    response = "🔍 Найдены студенты:\n"
                    for student in found_students[:10]:
                        response += f"- {student['fio']} ({student['direction']}, {student['group']})\n"
                    if len(found_students) > 10:
                        response += f"... и ещё {len(found_students) - 10}"
                    self._send_message(peer_id, response)
                else:
                    self._send_message(peer_id, "❌ Студент не найден. Попробуйте ввести ФИО полностью или частично.")

        except CNCApiError as e:
            error_msg = f"❌ Ошибка работы с таблицей: {e}"
            logger.error(error_msg)
            self._send_message(peer_id, error_msg)
        except Exception as e:
            error_msg = f"❌ Внутренняя ошибка бота: {e}"
            logger.error(error_msg, exc_info=True)
            self._send_message(peer_id, error_msg)

    def _send_message(self, peer_id: int, text: str):
        """Отправка сообщения пользователю"""
        try:
            self.vk_session.method(
                "messages.send",
                {
                    "peer_id": peer_id,
                    "message": text,
                    "random_id": random.randint(0, 2 ** 31),
                },
            )
            logger.debug(f"✅ Сообщение отправлено пользователю {peer_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")


if __name__ == "__main__":
    bot = StudentBot()
    bot.run()
