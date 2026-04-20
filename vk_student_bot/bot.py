"""VK-бот мониторинга студентов с кнопочным UX."""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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
CNC_API_BASE = os.getenv("CNC_API_BASE", "http://web:8000/api").rstrip("/")
CNC_BOT_SECRET = os.getenv("CNC_BOT_SECRET", os.getenv("CNC_BOT_API_SECRET", "")).strip()
CNC_SECTION_TYPE = os.getenv("CNC_SECTION_TYPE", "rangers").strip()
CNC_TABLE_TITLE_FRAGMENT = os.getenv("CNC_TABLE_TITLE_FRAGMENT", "киберрейнджеры").strip()
DIRS_RAW = os.getenv("CNC_DIRECTION_SHEETS", "ЧПУ,РОБО,Аэро,микро")
SPREADSHEETS = [x.strip() for x in DIRS_RAW.split(",") if x.strip()]
TZ_NAME = os.getenv("TIMEZONE", "Europe/Moscow")

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
                if attempt < retries:
                    time.sleep(2**attempt)
                    continue
                raise CNCApiError(str(last_error)) from last_error
        raise CNCApiError(str(last_error))

    def lookup_table(self, force_refresh: bool = False) -> dict:
        if self._table_cache and not force_refresh:
            return self._table_cache
        result = self.post(
            "lookup_table",
            {"section_type": CNC_SECTION_TYPE, "title_contains": CNC_TABLE_TITLE_FRAGMENT},
        )
        self._table_cache = result
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
    ):
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


@dataclass
class UserCtx:
    direction: Optional[str] = None
    group: Optional[str] = None
    student: Optional[str] = None
    selected_date: str = ""
    awaiting: Optional[str] = None  # "date_input" | "remark_input"
    current_view: str = "main"
    groups_page: int = 0
    students_page: int = 0
    directions_cache: List[str] = field(default_factory=list)
    groups_cache: List[str] = field(default_factory=list)
    students_cache: List[dict] = field(default_factory=list)


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


PER_PAGE = 6  # максимум кнопок-элементов на странице (влезает в VK: 10 рядов)


class StudentBot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.long_poll = VkBotLongPoll(self.vk_session, VK_GROUP_ID)
        self.api = CNCApi(CNC_API_BASE)
        self.table_info: Optional[dict] = None
        self.ctx: Dict[int, UserCtx] = {}

    def _ctx(self, peer_id: int) -> UserCtx:
        if peer_id not in self.ctx:
            self.ctx[peer_id] = UserCtx(selected_date=_tz_now().strftime("%d.%m.%Y"))
        return self.ctx[peer_id]

    def ensure_table(self):
        if self.table_info is None:
            self.table_info = self.api.lookup_table()
            logger.info(
                "Таблица id=%s, листов=%s",
                self.table_info.get("id"),
                len(self.table_info.get("sheet_names") or []),
            )

    def table_id(self) -> int:
        self.ensure_table()
        return int(self.table_info["id"])

    def _all_sheets(self) -> List[str]:
        """Все листы таблицы — сперва из кеша lookup_table, иначе через list_sheets."""
        self.ensure_table()
        names = list(self.table_info.get("sheet_names") or [])
        if not names:
            try:
                names = self.api.list_sheets(self.table_id())
            except Exception:
                logger.exception("list_sheets failed")
                names = []
        return names

    def directions(self) -> List[str]:
        """Упорядоченный список направлений: сперва по порядку из env, затем все остальные листы."""
        names = self._all_sheets()
        if not names:
            return []
        ordered: List[str] = []
        for pref in SPREADSHEETS:
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
        logger.info("Запуск VK-бота мониторинга…")
        self.ensure_table()
        for event in self.long_poll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self.handle(event.obj.message)
            except Exception:
                logger.exception("Ошибка обработки сообщения")

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

            self.show_main(peer_id, "Не понял команду. Используйте кнопки ниже.")
        except CNCApiError as e:
            self.send(peer_id, f"❌ {e}")
        except Exception as e:
            logger.exception("handle")
            self.send(peer_id, f"❌ Ошибка: {e}")

    def handle_payload(self, peer_id: int, ctx: UserCtx, p: dict):
        cmd = p.get("c")
        try:
            if cmd == "main":
                self.show_main(peer_id, "Главное меню")
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
                self.send(peer_id, "Введите текст замечания одним сообщением.")
            elif cmd == "stu_st":
                self.set_status(peer_id, ctx, "учится")
            elif cmd == "stu_ex":
                self.set_status(peer_id, ctx, "отчислен")
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
        ctx.awaiting = None
        if not text.strip():
            self.send(peer_id, "❌ Пустой текст замечания.")
            self.show_student_actions(peer_id, ctx)
            return
        self.write_remark(peer_id, ctx, text.strip())

    # -------------------- экраны --------------------

    def show_main(self, peer_id: int, text: str):
        ctx = self._ctx(peer_id)
        ctx.current_view = "main"
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("🎓 Направления", VkKeyboardColor.PRIMARY, payload=_pl("dirs"))
        kb.add_line()
        kb.add_button("📋 Группы", VkKeyboardColor.SECONDARY, payload=_pl("grps"))
        kb.add_button("👤 Студент", VkKeyboardColor.SECONDARY, payload=_pl("sts"))
        kb.add_line()
        kb.add_button("📅 Выбор даты", VkKeyboardColor.SECONDARY, payload=_pl("date"))
        suffix = []
        if ctx.direction:
            suffix.append(f"🎓 {ctx.direction}")
        if ctx.group:
            suffix.append(f"🏷 {ctx.group}")
        if ctx.student:
            suffix.append(f"👤 {ctx.student}")
        suffix.append(f"📅 {ctx.selected_date}")
        body = text + "\n\n" + " · ".join(suffix)
        self.send(peer_id, body, keyboard=kb)

    def show_directions(self, peer_id: int, ctx: UserCtx):
        ctx.current_view = "directions"
        dirs = self.directions()
        ctx.directions_cache = dirs
        kb = VkKeyboard(one_time=False, inline=False)
        if not dirs:
            kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
            self.send(
                peer_id,
                "⚠️ Не удалось получить список направлений. Проверьте, что таблица импортирована.",
                keyboard=kb,
            )
            return
        # по 1 кнопке в ряд — всегда помещается и выглядит аккуратно
        for i, name in enumerate(dirs[:8]):
            kb.add_button(name[:40], VkKeyboardColor.PRIMARY, payload=_pl("dir", i=i))
            kb.add_line()
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(peer_id, "Выберите направление:", keyboard=kb)

    def show_groups(self, peer_id: int, ctx: UserCtx):
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        if not ctx.groups_cache:
            ctx.groups_cache = self.api.list_groups(self.table_id(), ctx.direction)
            ctx.groups_page = 0
        groups = ctx.groups_cache
        if not groups:
            kb = VkKeyboard(one_time=False, inline=False)
            kb.add_button("🎓 Направления", VkKeyboardColor.PRIMARY, payload=_pl("dirs"))
            kb.add_line()
            kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
            self.send(peer_id, f"В направлении «{ctx.direction}» группы не найдены.", keyboard=kb)
            return
        ctx.current_view = "groups"
        total_pages = max(1, (len(groups) + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(ctx.groups_page, total_pages - 1))
        ctx.groups_page = page
        start = page * PER_PAGE
        shown = groups[start : start + PER_PAGE]

        kb = VkKeyboard(one_time=False, inline=False)
        for i, g in enumerate(shown):
            kb.add_button(g[:40], VkKeyboardColor.PRIMARY, payload=_pl("grp", i=start + i))
            kb.add_line()
        if total_pages > 1:
            if page > 0:
                kb.add_button(
                    "⬅️ Назад",
                    VkKeyboardColor.SECONDARY,
                    payload=_pl("gpage", p=page - 1),
                )
            if page < total_pages - 1:
                kb.add_button(
                    "➡️ Вперед",
                    VkKeyboardColor.SECONDARY,
                    payload=_pl("gpage", p=page + 1),
                )
            kb.add_line()
        kb.add_button("🎓 Направления", VkKeyboardColor.SECONDARY, payload=_pl("dirs"))
        kb.add_button("🔙 Меню", VkKeyboardColor.SECONDARY, payload=_pl("main"))
        self.send(
            peer_id,
            f"Направление: {ctx.direction}\nВыберите группу ({page + 1}/{total_pages}):",
            keyboard=kb,
        )

    def show_students(self, peer_id: int, ctx: UserCtx):
        if not ctx.direction:
            self.show_directions(peer_id, ctx)
            return
        if not ctx.group:
            self.show_groups(peer_id, ctx)
            return
        if not ctx.students_cache:
            ctx.students_cache = self.api.list_students(
                self.table_id(), ctx.direction, ctx.group
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
        if not (ctx.direction and ctx.group and ctx.student):
            self.show_main(peer_id, "Сначала выберите направление, группу и студента.")
            return
        try:
            profile = self.api.get_student_profile(
                self.table_id(),
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
        links = profile.get("social_links") or []
        lines = [
            f"👤 {profile.get('fio', ctx.student)}",
            f"📚 Направление: {ctx.direction}",
            f"🏷 Группа: {profile.get('group', ctx.group)}",
            f"🎓 Статус учебы: {status_value}",
            f"📅 Дата замечаний: {ctx.selected_date}",
        ]
        if links:
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
        kb.add_button("🎓 Учится", VkKeyboardColor.PRIMARY, payload=_pl("stu_st"))
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

    def write_remark(self, peer_id: int, ctx: UserCtx, text: Optional[str]):
        if not (ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        self.api.set_student_remark(
            self.table_id(),
            ctx.direction,
            ctx.student,
            ctx.selected_date,
            text,
            ctx.group,
        )
        if text:
            self.send(peer_id, f"✅ Замечание записано на {ctx.selected_date}.")
        else:
            self.send(peer_id, f"✅ Записано «замечаний нет» на {ctx.selected_date}.")
        ctx.students_cache = []  # в данных строки могло поменяться
        self.show_student_profile(peer_id, ctx)

    def set_status(self, peer_id: int, ctx: UserCtx, status_value: str):
        if not (ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        self.api.set_student_status(
            self.table_id(), ctx.direction, ctx.student, status_value, ctx.group
        )
        self.send(peer_id, f"✅ Статус обновлён: {status_value}")
        ctx.students_cache = []
        self.show_student_profile(peer_id, ctx)

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


if __name__ == "__main__":
    StudentBot().run()
