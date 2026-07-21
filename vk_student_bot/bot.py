"""VK-бот мониторинга студентов с кнопочным UX."""

from __future__ import annotations

import atexit
import json
import logging
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TextIO

import requests
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

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
CNC_API_BASE = os.getenv("CNC_API_BASE", "http://127.0.0.1:8000/api").rstrip("/")
CNC_BOT_SECRET = os.getenv("CNC_BOT_SECRET", os.getenv("CNC_BOT_API_SECRET", "")).strip()
CNC_SECTION_TYPE = os.getenv("CNC_SECTION_TYPE", "rangers").strip()
CNC_TABLE_TITLE_FRAGMENT = os.getenv("CNC_TABLE_TITLE_FRAGMENT", "киберрейнджеры").strip()
DIRS_RAW = os.getenv("CNC_DIRECTION_SHEETS", "ЧПУ,РОБО,Аэро,микро")
SPREADSHEETS = [x.strip() for x in DIRS_RAW.split(",") if x.strip()]
TZ_NAME = os.getenv("TIMEZONE", "Europe/Moscow")
GROUPS_JSON = os.getenv("CNC_TABLE_GROUPS_JSON", "").strip()
# Тишина long-poll до soft reconnect (сек). Успешный check() с пустыми events тоже «живая» тик.
BOT_WATCHDOG_IDLE_SEC = int(os.getenv("BOT_WATCHDOG_IDLE_SEC", "300"))
# После soft reconnect без нового heartbeat — hard exit для supervisor/Docker.
BOT_WATCHDOG_HARD_AFTER_SEC = int(os.getenv("BOT_WATCHDOG_HARD_AFTER_SEC", "60"))


def _default_table_groups() -> List[dict]:
    return [
        {
            "key": "production",
            "title": "Производственная",
            "table_title": "Рейнджеры_производственная_группа",
            "section_type": "rangers",
            "directions": ["ЧПУ", "МИКРО", "АЭРО", "РОБО"],
        },
        {
            "key": "operations",
            "title": "Эксплуатация",
            "table_title": "Рейнджеры_группа_эксплуатации",
            "section_type": "rangers",
            "directions": ["ХимБио", "ЭлМонтаж", "БИМ", "ПромБез", "КиПиА", "Автоматика"],
        },
        {
            "key": "integration",
            "title": "Интеграционная",
            "table_title": "Рейнджеры_интеграционная_группа",
            "section_type": "rangers",
            "directions": ["Юриспруденция", "Медицина", "Преподавание", "Экономика", "Алабуга Старт"],
        },
        {
            "key": "programming",
            "title": "Программирование",
            "table_title": "Рейнджеры_группа_программирования",
            "section_type": "rangers",
            "directions": ["Python", "Бизнес-информатика"],
        },
    ]


def _load_table_groups() -> List[dict]:
    if not GROUPS_JSON:
        return _default_table_groups()
    try:
        raw = json.loads(GROUPS_JSON)
        if not isinstance(raw, list):
            raise ValueError("CNC_TABLE_GROUPS_JSON должен быть массивом")
        out = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or f"group_{idx+1}").strip()
            title = str(item.get("title") or key).strip()
            table_title = str(item.get("table_title") or item.get("title_fragment") or "").strip()
            section_type = str(item.get("section_type") or CNC_SECTION_TYPE).strip()
            directions = [str(x).strip() for x in (item.get("directions") or []) if str(x).strip()]
            if not table_title:
                continue
            out.append(
                {
                    "key": key,
                    "title": title,
                    "table_title": table_title,
                    "section_type": section_type,
                    "directions": directions,
                }
            )
        return out or _default_table_groups()
    except Exception:
        logger.exception("Не удалось прочитать CNC_TABLE_GROUPS_JSON, используем defaults")
        return _default_table_groups()


TABLE_GROUPS = _load_table_groups()
TABLE_GROUPS_BY_KEY = {str(x["key"]): x for x in TABLE_GROUPS}

for name, value in {
    "VK_TOKEN": VK_TOKEN,
    "VK_GROUP_ID": str(VK_GROUP_ID),
    "CNC_BOT_SECRET": CNC_BOT_SECRET,
}.items():
    if not value:
        raise ValueError(f"Обязательная переменная окружения: {name}")


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
        self._table_cache: Dict[str, dict] = {}

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
                    text = r.text or str(r.status_code)
                    try:
                        detail = r.json().get("detail", text)
                    except Exception:
                        detail = text
                    if isinstance(detail, str) and detail.lstrip().startswith("<!"):
                        detail = (
                            f"сервер вернул HTML {r.status_code} (внутренняя ошибка Django). "
                            "Проверьте логи web/gunicorn и переменные CNC_BOT_API_SECRET, "
                            "CNC_BOT_TABLE_OWNER_USERNAME."
                        )
                    raise CNCApiError(f"Ошибка API ({r.status_code}): {detail}")
                return r.json()
            except CNCApiError:
                raise
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(2**attempt)
                    continue
                raise CNCApiError(str(last_error)) from last_error
        raise CNCApiError(str(last_error))

    def lookup_table(
        self,
        *,
        section_type: str = CNC_SECTION_TYPE,
        title_contains: str = CNC_TABLE_TITLE_FRAGMENT,
        cache_key: str = "default",
        force_refresh: bool = False,
    ) -> dict:
        if cache_key in self._table_cache and not force_refresh:
            return self._table_cache[cache_key]
        result = self.post(
            "lookup_table",
            {"section_type": section_type, "title_contains": title_contains},
        )
        self._table_cache[cache_key] = result
        return result

    def list_sheets(self, table_id: int) -> List[str]:
        return self.post("list_sheets", {"table_id": table_id}).get("sheet_names", [])

    def list_groups(self, table_id: int, sheet_name: str) -> List[str]:
        return self.post("list_groups", {"table_id": table_id, "sheet_name": sheet_name}).get(
            "groups", []
        )

    def list_students(self, table_id: int, sheet_name: str, group: Optional[str]) -> List[dict]:
        body: Dict[str, Any] = {"table_id": table_id, "sheet_name": sheet_name}
        if group:
            body["group"] = group
        return self.post("list_students", body).get("students", [])

    def get_student_profile(
        self,
        table_id: int,
        sheet_name: str,
        student_fio: str,
        group: Optional[str],
        remark_date: Optional[str] = None,
    ) -> dict:
        body: Dict[str, Any] = {
            "table_id": table_id,
            "sheet_name": sheet_name,
            "student_fio": student_fio,
        }
        if group:
            body["group"] = group
        if remark_date:
            body["remark_date"] = remark_date
        return self.post("get_student_profile", body).get("student", {})

    def set_student_remark(
        self,
        table_id: int,
        sheet_name: str,
        student_fio: str,
        remark_date: str,
        remark_text: Optional[str],
        group: Optional[str],
        evidence: Optional[bytes] = None,
        evidence_filename: str = "evidence.jpg",
        evidence_mime: str = "image/jpeg",
    ):
        body: Dict[str, Any] = {
            "table_id": str(table_id),
            "sheet_name": sheet_name,
            "student_fio": student_fio,
            "remark_date": remark_date,
            "action": "set_student_remark",
        }
        if remark_text is not None:
            body["remark_text"] = remark_text
        if group:
            body["group"] = group
        if evidence is None:
            return self.post("set_student_remark", {k: v for k, v in body.items() if k != "action"})

        headers = {"X-CNC-Bot-Token": CNC_BOT_SECRET}
        files = {
            "evidence": (evidence_filename, evidence, evidence_mime),
        }
        last_error = None
        for attempt in range(1, 4):
            try:
                r = requests.post(
                    f"{self.base}/bot/gateway/",
                    data=body,
                    files=files,
                    headers=headers,
                    timeout=60,
                )
                if r.status_code >= 400:
                    text = r.text or str(r.status_code)
                    try:
                        detail = r.json().get("detail", text)
                    except Exception:
                        detail = text
                    raise CNCApiError(f"Ошибка API ({r.status_code}): {detail}")
                return r.json()
            except CNCApiError:
                raise
            except Exception as e:
                last_error = e
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise CNCApiError(str(last_error)) from last_error
        raise CNCApiError(str(last_error))

    def set_student_status(
        self,
        table_id: int,
        sheet_name: str,
        student_fio: str,
        status_value: str,
        group: Optional[str],
    ):
        body: Dict[str, Any] = {
            "table_id": table_id,
            "sheet_name": sheet_name,
            "student_fio": student_fio,
            "status_value": status_value,
        }
        if group:
            body["group"] = group
        return self.post("set_student_status", body)

    def expel_student_to_trash(
        self,
        table_id: int,
        sheet_name: str,
        student_fio: str,
        group: Optional[str],
    ) -> dict:
        body: Dict[str, Any] = {
            "table_id": table_id,
            "sheet_name": sheet_name,
            "student_fio": student_fio,
        }
        if group:
            body["group"] = group
        return self.post("expel_student_to_trash", body)

    def list_trashed_students(self, table_id: int, sheet_name: str) -> List[dict]:
        return self.post(
            "list_trashed_students",
            {"table_id": table_id, "sheet_name": sheet_name},
        ).get("students", [])

    def restore_student_from_trash(self, trash_id: int) -> dict:
        return self.post("restore_student_from_trash", {"trash_id": trash_id})

    def export_table_xlsx(
        self, table_id: int, year: Optional[int] = None, month: Optional[int] = None
    ) -> tuple[bytes, str]:
        payload: Dict[str, Any] = {"action": "export_table_xlsx", "table_id": table_id}
        if year and month:
            payload["year"] = year
            payload["month"] = month
        r = requests.post(
            f"{self.base}/bot/gateway/",
            json=payload,
            headers=_headers(),
            timeout=90,
        )
        if r.status_code >= 400:
            text = r.text or str(r.status_code)
            try:
                detail = r.json().get("detail", text)
            except Exception:
                detail = text
            raise CNCApiError(f"Ошибка API ({r.status_code}): {detail}")
        cd = r.headers.get("Content-Disposition", "")
        filename = "table.xlsx"
        marker = 'filename="'
        if marker in cd:
            tail = cd.split(marker, 1)[1]
            filename = tail.split('"', 1)[0] or filename
        if not filename.lower().endswith(".xlsx"):
            filename = f"{filename}.xlsx"
        return r.content, filename

    def list_report_archives(self, table_id: int) -> List[dict]:
        return self.post("list_report_archives", {"table_id": table_id}).get("archives", [])

    def export_monitoring_report_docx(
        self,
        table_id: int,
        sheet_name: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> tuple[bytes, str]:
        payload: Dict[str, Any] = {
            "action": "export_monitoring_report_docx",
            "table_id": table_id,
            "sheet_name": sheet_name,
        }
        if year and month:
            payload["year"] = year
            payload["month"] = month
        r = requests.post(
            f"{self.base}/bot/gateway/",
            json=payload,
            headers=_headers(),
            timeout=120,
        )
        if r.status_code >= 400:
            text = r.text or str(r.status_code)
            try:
                detail = r.json().get("detail", text)
            except Exception:
                detail = text
            raise CNCApiError(f"Ошибка API ({r.status_code}): {detail}")
        cd = r.headers.get("Content-Disposition", "")
        filename = "monitoring_report.docx"
        marker = 'filename="'
        if marker in cd:
            tail = cd.split(marker, 1)[1]
            filename = tail.split('"', 1)[0] or filename
        if not filename.lower().endswith(".docx"):
            filename = f"{filename}.docx"
        return r.content, filename


@dataclass
class UserCtx:
    table_group_key: Optional[str] = None
    direction: Optional[str] = None
    group: Optional[str] = None
    student: Optional[str] = None
    selected_date: str = ""
    awaiting: Optional[str] = None  # "date_input" | "remark_input" | "remark_photo"
    remark_draft_text: Optional[str] = None
    current_view: str = "main"
    groups_page: int = 0
    students_page: int = 0
    directions_cache: List[str] = field(default_factory=list)
    groups_cache: List[str] = field(default_factory=list)
    students_cache: List[dict] = field(default_factory=list)
    trash_cache: List[dict] = field(default_factory=list)
    trash_page: int = 0
    report_archives_cache: List[dict] = field(default_factory=list)


def _pl(cmd: str, **kwargs) -> str:
    """Компактный payload для кнопки. Короткие ключи, чтобы влезать в лимит VK."""
    data = {"c": cmd}
    data.update(kwargs)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _parse_payload(raw: Optional[Any]) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


PER_PAGE = 5  # студенты / корзина; запас по лимиту VK (max 10 рядов default keyboard)
GROUPS_PER_PAGE = 4  # группы: место под пагинацию + компактный footer
BOT_LOCK_EXIT = 99  # второй экземпляр; wrapper ждёт и пробует снова
_LOCK_FH: Optional[TextIO] = None


def _bot_lock_path() -> str:
    override = os.getenv("BOT_LOCK_FILE", "").strip()
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cnc_vk_bot.lock")


def acquire_singleton_lock() -> None:
    """Один процесс bot.py на хост: иначе VK шлёт одно событие всем long-poll."""
    global _LOCK_FH
    path = _bot_lock_path()
    fh = open(path, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                fh.close()
                logger.error("Уже запущен другой экземпляр бота (lock=%s)", path)
                sys.exit(BOT_LOCK_EXIT)
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                fh.close()
                logger.error("Уже запущен другой экземпляр бота (lock=%s)", path)
                sys.exit(BOT_LOCK_EXIT)
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _LOCK_FH = fh

        def _release() -> None:
            global _LOCK_FH
            if _LOCK_FH is None:
                return
            try:
                if os.name == "nt":
                    import msvcrt

                    _LOCK_FH.seek(0)
                    msvcrt.locking(_LOCK_FH.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(_LOCK_FH.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                _LOCK_FH.close()
            except Exception:
                pass
            _LOCK_FH = None

        atexit.register(_release)
    except Exception:
        fh.close()
        raise


def _add_nav_row(kb: VkKeyboard, *, page: int, total_pages: int, page_cmd: str) -> None:
    if total_pages <= 1:
        return
    if page > 0:
        kb.add_button(
            "⬅️",
            VkKeyboardColor.SECONDARY,
            payload=_pl(page_cmd, p=page - 1),
        )
    if page < total_pages - 1:
        kb.add_button(
            "➡️",
            VkKeyboardColor.SECONDARY,
            payload=_pl(page_cmd, p=page + 1),
        )
    kb.add_line()


class StudentBot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.long_poll = VkBotLongPoll(self.vk_session, VK_GROUP_ID)
        self.api = CNCApi(CNC_API_BASE)
        self.table_info: Dict[str, dict] = {}
        self.ctx: Dict[int, UserCtx] = {}
        self._last_alive = time.monotonic()
        self._soft_reconnect = threading.Event()
        self._soft_attempted_at: Optional[float] = None
        self._watchdog_lock = threading.Lock()

    def _touch_alive(self) -> None:
        with self._watchdog_lock:
            self._last_alive = time.monotonic()
            self._soft_attempted_at = None

    def _reset_vk_longpoll(self) -> None:
        """Новая HTTP-сессия и long-poll (после обрыва или soft reconnect)."""
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.long_poll = VkBotLongPoll(self.vk_session, VK_GROUP_ID)

    def _interrupt_longpoll(self) -> None:
        """Пытаемся разблокировать зависший HTTP-запрос long-poll."""
        try:
            http = getattr(self.vk_session, "http", None)
            if http is not None:
                http.close()
        except Exception:
            logger.exception("Не удалось закрыть VK HTTP-сессию для soft reconnect")

    def _watchdog_loop(self) -> None:
        while True:
            time.sleep(15)
            now = time.monotonic()
            with self._watchdog_lock:
                idle = now - self._last_alive
                soft_at = self._soft_attempted_at
            if idle < BOT_WATCHDOG_IDLE_SEC:
                continue
            if soft_at is None:
                logger.error(
                    "Watchdog: long-poll молчит %.0f сек (порог %s) — soft reconnect",
                    idle,
                    BOT_WATCHDOG_IDLE_SEC,
                )
                with self._watchdog_lock:
                    self._soft_attempted_at = time.monotonic()
                self._soft_reconnect.set()
                self._interrupt_longpoll()
                continue
            if now - soft_at >= BOT_WATCHDOG_HARD_AFTER_SEC:
                logger.error(
                    "Watchdog: soft reconnect не помог за %s сек — hard exit для автоперезапуска",
                    BOT_WATCHDOG_HARD_AFTER_SEC,
                )
                os._exit(1)

    def _ctx(self, peer_id: int) -> UserCtx:
        if peer_id not in self.ctx:
            self.ctx[peer_id] = UserCtx(selected_date=_tz_now().strftime("%d.%m.%Y"))
        return self.ctx[peer_id]

    def ensure_table(self, group_key: str):
        if group_key not in TABLE_GROUPS_BY_KEY:
            raise CNCApiError(f"Неизвестная группа таблицы: {group_key}")
        if group_key not in self.table_info:
            cfg = TABLE_GROUPS_BY_KEY[group_key]
            self.table_info[group_key] = self.api.lookup_table(
                section_type=cfg["section_type"],
                title_contains=cfg["table_title"],
                cache_key=group_key,
            )
            logger.info(
                "Таблица key=%s id=%s, листов=%s",
                group_key,
                self.table_info[group_key].get("id"),
                len(self.table_info[group_key].get("sheet_names") or []),
            )

    def table_id(self, group_key: str) -> int:
        self.ensure_table(group_key)
        return int(self.table_info[group_key]["id"])

    def _all_sheets(self, group_key: str) -> List[str]:
        """Все листы таблицы — сперва из кеша lookup_table, иначе через list_sheets."""
        self.ensure_table(group_key)
        names = list(self.table_info[group_key].get("sheet_names") or [])
        if not names:
            try:
                names = self.api.list_sheets(self.table_id(group_key))
            except Exception:
                logger.exception("list_sheets failed")
                names = []
        return names

    def directions(self, group_key: str) -> List[str]:
        """Упорядоченный список направлений: сперва по порядку из env, затем все остальные листы."""
        names = self._all_sheets(group_key)
        if not names:
            return []
        configured = TABLE_GROUPS_BY_KEY.get(group_key, {}).get("directions") or SPREADSHEETS
        ordered: List[str] = []
        for pref in configured:
            pl = pref.lower()
            for n in names:
                nl = n.lower()
                if (pl == nl or pl in nl or nl in pl) and n not in ordered:
                    ordered.append(n)
                    break
        for n in names:
            if n not in ordered:
                ordered.append(n)
        return ordered

    def run(self):
        logger.info(
            "Запуск VK-бота мониторинга… (watchdog idle=%ss, hard_after=%ss)",
            BOT_WATCHDOG_IDLE_SEC,
            BOT_WATCHDOG_HARD_AFTER_SEC,
        )
        threading.Thread(target=self._watchdog_loop, name="lp-watchdog", daemon=True).start()
        reconnect_delay = 5
        while True:
            try:
                self._soft_reconnect.clear()
                while True:
                    if self._soft_reconnect.is_set():
                        raise RuntimeError("soft reconnect requested by watchdog")
                    events = self.long_poll.check()
                    self._touch_alive()
                    reconnect_delay = 5
                    for event in events:
                        try:
                            if event.type == VkBotEventType.MESSAGE_NEW:
                                self.handle(event.obj.message)
                        except Exception:
                            logger.exception("Ошибка обработки сообщения")
            except Exception:
                logger.exception(
                    "Longpoll оборвался, повторное подключение через %s сек.",
                    reconnect_delay,
                )
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)
                self._reset_vk_longpoll()

    # -------------------- маршрутизация сообщений --------------------

    def handle(self, msg: dict):
        peer_id = msg.get("peer_id")
        text = (msg.get("text") or "").strip()
        payload = _parse_payload(msg.get("payload"))
        logger.info("Сообщение peer=%s text=%s payload=%s", peer_id, text[:120], payload)
        ctx = self._ctx(peer_id)

        try:
            if payload:
                self.handle_payload(peer_id, ctx, payload)
                return
            if ctx.awaiting == "date_input":
                self.handle_date_input(peer_id, ctx, text)
                return
            if ctx.awaiting == "remark_input":
                self.handle_remark_input(peer_id, ctx, text)
                return
            if ctx.awaiting == "remark_photo":
                self.handle_remark_photo(peer_id, ctx, msg)
                return

            tl = text.lower()
            if tl in ("начать", "старт", "меню", "помощь", "help", "?", "/start"):
                self.show_main(peer_id, "Выберите раздел:")
                return

            # Текстовые алиасы для базовых кнопок (на случай если пользователь печатает сам)
            if "направлен" in tl:
                self.show_directions(peer_id, ctx)
                return
            if "групп" in tl:
                self.show_groups(peer_id, ctx)
                return
            if "студент" in tl:
                self.show_students(peer_id, ctx)
                return
            if "дата" in tl:
                self.show_date_picker(peer_id, ctx)
                return
            if "выгруз" in tl or "excel" in tl or "xlsx" in tl:
                self.export_table_to_vk(peer_id)
                return
            if "отчет" in tl or "отчёт" in tl or "word" in tl or "docx" in tl:
                self.export_report_to_vk(peer_id, ctx)
                return

            self.show_main(peer_id, "Не понял команду. Используйте кнопки ниже.")
        except CNCApiError as e:
            self.send(peer_id, f"❌ {e}")
        except Exception as e:
            logger.exception("handle")
            self.send(peer_id, f"❌ Ошибка: {e}")

    def handle_payload(self, peer_id: int, ctx: UserCtx, p: dict):
        if ctx.awaiting in ("remark_input", "remark_photo") or ctx.remark_draft_text:
            self._clear_remark_draft(ctx)
        cmd = p.get("c")
        try:
            if cmd == "main":
                self.show_main(peer_id, "Главное меню")
            elif cmd == "tbls":
                self.show_table_groups(peer_id, ctx)
            elif cmd == "tbl":
                key = str(p.get("k") or "").strip()
                if key in TABLE_GROUPS_BY_KEY:
                    ctx.table_group_key = key
                    ctx.direction = None
                    ctx.group = None
                    ctx.student = None
                    ctx.directions_cache = []
                    ctx.groups_cache = []
                    ctx.students_cache = []
                    ctx.groups_page = 0
                    ctx.students_page = 0
                    self.send(peer_id, f"Выбрана группа: {TABLE_GROUPS_BY_KEY[key]['title']}")
                    self.show_directions(peer_id, ctx)
                else:
                    self.show_table_groups(peer_id, ctx)
            elif cmd == "dirs":
                self.show_directions(peer_id, ctx)
            elif cmd == "dir":  # pick direction by index
                idx = int(p.get("i", -1))
                if 0 <= idx < len(ctx.directions_cache):
                    ctx.direction = ctx.directions_cache[idx]
                    ctx.group = None
                    ctx.student = None
                    ctx.groups_cache = []
                    ctx.students_cache = []
                    ctx.groups_page = 0
                    ctx.students_page = 0
                    self.send(peer_id, f"✅ Направление: {ctx.direction}")
                    self.show_groups(peer_id, ctx)
                else:
                    self.show_directions(peer_id, ctx)
            elif cmd == "grps":
                self.show_groups(peer_id, ctx)
            elif cmd == "grp":  # pick group by index
                idx = int(p.get("i", -1))
                if 0 <= idx < len(ctx.groups_cache):
                    ctx.group = ctx.groups_cache[idx]
                    ctx.student = None
                    ctx.students_cache = []
                    ctx.students_page = 0
                    self.send(peer_id, f"✅ Группа: {ctx.group}")
                    self.show_students(peer_id, ctx)
                else:
                    self.show_groups(peer_id, ctx)
            elif cmd == "sts":
                self.show_students(peer_id, ctx)
            elif cmd == "st":  # pick student by index
                idx = int(p.get("i", -1))
                if 0 <= idx < len(ctx.students_cache):
                    ctx.student = ctx.students_cache[idx].get("fio", "")
                    self.show_student_profile(peer_id, ctx)
                else:
                    self.show_students(peer_id, ctx)
            elif cmd == "gpage":
                ctx.groups_page = int(p.get("p", 0))
                self.show_groups(peer_id, ctx)
            elif cmd == "spage":
                ctx.students_page = int(p.get("p", 0))
                self.show_students(peer_id, ctx)
            elif cmd == "date":
                self.show_date_picker(peer_id, ctx)
            elif cmd == "exp_xlsx":
                self.export_table_to_vk(peer_id)
            elif cmd == "rep_cur":
                self.export_report_to_vk(peer_id, ctx)
            elif cmd == "rep_arc":
                self.show_report_archives(peer_id, ctx)
            elif cmd == "rep_m":
                idx = int(p.get("i", -1))
                if 0 <= idx < len(ctx.report_archives_cache):
                    archive = ctx.report_archives_cache[idx]
                    self.export_report_to_vk(
                        peer_id,
                        ctx,
                        year=int(archive.get("year")),
                        month=int(archive.get("month")),
                    )
                else:
                    self.show_report_archives(peer_id, ctx)
            elif cmd == "rep_x":
                idx = int(p.get("i", -1))
                if 0 <= idx < len(ctx.report_archives_cache):
                    archive = ctx.report_archives_cache[idx]
                    self.export_table_to_vk(
                        peer_id,
                        year=int(archive.get("year")),
                        month=int(archive.get("month")),
                    )
                else:
                    self.show_report_archives(peer_id, ctx)
            elif cmd == "d_today":
                ctx.selected_date = _tz_now().strftime("%d.%m.%Y")
                self.send(peer_id, f"📅 Дата: {ctx.selected_date}")
                self._return_after_date(peer_id, ctx)
            elif cmd == "d_m7":
                d = datetime.strptime(ctx.selected_date, "%d.%m.%Y") - timedelta(days=7)
                ctx.selected_date = d.strftime("%d.%m.%Y")
                self.send(peer_id, f"📅 Дата: {ctx.selected_date}")
                self._return_after_date(peer_id, ctx)
            elif cmd == "d_p7":
                d = datetime.strptime(ctx.selected_date, "%d.%m.%Y") + timedelta(days=7)
                ctx.selected_date = d.strftime("%d.%m.%Y")
                self.send(peer_id, f"📅 Дата: {ctx.selected_date}")
                self._return_after_date(peer_id, ctx)
            elif cmd == "d_manual":
                ctx.awaiting = "date_input"
                self.send(peer_id, "Введите дату в формате ДД.ММ.ГГГГ")
            elif cmd == "rem_no":
                self.write_remark(peer_id, ctx, None)
            elif cmd == "rem_txt":
                ctx.awaiting = "remark_input"
                ctx.remark_draft_text = None
                self.send(
                    peer_id,
                    "Введите текст замечания одним сообщением.\n"
                    "После текста бот попросит прислать скрин (фото или файл jpg/png/webp/bmp).",
                )
            elif cmd == "stu_ex":
                self.confirm_expel(peer_id, ctx)
            elif cmd == "ex_yes":
                self.expel_student(peer_id, ctx)
            elif cmd == "ex_no":
                self.send(peer_id, "Отчисление отменено.")
                self.show_student_actions(peer_id, ctx)
            elif cmd == "trash":
                self.show_trash(peer_id, ctx)
            elif cmd == "tpage":
                ctx.trash_page = int(p.get("p", 0))
                self.show_trash(peer_id, ctx, refresh=False)
            elif cmd == "ti":
                idx = int(p.get("i", -1))
                self.confirm_restore(peer_id, ctx, idx)
            elif cmd == "tr_yes":
                idx = int(p.get("i", -1))
                self.restore_student(peer_id, ctx, idx)
            elif cmd == "tr_no":
                self.send(peer_id, "Восстановление отменено.")
                self.show_trash(peer_id, ctx, refresh=False)
            elif cmd == "card":
                self.show_student_profile(peer_id, ctx)
            else:
                self.show_main(peer_id, "Неизвестная кнопка. Открываю меню.")
        except CNCApiError as e:
            self.send(peer_id, f"❌ {e}")
        except Exception as e:
            logger.exception("handle_payload")
            self.send(peer_id, f"❌ Ошибка: {e}")

    def _return_after_date(self, peer_id: int, ctx: UserCtx):
        if ctx.direction and ctx.group and ctx.student:
            self.show_student_profile(peer_id, ctx)
        else:
            self.show_main(peer_id, "Дата сохранена. Выберите раздел:")

    def _selected_group_cfg(self, ctx: UserCtx) -> Optional[dict]:
        if not ctx.table_group_key:
            return None
        return TABLE_GROUPS_BY_KEY.get(ctx.table_group_key)

    # -------------------- ввод от пользователя --------------------

    def handle_date_input(self, peer_id: int, ctx: UserCtx, text: str):
        ctx.awaiting = None
        try:
            datetime.strptime(text.strip(), "%d.%m.%Y")
        except Exception:
            self.send(peer_id, "❌ Неверная дата. Формат: ДД.ММ.ГГГГ")
            self.show_date_picker(peer_id, ctx)
            return
        ctx.selected_date = text.strip()
        self.send(peer_id, f"📅 Дата сохранена: {ctx.selected_date}")
        self._return_after_date(peer_id, ctx)

    def handle_remark_input(self, peer_id: int, ctx: UserCtx, text: str):
        if not text.strip():
            self._clear_remark_draft(ctx)
            self.send(peer_id, "❌ Пустой текст замечания.")
            self.show_student_actions(peer_id, ctx)
            return
        ctx.remark_draft_text = text.strip()
        ctx.awaiting = "remark_photo"
        self.send(
            peer_id,
            "Текст принят. Пришлите скрин доказательства одним сообщением "
            "(фото VK или файл jpg/png/webp/bmp).\n"
            "Пока скрин не прислан, замечание в таблицу не записывается.",
        )

    def handle_remark_photo(self, peer_id: int, ctx: UserCtx, msg: dict):
        draft = (ctx.remark_draft_text or "").strip()
        if not draft:
            self._clear_remark_draft(ctx)
            self.send(peer_id, "❌ Черновик замечания потерян. Начните заново.")
            self.show_student_actions(peer_id, ctx)
            return
        extracted = self._extract_evidence_from_message(msg)
        if not extracted:
            self.send(
                peer_id,
                "❌ Нужен скрин: фото или файл jpg/png/webp/bmp. Текст уже сохранён в черновике — пришлите картинку.",
            )
            return
        raw, filename, mime = extracted
        self.write_remark(
            peer_id,
            ctx,
            draft,
            evidence=raw,
            evidence_filename=filename,
            evidence_mime=mime,
        )

    def _clear_remark_draft(self, ctx: UserCtx) -> None:
        ctx.awaiting = None
        ctx.remark_draft_text = None

    def _extract_evidence_from_message(
        self, msg: dict
    ) -> Optional[tuple[bytes, str, str]]:
        attachments = msg.get("attachments") or []
        if not isinstance(attachments, list):
            return None
        for att in attachments:
            if not isinstance(att, dict):
                continue
            kind = (att.get("type") or "").strip().lower()
            if kind == "photo":
                photo = att.get("photo") or {}
                url = _largest_photo_url(photo)
                if not url:
                    continue
                raw = self._download_bytes(url)
                if raw:
                    return raw, "evidence.jpg", "image/jpeg"
            if kind == "doc":
                doc = att.get("doc") or {}
                ext = str(doc.get("ext") or "").lower().lstrip(".")
                title = str(doc.get("title") or f"evidence.{ext or 'jpg'}")
                url = str(doc.get("url") or "").strip()
                if ext not in {"jpg", "jpeg", "png", "webp", "bmp"} or not url:
                    continue
                raw = self._download_bytes(url)
                if not raw:
                    continue
                mime = {
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp",
                    "bmp": "image/bmp",
                }.get(ext, "image/jpeg")
                if not title.lower().endswith(f".{ext}"):
                    title = f"{title}.{ext}"
                return raw, title, mime
        return None

    def _download_bytes(self, url: str) -> Optional[bytes]:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception:
            logger.exception("Не удалось скачать вложение VK: %s", url)
            return None

    # -------------------- экраны --------------------

    def show_main(self, peer_id: int, text: str):
        ctx = self._ctx(peer_id)
        ctx.current_view = "main"
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("Алабуга Политех", VkKeyboardColor.PRIMARY, payload=_pl("tbls"))
        suffix = []
        if ctx.table_group_key and ctx.table_group_key in TABLE_GROUPS_BY_KEY:
            suffix.append(f"Группа таблицы: {TABLE_GROUPS_BY_KEY[ctx.table_group_key]['title']}")
        if ctx.direction:
            suffix.append(f"Направление: {ctx.direction}")
        if ctx.group:
            suffix.append(f"Группа: {ctx.group}")
        if ctx.student:
            suffix.append(f"Студент: {ctx.student}")
        suffix.append(f"Дата: {ctx.selected_date}")
        body = text + "\n\n" + " · ".join(suffix)
        self.send(peer_id, body, keyboard=kb)

    def show_table_groups(self, peer_id: int, ctx: UserCtx):
        ctx.current_view = "table_groups"
        kb = VkKeyboard(one_time=False, inline=False)
        for group in TABLE_GROUPS:
            kb.add_button(group["title"][:40], VkKeyboardColor.PRIMARY, payload=_pl("tbl", k=group["key"]))
            kb.add_line()
        kb.add_button("В меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(peer_id, "Выберите группу таблиц:", keyboard=kb)

    def show_directions(self, peer_id: int, ctx: UserCtx):
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        ctx.current_view = "directions"
        dirs = self.directions(ctx.table_group_key)
        ctx.directions_cache = dirs
        kb = VkKeyboard(one_time=False, inline=False)
        if not dirs:
            kb.add_button("В меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
            self.send(
                peer_id,
                "⚠️ Не удалось получить список направлений. Проверьте, что таблица импортирована.",
                keyboard=kb,
            )
            return
        # до 6 направлений + 2 ряда footer ≤ 8 (лимит VK default keyboard = 10)
        for i, name in enumerate(dirs[:6]):
            kb.add_button(name[:40], VkKeyboardColor.PRIMARY, payload=_pl("dir", i=i))
            kb.add_line()
        if len(dirs) > 6:
            logger.warning(
                "Направлений %s > 6 для key=%s — показаны первые 6",
                len(dirs),
                ctx.table_group_key,
            )
        kb.add_button("Сменить группу таблиц", VkKeyboardColor.SECONDARY, payload=_pl("tbls"))
        kb.add_line()
        kb.add_button("В меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(peer_id, "Выберите направление:", keyboard=kb)

    def show_groups(self, peer_id: int, ctx: UserCtx):
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        if not ctx.groups_cache:
            ctx.groups_cache = self.api.list_groups(self.table_id(ctx.table_group_key), ctx.direction)
            ctx.groups_page = 0
        groups = ctx.groups_cache
        if not groups:
            kb = VkKeyboard(one_time=False, inline=False)
            kb.add_button("🎓 Направления", VkKeyboardColor.PRIMARY, payload=_pl("dirs"))
            kb.add_line()
            kb.add_button("🗑 Корзина", VkKeyboardColor.SECONDARY, payload=_pl("trash"))
            kb.add_line()
            kb.add_button("📄 Отчет Word", VkKeyboardColor.POSITIVE, payload=_pl("rep_cur"))
            kb.add_line()
            kb.add_button("📤 Экспорт Excel", VkKeyboardColor.POSITIVE, payload=_pl("exp_xlsx"))
            kb.add_line()
            kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
            self.send(peer_id, f"В направлении «{ctx.direction}» группы не найдены.", keyboard=kb)
            return
        ctx.current_view = "groups"
        total_pages = max(1, (len(groups) + GROUPS_PER_PAGE - 1) // GROUPS_PER_PAGE)
        page = max(0, min(ctx.groups_page, total_pages - 1))
        ctx.groups_page = page
        start = page * GROUPS_PER_PAGE
        shown = groups[start : start + GROUPS_PER_PAGE]

        # Макс рядов: 4 группы + 1 nav + 3 footer = 8 (лимит VK default = 10)
        kb = VkKeyboard(one_time=False, inline=False)
        for i, g in enumerate(shown):
            kb.add_button(g[:40], VkKeyboardColor.PRIMARY, payload=_pl("grp", i=start + i))
            kb.add_line()
        _add_nav_row(kb, page=page, total_pages=total_pages, page_cmd="gpage")
        kb.add_button("Направления", VkKeyboardColor.SECONDARY, payload=_pl("dirs"))
        kb.add_button("Корзина", VkKeyboardColor.SECONDARY, payload=_pl("trash"))
        kb.add_line()
        kb.add_button("Отчет Word", VkKeyboardColor.POSITIVE, payload=_pl("rep_cur"))
        kb.add_button("Архив", VkKeyboardColor.SECONDARY, payload=_pl("rep_arc"))
        kb.add_line()
        kb.add_button("Excel", VkKeyboardColor.POSITIVE, payload=_pl("exp_xlsx"))
        kb.add_button("Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(
            peer_id,
            f"Направление: {ctx.direction}\nВыберите группу ({page + 1}/{total_pages}):",
            keyboard=kb,
        )

    def show_students(self, peer_id: int, ctx: UserCtx):
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        if not ctx.group:
            self.show_groups(peer_id, ctx)
            return
        if not ctx.students_cache:
            ctx.students_cache = self.api.list_students(
                self.table_id(ctx.table_group_key), ctx.direction, ctx.group
            )
            ctx.students_page = 0
        students = ctx.students_cache
        if not students:
            kb = VkKeyboard(one_time=False, inline=False)
            kb.add_button("📋 Группы", VkKeyboardColor.PRIMARY, payload=_pl("grps"))
            kb.add_line()
            kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
            self.send(peer_id, f"В группе «{ctx.group}» студенты не найдены.", keyboard=kb)
            return
        ctx.current_view = "students"
        total_pages = max(1, (len(students) + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(ctx.students_page, total_pages - 1))
        ctx.students_page = page
        start = page * PER_PAGE
        shown = students[start : start + PER_PAGE]

        kb = VkKeyboard(one_time=False, inline=False)
        for i, stu in enumerate(shown):
            fio = (stu.get("fio") or "").strip() or "—"
            kb.add_button(fio[:40], VkKeyboardColor.PRIMARY, payload=_pl("st", i=start + i))
            kb.add_line()
        if total_pages > 1:
            if page > 0:
                kb.add_button(
                    "⬅️ Назад",
                    VkKeyboardColor.SECONDARY,
                    payload=_pl("spage", p=page - 1),
                )
            if page < total_pages - 1:
                kb.add_button(
                    "➡️ Вперед",
                    VkKeyboardColor.SECONDARY,
                    payload=_pl("spage", p=page + 1),
                )
            kb.add_line()
        kb.add_button("📋 Группы", VkKeyboardColor.SECONDARY, payload=_pl("grps"))
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(
            peer_id,
            f"Группа: {ctx.group}\nВыберите студента ({page + 1}/{total_pages}):",
            keyboard=kb,
        )

    def show_student_profile(self, peer_id: int, ctx: UserCtx):
        if not (ctx.table_group_key and ctx.direction and ctx.group and ctx.student):
            self.show_main(peer_id, "Сначала выберите направление, группу и студента.")
            return
        try:
            profile = self.api.get_student_profile(
                self.table_id(ctx.table_group_key),
                ctx.direction,
                ctx.student,
                ctx.group,
                ctx.selected_date,
            )
        except CNCApiError as e:
            self.send(peer_id, f"❌ Не удалось получить данные студента: {e}")
            self.show_students(peer_id, ctx)
            return

        status_value = (profile.get("status") or "").strip() or "—"
        remark_value = (profile.get("remark_value") or "").strip()
        social_profiles = profile.get("social_profiles") or []
        links = profile.get("social_links") or []
        lines = [
            f"👤 {profile.get('fio', ctx.student)}",
            f"📚 Направление: {ctx.direction}",
            f"🏷 Группа: {profile.get('group', ctx.group)}",
            f"🎓 Статус учебы: {status_value}",
            f"📅 Дата замечаний: {ctx.selected_date}",
        ]
        if social_profiles:
            lines.append("")
            lines.append("🔗 Соцсети:")
            for item in social_profiles[:10]:
                label = (item.get("label") or "Ссылка").strip()
                url = (item.get("url") or "").strip()
                if url:
                    lines.append(f"• {label}: {url}")
        elif links:
            # Fallback для совместимости со старым ответом API.
            lines.append("")
            lines.append("🔗 Соцсети:")
            for link in links[:10]:
                lines.append(f"• {link}")
        else:
            lines.append("🔗 Соцсети: не указаны")
        if remark_value:
            lines.append("")
            lines.append("📝 Текущие замечания в ячейке:")
            lines.append(remark_value[:600])
        self.send(peer_id, "\n".join(lines))
        self.show_student_actions(peer_id, ctx)

    def show_student_actions(self, peer_id: int, ctx: UserCtx):
        ctx.current_view = "student_actions"
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("✅ Замечаний нет", VkKeyboardColor.POSITIVE, payload=_pl("rem_no"))
        kb.add_line()
        kb.add_button("✍️ Замечание", VkKeyboardColor.NEGATIVE, payload=_pl("rem_txt"))
        kb.add_line()
        kb.add_button("🚫 Отчислен", VkKeyboardColor.SECONDARY, payload=_pl("stu_ex"))
        kb.add_line()
        kb.add_button("📅 Выбор даты", VkKeyboardColor.SECONDARY, payload=_pl("date"))
        kb.add_line()
        kb.add_button("👥 К студентам", VkKeyboardColor.SECONDARY, payload=_pl("sts"))
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(
            peer_id,
            f"Действия по студенту «{ctx.student}» на {ctx.selected_date}:",
            keyboard=kb,
        )

    def show_date_picker(self, peer_id: int, ctx: UserCtx):
        ctx.current_view = "date"
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("🗓 Сегодня", VkKeyboardColor.PRIMARY, payload=_pl("d_today"))
        kb.add_line()
        kb.add_button("⬅️ -7 дней", VkKeyboardColor.SECONDARY, payload=_pl("d_m7"))
        kb.add_button("➡️ +7 дней", VkKeyboardColor.SECONDARY, payload=_pl("d_p7"))
        kb.add_line()
        kb.add_button("⌨️ Ввести дату", VkKeyboardColor.SECONDARY, payload=_pl("d_manual"))
        kb.add_line()
        if ctx.student:
            kb.add_button(
                "👤 К карточке", VkKeyboardColor.SECONDARY, payload=_pl("card")
            )
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(peer_id, f"Текущая дата: {ctx.selected_date}", keyboard=kb)

    # -------------------- действия --------------------

    def _student_list_snapshot(self, ctx: UserCtx) -> List[dict]:
        """Текущий порядок студентов (из кеша или свежий запрос)."""
        if ctx.students_cache:
            return list(ctx.students_cache)
        if not (ctx.table_group_key and ctx.direction and ctx.group):
            return []
        try:
            return self.api.list_students(
                self.table_id(ctx.table_group_key), ctx.direction, ctx.group
            )
        except Exception:
            logger.exception("Не удалось получить список студентов для автоперехода")
            return []

    def _go_next_student_or_list(self, peer_id: int, ctx: UserCtx) -> None:
        """После замечания / «замечаний нет» — следующий студент или список группы."""
        students = self._student_list_snapshot(ctx)
        current = (ctx.student or "").strip()
        idx = next(
            (i for i, s in enumerate(students) if (s.get("fio") or "").strip() == current),
            -1,
        )
        ctx.students_cache = []  # в данных строки могло поменяться

        if idx >= 0 and idx + 1 < len(students):
            next_fio = (students[idx + 1].get("fio") or "").strip()
            if next_fio:
                ctx.student = next_fio
                ctx.students_page = (idx + 1) // PER_PAGE
                self.show_student_profile(peer_id, ctx)
                return

        ctx.student = None
        self.send(peer_id, "✅ Группа пройдена. Выберите студента или другую группу.")
        self.show_students(peer_id, ctx)

    def write_remark(
        self,
        peer_id: int,
        ctx: UserCtx,
        text: Optional[str],
        *,
        evidence: Optional[bytes] = None,
        evidence_filename: str = "evidence.jpg",
        evidence_mime: str = "image/jpeg",
    ):
        if not (ctx.table_group_key and ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        if text and evidence is None:
            self.send(peer_id, "❌ Для замечания нужен скрин. Начните заново.")
            self._clear_remark_draft(ctx)
            self.show_student_actions(peer_id, ctx)
            return
        self.api.set_student_remark(
            self.table_id(ctx.table_group_key),
            ctx.direction,
            ctx.student,
            ctx.selected_date,
            text,
            ctx.group,
            evidence=evidence,
            evidence_filename=evidence_filename,
            evidence_mime=evidence_mime,
        )
        self._clear_remark_draft(ctx)
        if text:
            self.send(peer_id, f"✅ Замечание и скрин записаны на {ctx.selected_date}.")
        else:
            self.send(peer_id, f"✅ Записано «замечаний нет» на {ctx.selected_date}.")
        self._go_next_student_or_list(peer_id, ctx)

    def confirm_expel(self, peer_id: int, ctx: UserCtx):
        if not (ctx.table_group_key and ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("✅ Да, в корзину", VkKeyboardColor.NEGATIVE, payload=_pl("ex_yes"))
        kb.add_line()
        kb.add_button("❌ Нет", VkKeyboardColor.SECONDARY, payload=_pl("ex_no"))
        self.send(
            peer_id,
            (
                "Удалить студента в корзину на 30 дней?\n\n"
                f"👤 {ctx.student}\n"
                f"🏷 Группа: {ctx.group or '—'}\n"
                f"📚 Направление: {ctx.direction}\n\n"
                "Строка целиком (ФИО, соцсети, замечания) уйдёт из основной таблицы. "
                "Скрины замечаний сохранятся до восстановления или истечения срока."
            ),
            keyboard=kb,
        )

    def expel_student(self, peer_id: int, ctx: UserCtx):
        if not (ctx.table_group_key and ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        students = self._student_list_snapshot(ctx)
        current = (ctx.student or "").strip()
        idx = next(
            (i for i, s in enumerate(students) if (s.get("fio") or "").strip() == current),
            -1,
        )
        try:
            result = self.api.expel_student_to_trash(
                self.table_id(ctx.table_group_key),
                ctx.direction,
                ctx.student,
                ctx.group,
            )
        except CNCApiError as e:
            self.send(peer_id, f"❌ Не удалось отчислить: {e}")
            self.show_student_actions(peer_id, ctx)
            return
        self.send(
            peer_id,
            f"✅ «{result.get('student_fio') or ctx.student}» перемещён в корзину на 30 дней.",
        )
        ctx.students_cache = []
        ctx.trash_cache = []
        if idx >= 0 and idx + 1 < len(students):
            next_fio = (students[idx + 1].get("fio") or "").strip()
            if next_fio:
                ctx.student = next_fio
                ctx.students_page = (idx + 1) // PER_PAGE
                self.show_student_profile(peer_id, ctx)
                return
        ctx.student = None
        self.send(peer_id, "✅ Группа пройдена. Выберите студента или другую группу.")
        self.show_students(peer_id, ctx)

    def show_trash(self, peer_id: int, ctx: UserCtx, *, refresh: bool = True):
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        if refresh or not ctx.trash_cache:
            try:
                ctx.trash_cache = self.api.list_trashed_students(
                    self.table_id(ctx.table_group_key), ctx.direction
                )
                ctx.trash_page = 0
            except CNCApiError as e:
                self.send(peer_id, f"❌ Не удалось открыть корзину: {e}")
                self.show_groups(peer_id, ctx)
                return
        items = ctx.trash_cache
        kb = VkKeyboard(one_time=False, inline=False)
        if not items:
            kb.add_button("📋 К группам", VkKeyboardColor.PRIMARY, payload=_pl("grps"))
            kb.add_line()
            kb.add_button("🎓 Направления", VkKeyboardColor.SECONDARY, payload=_pl("dirs"))
            kb.add_line()
            kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
            self.send(
                peer_id,
                f"🗑 Корзина направления «{ctx.direction}» пуста.",
                keyboard=kb,
            )
            return
        ctx.current_view = "trash"
        total_pages = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(ctx.trash_page, total_pages - 1))
        ctx.trash_page = page
        start = page * PER_PAGE
        shown = items[start : start + PER_PAGE]
        for i, item in enumerate(shown):
            fio = (item.get("fio") or "").strip() or "—"
            kb.add_button(fio[:40], VkKeyboardColor.PRIMARY, payload=_pl("ti", i=start + i))
            kb.add_line()
        if total_pages > 1:
            if page > 0:
                kb.add_button(
                    "⬅️ Назад",
                    VkKeyboardColor.SECONDARY,
                    payload=_pl("tpage", p=page - 1),
                )
            if page < total_pages - 1:
                kb.add_button(
                    "➡️ Вперед",
                    VkKeyboardColor.SECONDARY,
                    payload=_pl("tpage", p=page + 1),
                )
            kb.add_line()
        kb.add_button("📋 К группам", VkKeyboardColor.PRIMARY, payload=_pl("grps"))
        kb.add_line()
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(
            peer_id,
            f"🗑 Корзина «{ctx.direction}» ({page + 1}/{total_pages}). Выберите студента:",
            keyboard=kb,
        )

    def confirm_restore(self, peer_id: int, ctx: UserCtx, idx: int):
        if not (0 <= idx < len(ctx.trash_cache)):
            self.show_trash(peer_id, ctx)
            return
        item = ctx.trash_cache[idx]
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("✅ Да", VkKeyboardColor.POSITIVE, payload=_pl("tr_yes", i=idx))
        kb.add_line()
        kb.add_button("❌ Нет", VkKeyboardColor.SECONDARY, payload=_pl("tr_no"))
        self.send(
            peer_id,
            (
                "Вы точно хотите восстановить данного студента?\n\n"
                f"👤 {item.get('fio') or '—'}\n"
                f"🏷 Группа: {item.get('group') or '—'}\n"
                f"📚 Направление: {ctx.direction}"
            ),
            keyboard=kb,
        )

    def restore_student(self, peer_id: int, ctx: UserCtx, idx: int):
        if not (0 <= idx < len(ctx.trash_cache)):
            self.show_trash(peer_id, ctx)
            return
        item = ctx.trash_cache[idx]
        trash_id = item.get("id")
        if not trash_id:
            self.send(peer_id, "❌ Нет id записи корзины.")
            self.show_trash(peer_id, ctx)
            return
        try:
            result = self.api.restore_student_from_trash(int(trash_id))
        except CNCApiError as e:
            self.send(peer_id, f"❌ Не удалось восстановить: {e}")
            self.show_trash(peer_id, ctx)
            return
        fio = result.get("student_fio") or item.get("fio") or "студент"
        group = result.get("group") or item.get("group") or "—"
        self.send(
            peer_id,
            f"✅ «{fio}» восстановлен в группу «{group}» по алфавиту фамилии.",
        )
        ctx.trash_cache = []
        ctx.students_cache = []
        self.show_trash(peer_id, ctx)

    def set_status(self, peer_id: int, ctx: UserCtx, status_value: str):
        if not (ctx.table_group_key and ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        self.api.set_student_status(
            self.table_id(ctx.table_group_key), ctx.direction, ctx.student, status_value, ctx.group
        )
        self.send(peer_id, f"✅ Статус обновлён: {status_value}")
        ctx.students_cache = []
        self.show_student_profile(peer_id, ctx)

    def show_report_archives(self, peer_id: int, ctx: UserCtx):
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        archives = self.api.list_report_archives(self.table_id(ctx.table_group_key))
        ctx.report_archives_cache = archives
        kb = VkKeyboard(one_time=False, inline=False)
        if archives:
            for i, archive in enumerate(archives[:3]):
                label = str(archive.get("label") or f"{archive.get('month'):02d}.{archive.get('year')}")
                kb.add_button(
                    f"📄 Word {label}"[:40],
                    VkKeyboardColor.PRIMARY,
                    payload=_pl("rep_m", i=i),
                )
                kb.add_line()
                kb.add_button(
                    f"📤 Excel {label}"[:40],
                    VkKeyboardColor.POSITIVE,
                    payload=_pl("rep_x", i=i),
                )
                kb.add_line()
        kb.add_button("📄 Текущий отчет", VkKeyboardColor.POSITIVE, payload=_pl("rep_cur"))
        kb.add_button("📤 Текущий Excel", VkKeyboardColor.POSITIVE, payload=_pl("exp_xlsx"))
        kb.add_line()
        kb.add_button("📋 Группы", VkKeyboardColor.SECONDARY, payload=_pl("grps"))
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        text = (
            f"Архивы отчетов для направления «{ctx.direction}»:"
            if archives
            else "Архивов за прошлые месяцы пока нет."
        )
        self.send(peer_id, text, keyboard=kb)

    def export_report_to_vk(
        self,
        peer_id: int,
        ctx: UserCtx,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ):
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        period = f" за {month:02d}.{year}" if year and month else ""
        self.send(peer_id, f"⏳ Готовлю Word-отчет{period} по направлению «{ctx.direction}»...")
        blob, filename = self.api.export_monitoring_report_docx(
            self.table_id(ctx.table_group_key), ctx.direction, year=year, month=month
        )
        self.send_document(
            peer_id,
            filename,
            blob,
            f"✅ Word-отчет{period}:",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def export_table_to_vk(
        self, peer_id: int, year: Optional[int] = None, month: Optional[int] = None
    ):
        ctx = self._ctx(peer_id)
        if not ctx.table_group_key:
            self.show_table_groups(peer_id, ctx)
            return
        period = f" за {month:02d}.{year}" if year and month else ""
        self.send(peer_id, f"⏳ Готовлю таблицу к выгрузке{period}...")
        table_id = self.table_id(ctx.table_group_key)
        blob, filename = self.api.export_table_xlsx(table_id, year=year, month=month)
        self.send_document(
            peer_id,
            filename,
            blob,
            f"✅ Таблица{period}:",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # -------------------- отправка --------------------

    def send(self, peer_id: int, text: str, keyboard: Optional[VkKeyboard] = None):
        payload: Dict[str, Any] = {
            "peer_id": peer_id,
            "message": text[:3900],
            "random_id": random.randint(0, 2**31),
        }
        if keyboard is not None:
            payload["keyboard"] = keyboard.get_keyboard()
        self.vk_session.method("messages.send", payload)

    def send_document(
        self,
        peer_id: int,
        filename: str,
        body: bytes,
        caption: Optional[str] = None,
        mime_type: str = "application/octet-stream",
    ):
        vk = self.vk_session.get_api()
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                upload = vk.docs.getMessagesUploadServer(type="doc", peer_id=peer_id)
                upload_url = upload.get("upload_url")
                if not upload_url:
                    raise RuntimeError("VK не вернул upload_url для документа")
                files = {
                    "file": (
                        filename,
                        body,
                        mime_type,
                    )
                }
                up_resp = requests.post(upload_url, files=files, timeout=120)
                if up_resp.status_code in {405, 500, 502, 503, 504}:
                    raise requests.HTTPError(
                        f"{up_resp.status_code} Client Error for url: {upload_url}",
                        response=up_resp,
                    )
                up_resp.raise_for_status()
                payload = up_resp.json()
                file_token = payload.get("file")
                if not file_token:
                    raise RuntimeError(f"VK upload error: {payload}")
                saved = vk.docs.save(file=file_token, title=filename)
                item = None
                if isinstance(saved, dict):
                    docs = saved.get("doc") or saved.get("docs")
                    if isinstance(docs, list) and docs:
                        item = docs[0]
                    elif isinstance(docs, dict):
                        item = docs
                if not item and isinstance(saved, list) and saved:
                    item = saved[0]
                if not item:
                    raise RuntimeError(f"VK save error: {saved}")
                owner_id = item.get("owner_id")
                doc_id = item.get("id")
                if owner_id is None or doc_id is None:
                    raise RuntimeError(f"VK save returned malformed doc: {item}")
                msg_payload: Dict[str, Any] = {
                    "peer_id": peer_id,
                    "random_id": random.randint(0, 2**31),
                    "attachment": f"doc{owner_id}_{doc_id}",
                }
                if caption:
                    msg_payload["message"] = caption[:3900]
                self.vk_session.method("messages.send", msg_payload)
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "VK document upload attempt %s/3 failed: %s", attempt, exc
                )
                if attempt < 3:
                    time.sleep(0.4 * attempt)
                    continue
                raise
        if last_error:
            raise last_error


def _largest_photo_url(photo: dict) -> Optional[str]:
    sizes = photo.get("sizes") if isinstance(photo, dict) else None
    if isinstance(sizes, list) and sizes:
        best = None
        best_area = -1
        for item in sizes:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            area = int(item.get("width") or 0) * int(item.get("height") or 0)
            if area >= best_area:
                best_area = area
                best = url
        if best:
            return best
    for key in ("photo_2560", "photo_1280", "photo_807", "photo_604", "photo_130", "photo_75"):
        url = str(photo.get(key) or "").strip()
        if url:
            return url
    return None


if __name__ == "__main__":
    acquire_singleton_lock()
    StudentBot().run()
