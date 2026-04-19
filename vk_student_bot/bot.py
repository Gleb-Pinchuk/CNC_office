"""
VK-бот мониторинга студентов: данные из БД (SectionTable) через /api/bot/gateway/,
синхронизация с Nextcloud — Celery на стороне Django (каждые 5 мин).
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

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

REQUIRED_ENV = {
    "VK_TOKEN": VK_TOKEN,
    "VK_GROUP_ID": str(VK_GROUP_ID) if VK_GROUP_ID else "",
    "CNC_BOT_SECRET": CNC_BOT_SECRET,
    "CNC_SECTION_TYPE": CNC_SECTION_TYPE,
}
for var_name, var_value in REQUIRED_ENV.items():
    if not var_value:
        logger.error("Переменная окружения %s обязательна", var_name)
        raise ValueError(f"Переменная окружения {var_name} обязательна")
if VK_GROUP_ID == 0:
    raise ValueError("VK_GROUP_ID должен быть положительным числом")


def _tz_now() -> datetime:
    if ZoneInfo:
        return datetime.now(tz=ZoneInfo(TZ_NAME))
    return datetime.now()


def _headers() -> dict:
    return {"Content-Type": "application/json", "X-CNC-Bot-Token": CNC_BOT_SECRET}


class CNCApiError(Exception):
    pass


class CNCApi:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self._table_cache: Optional[dict] = None

    def post(self, action: str, payload: dict, retries: int = 3) -> dict:
        body = {"action": action, **payload}
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    f"{self.base}/bot/gateway/",
                    json=body,
                    headers=_headers(),
                    timeout=30,
                )
                if r.status_code >= 400:
                    error_detail = r.text or str(r.status_code)
                    if r.status_code == 503:
                        last_error = CNCApiError(f"Сервис временно недоступен: {error_detail}")
                        continue
                    try:
                        detail = r.json().get("detail", error_detail)
                    except Exception:
                        detail = error_detail
                    raise CNCApiError(f"Ошибка API ({r.status_code}): {detail}")
                return r.json()
            except requests.exceptions.ConnectionError as e:
                last_error = CNCApiError(f"Нет подключения к API: {e}")
                if attempt < retries:
                    time.sleep(2**attempt)
                    continue
                break
            except requests.exceptions.Timeout as e:
                last_error = CNCApiError(f"Таймаут: {e}")
                if attempt < retries:
                    time.sleep(2**attempt)
                    continue
                break
            except CNCApiError:
                raise
            except Exception as e:
                raise CNCApiError(str(e)) from e
        raise last_error

    def lookup_table(self, force_refresh: bool = False) -> dict:
        if self._table_cache and not force_refresh:
            return self._table_cache
        result = self.post(
            "lookup_table",
            {
                "section_type": CNC_SECTION_TYPE,
                "title_contains": CNC_TABLE_TITLE_FRAGMENT,
            },
        )
        self._table_cache = result
        return result

    def invalidate_cache(self):
        self._table_cache = None

    def get_sheet_data(self, table_id: int, sheet_name: Optional[str]) -> List[List[Any]]:
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

    def list_groups(self, table_id: int, sheet_name: str) -> List[str]:
        r = self.post("list_groups", {"table_id": table_id, "sheet_name": sheet_name})
        return r.get("groups") or []

    def search_students(
        self,
        table_id: int,
        sheet_name: str,
        *,
        group: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[dict]:
        body: Dict[str, Any] = {"table_id": table_id, "sheet_name": sheet_name}
        if group:
            body["group"] = group
        if query:
            body["query"] = query
        r = self.post("search_students", body)
        return r.get("students") or []

    def set_student_remark(
        self,
        table_id: int,
        sheet_name: str,
        student_fio: str,
        remark_date: str,
        remark_text: Optional[str] = None,
        group: Optional[str] = None,
    ) -> dict:
        body: Dict[str, Any] = {
            "table_id": table_id,
            "sheet_name": sheet_name,
            "student_fio": student_fio,
            "remark_date": remark_date,
        }
        if remark_text is not None:
            body["remark_text"] = remark_text
        if group:
            body["group"] = group
        return self.post("set_student_remark", body)


@dataclass
class UserCtx:
    direction: Optional[str] = None
    group: Optional[str] = None


def _pick_direction(directions: List[str], token: str) -> Optional[str]:
    t = token.strip().lower()
    for d in directions:
        if t == d.lower() or t in d.lower() or d.lower() in t:
            return d
    if token.strip().isdigit():
        i = int(token.strip()) - 1
        if 0 <= i < len(directions):
            return directions[i]
    return None


class StudentBot:
    """Сценарии: направление → группа → поиск; замечание с датой через API."""

    def __init__(self):
        if not VK_TOKEN:
            raise ValueError("VK_TOKEN не задан")
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.long_poll = VkBotLongPoll(self.vk_session, VK_GROUP_ID)
        self.api = CNCApi(CNC_API_BASE)
        self.table_info: Optional[dict] = None
        self._ctx: Dict[int, UserCtx] = {}

    def ensure_table_loaded(self):
        if self.table_info is None:
            self.table_info = self.api.lookup_table()

    def _ctx_for(self, peer_id: int) -> UserCtx:
        if peer_id not in self._ctx:
            self._ctx[peer_id] = UserCtx()
        return self._ctx[peer_id]

    def get_directions(self) -> List[str]:
        self.ensure_table_loaded()
        table_id = self.table_info["id"]
        result = self.api.post("list_sheets", {"table_id": table_id})
        sheet_names = result.get("sheet_names", [])
        directions = []
        for sheet in sheet_names:
            sl = sheet.lower()
            for dir_name in SPREADSHEETS:
                if dir_name.lower() in sl:
                    directions.append(sheet)
                    break
        if not directions:
            directions = sheet_names
        return directions

    def run(self):
        logger.info("Запуск VK-бота мониторинга…")
        self.ensure_table_loaded()
        logger.info("Таблица id=%s", self.table_info.get("id"))
        for event in self.long_poll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self._handle_message(event.obj.message)
            except Exception as e:
                logger.error("Ошибка обработки события: %s", e, exc_info=True)

    def _handle_message(self, message: dict):
        peer_id = message.get("peer_id")
        raw = message.get("text", "").strip()
        text = raw.lower()
        ctx = self._ctx_for(peer_id)

        logger.info("Сообщение peer=%s: %s", peer_id, raw[:200])

        try:
            if text in ("помощь", "help", "?", "меню"):
                self._send_help(peer_id)
                return

            if text in ("начать", "старт", "направление", "направления"):
                dirs = self.get_directions()
                lines = ["📚 Направления (листы Excel):"]
                for i, d in enumerate(dirs, 1):
                    lines.append(f"{i}. {d}")
                lines.append("")
                lines.append("Выберите: номер или название, затем «группы» / «группа …».")
                self._send(peer_id, "\n".join(lines))
                return

            dirs = self.get_directions()
            picked = _pick_direction(dirs, raw.strip())
            if picked and (raw.strip().isdigit() or len(raw.strip()) >= 2):
                ctx.direction = picked
                self._send(
                    peer_id,
                    f"✅ Направление: {picked}\n"
                    f"Дальше: «группы» — список групп, «группа ИВТ-1», "
                    f"«кто Иванов» — поиск.\n"
                    f"Замечание: «замечание {picked} ДД.ММ.ГГГГ ФИО | текст»\n"
                    f"Без замечаний: «нет замечаний {picked} ДД.ММ.ГГГГ ФИО»",
                )
                return

            m_groups = re.match(r"^группы?\s*$", text, re.I)
            if m_groups:
                self._cmd_groups(peer_id, ctx, None)
                return

            m_group = re.match(r"^группа\s+(.+)$", raw, re.I)
            if m_group:
                ctx.group = m_group.group(1).strip()
                self._send(peer_id, f"✅ Группа: {ctx.group}")
                return

            m_who = re.match(r"^кто\s+(.+)$", raw, re.I)
            if m_who:
                self._cmd_who(peer_id, ctx, m_who.group(1).strip())
                return

            m_rm = re.match(
                r"^замечание\s+(.+?)\s+(\d{1,2}\.\d{1,2}\.\d{2,4})\s+(.+?)\s*\|\s*(.+)$",
                raw,
                re.I | re.S,
            )
            if m_rm:
                sheet = m_rm.group(1).strip()
                dt = m_rm.group(2).strip()
                fio = m_rm.group(3).strip()
                rtxt = m_rm.group(4).strip()
                self._cmd_remark(peer_id, sheet, dt, fio, rtxt, ctx.group)
                return

            m_no = re.match(
                r"^(?:нет\s+замечаний|замечаний\s+нет)\s+(.+?)\s+(\d{1,2}\.\d{1,2}\.\d{2,4})\s+(.+)$",
                raw,
                re.I | re.S,
            )
            if m_no:
                sheet = m_no.group(1).strip()
                dt = m_no.group(2).strip()
                fio = m_no.group(3).strip()
                self._cmd_remark(peer_id, sheet, dt, fio, None, ctx.group)
                return

            if len(text) >= 3:
                self._cmd_search_all(peer_id, raw.strip())
                return

            self._send(peer_id, "Не понял команду. Напишите «помощь».")

        except CNCApiError as e:
            self._send(peer_id, f"❌ {e}")
        except Exception as e:
            logger.exception("handle_message")
            self._send(peer_id, f"❌ Ошибка: {e}")

    def _send_help(self, peer_id: int):
        self._send(
            peer_id,
            "📖 Мониторинг студентов\n\n"
            "• начать — список направлений\n"
            "• номер или название листа — выбрать направление\n"
            "• группы — список групп (нужно выбранное направление)\n"
            "• группа ИВТ-1 — фильтр по группе\n"
            "• кто Иванов — поиск в текущем направлении\n"
            "• замечание <лист> ДД.ММ.ГГГГ ФИО | текст замечания\n"
            "• нет замечаний <лист> ДД.ММ.ГГГГ ФИО\n\n"
            "Лист укажите как в Excel (например РОБО). "
            "Синхронизация с Nextcloud — каждые 5 мин (Celery).",
        )

    def _resolve_sheet(self, token: str) -> Optional[str]:
        dirs = self.get_directions()
        return _pick_direction(dirs, token)

    def _cmd_groups(self, peer_id: int, ctx: UserCtx, _arg):
        if not ctx.direction:
            self._send(peer_id, "Сначала выберите направление (начать → номер).")
            return
        self.ensure_table_loaded()
        tid = self.table_info["id"]
        groups = self.api.list_groups(tid, ctx.direction)
        if not groups:
            self._send(peer_id, "Группы не найдены.")
            return
        self._send(peer_id, "📂 Группы:\n" + "\n".join(f"• {g}" for g in groups[:40]))

    def _cmd_who(self, peer_id: int, ctx: UserCtx, q: str):
        if not ctx.direction:
            self._send(peer_id, "Сначала выберите направление.")
            return
        self.ensure_table_loaded()
        tid = self.table_info["id"]
        st = self.api.search_students(
            tid, ctx.direction, group=ctx.group, query=q
        )
        if not st:
            self._send(peer_id, "Никого не найдено.")
            return
        lines = [f"Найдено: {len(st)}"]
        for s in st[:15]:
            lines.append(f"• {s.get('fio')} ({s.get('group')})")
        if len(st) > 15:
            lines.append(f"… ещё {len(st) - 15}")
        self._send(peer_id, "\n".join(lines))

    def _cmd_search_all(self, peer_id: int, q: str):
        self.ensure_table_loaded()
        tid = self.table_info["id"]
        found = []
        for d in self.get_directions():
            for s in self.api.search_students(tid, d, query=q.lower()):
                found.append((d, s))
        if not found:
            self._send(peer_id, "❌ Не найдено. Уточните ФИО или выберите направление.")
            return
        lines = []
        for d, s in found[:12]:
            lines.append(f"• {s.get('fio')} — {d}, гр. {s.get('group')}")
        if len(found) > 12:
            lines.append(f"… всего совпадений: {len(found)}")
        self._send(peer_id, "\n".join(lines))

    def _cmd_remark(
        self,
        peer_id: int,
        sheet_token: str,
        date_str: str,
        fio: str,
        text: Optional[str],
        group: Optional[str],
    ):
        sheet = self._resolve_sheet(sheet_token) or sheet_token
        self.ensure_table_loaded()
        tid = self.table_info["id"]
        try:
            self.api.set_student_remark(
                tid,
                sheet,
                fio,
                date_str,
                remark_text=text,
                group=group,
            )
        except CNCApiError as e:
            if "409" in str(e) or "Несколько" in str(e):
                self._send(
                    peer_id,
                    "Несколько студентов подходят. Укажите «группа …» и повторите.",
                )
                return
            raise
        if text:
            self._send(peer_id, f"✅ Замечание на {date_str} записано для {fio}.")
        else:
            self._send(peer_id, f"✅ На {date_str} для {fio}: замечаний нет.")

    def _send(self, peer_id: int, text: str):
        self.vk_session.method(
            "messages.send",
            {
                "peer_id": peer_id,
                "message": text[:3900],
                "random_id": random.randint(0, 2**31),
            },
        )


if __name__ == "__main__":
    StudentBot().run()
