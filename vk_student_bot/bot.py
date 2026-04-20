"""VK-бот мониторинга студентов с кнопочным UX."""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass
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


def _payload(cmd: str, value: Optional[str] = None) -> str:
    data = {"cmd": cmd}
    if value is not None:
        data["value"] = value
    return json.dumps(data, ensure_ascii=False)


def _parse_payload(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _pick_direction(directions: List[str], token: str) -> Optional[str]:
    t = token.strip().lower()
    for d in directions:
        dl = d.lower()
        if t == dl or t in dl or dl in t:
            return d
    return None


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

    def table_id(self) -> int:
        self.ensure_table()
        return int(self.table_info["id"])

    def directions(self) -> List[str]:
        names = self.api.list_sheets(self.table_id())
        ordered = []
        for name in SPREADSHEETS:
            for n in names:
                if name.lower() == n.lower() or name.lower() in n.lower():
                    if n not in ordered:
                        ordered.append(n)
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
            if tl in ("начать", "старт", "меню", "помощь", "help", "?"):
                self.show_main(peer_id, "Выберите раздел:")
                return
            if "направлен" in tl:
                self.show_directions(peer_id)
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

            # fallback: попытка выбрать направление/группу/студента текстом
            if self.try_select_by_text(peer_id, ctx, text):
                return
            self.show_main(peer_id, "Не понял команду. Используйте кнопки.")
        except CNCApiError as e:
            self.send(peer_id, f"❌ {e}")
        except Exception as e:
            logger.exception("handle")
            self.send(peer_id, f"❌ Ошибка: {e}")

    def handle_payload(self, peer_id: int, ctx: UserCtx, payload: dict):
        cmd = payload.get("cmd")
        value = payload.get("value", "")
        if cmd == "main":
            self.show_main(peer_id, "Главное меню")
        elif cmd == "directions":
            self.show_directions(peer_id)
        elif cmd == "groups":
            self.show_groups(peer_id, ctx)
        elif cmd == "students":
            self.show_students(peer_id, ctx)
        elif cmd == "pick_direction":
            ctx.direction = value
            ctx.group = None
            ctx.student = None
            self.send(peer_id, f"✅ Направление: {value}")
            self.show_main(peer_id, "Теперь выберите группы или студентов.")
        elif cmd == "pick_group":
            ctx.group = value
            ctx.student = None
            self.send(peer_id, f"✅ Группа: {value}")
            self.show_students(peer_id, ctx)
        elif cmd == "pick_student":
            ctx.student = value
            self.show_student_profile(peer_id, ctx)
        elif cmd == "date":
            self.show_date_picker(peer_id, ctx)
        elif cmd == "date_today":
            ctx.selected_date = _tz_now().strftime("%d.%m.%Y")
            self.send(peer_id, f"📅 Дата: {ctx.selected_date}")
            self.show_student_actions(peer_id)
        elif cmd == "date_minus7":
            d = datetime.strptime(ctx.selected_date, "%d.%m.%Y") - timedelta(days=7)
            ctx.selected_date = d.strftime("%d.%m.%Y")
            self.send(peer_id, f"📅 Дата: {ctx.selected_date}")
            self.show_student_actions(peer_id)
        elif cmd == "date_plus7":
            d = datetime.strptime(ctx.selected_date, "%d.%m.%Y") + timedelta(days=7)
            ctx.selected_date = d.strftime("%d.%m.%Y")
            self.send(peer_id, f"📅 Дата: {ctx.selected_date}")
            self.show_student_actions(peer_id)
        elif cmd == "date_manual":
            ctx.awaiting = "date_input"
            self.send(peer_id, "Введите дату в формате ДД.ММ.ГГГГ")
        elif cmd == "remark_none":
            self.write_remark(peer_id, ctx, None)
        elif cmd == "remark_text":
            ctx.awaiting = "remark_input"
            self.send(peer_id, "Введите текст замечания одним сообщением.")
        elif cmd == "status_study":
            self.set_status(peer_id, ctx, "учится")
        elif cmd == "status_dismissed":
            self.set_status(peer_id, ctx, "отчислен")
        else:
            self.show_main(peer_id, "Неизвестная кнопка, откройте меню.")

    def try_select_by_text(self, peer_id: int, ctx: UserCtx, text: str) -> bool:
        if not text:
            return False
        direction = _pick_direction(self.directions(), text)
        if direction:
            ctx.direction = direction
            ctx.group = None
            ctx.student = None
            self.send(peer_id, f"✅ Направление: {direction}")
            self.show_main(peer_id, "Выберите следующий шаг.")
            return True
        if ctx.direction:
            groups = self.api.list_groups(self.table_id(), ctx.direction)
            for g in groups:
                if text.lower() == g.lower():
                    ctx.group = g
                    self.send(peer_id, f"✅ Группа: {g}")
                    self.show_students(peer_id, ctx)
                    return True
        return False

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
        self.show_student_actions(peer_id)

    def handle_remark_input(self, peer_id: int, ctx: UserCtx, text: str):
        ctx.awaiting = None
        if not text.strip():
            self.send(peer_id, "❌ Пустой текст замечания.")
            self.show_student_actions(peer_id)
            return
        self.write_remark(peer_id, ctx, text.strip())

    def show_main(self, peer_id: int, text: str):
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("1) Направления", VkKeyboardColor.PRIMARY, payload=_payload("directions"))
        kb.add_line()
        kb.add_button("2) Группы", VkKeyboardColor.SECONDARY, payload=_payload("groups"))
        kb.add_button("3) Студент", VkKeyboardColor.SECONDARY, payload=_payload("students"))
        kb.add_line()
        kb.add_button("5) Выбор даты", VkKeyboardColor.SECONDARY, payload=_payload("date"))
        self.send(peer_id, text, keyboard=kb)

    def show_directions(self, peer_id: int):
        dirs = self.directions()
        kb = VkKeyboard(one_time=False, inline=False)
        for i, d in enumerate(dirs[:4]):
            kb.add_button(d, VkKeyboardColor.PRIMARY, payload=_payload("pick_direction", d))
            if i % 2 == 1 and i < 3:
                kb.add_line()
        kb.add_line()
        kb.add_button("Меню", VkKeyboardColor.SECONDARY, payload=_payload("main"))
        self.send(peer_id, "Выберите направление:", keyboard=kb)

    def show_groups(self, peer_id: int, ctx: UserCtx):
        if not ctx.direction:
            self.show_directions(peer_id)
            return
        groups = self.api.list_groups(self.table_id(), ctx.direction)
        if not groups:
            self.send(peer_id, f"В направлении {ctx.direction} группы не найдены.")
            self.show_main(peer_id, "Откройте меню.")
            return
        kb = VkKeyboard(one_time=False, inline=False)
        row_count = 0
        for g in groups[:20]:
            kb.add_button(g, VkKeyboardColor.PRIMARY, payload=_payload("pick_group", g))
            row_count += 1
            if row_count % 2 == 0:
                kb.add_line()
        kb.add_button("Меню", VkKeyboardColor.SECONDARY, payload=_payload("main"))
        self.send(peer_id, f"Направление: {ctx.direction}\nВыберите группу:", keyboard=kb)

    def show_students(self, peer_id: int, ctx: UserCtx):
        if not ctx.direction:
            self.show_directions(peer_id)
            return
        if not ctx.group:
            self.show_groups(peer_id, ctx)
            return
        students = self.api.list_students(self.table_id(), ctx.direction, ctx.group)
        if not students:
            self.send(peer_id, f"В группе {ctx.group} студенты не найдены.")
            return
        kb = VkKeyboard(one_time=False, inline=False)
        for i, st in enumerate(students[:20]):
            fio = st.get("fio", "")
            kb.add_button(fio[:40], VkKeyboardColor.PRIMARY, payload=_payload("pick_student", fio))
            if i % 1 == 0:
                kb.add_line()
        kb.add_button("Меню", VkKeyboardColor.SECONDARY, payload=_payload("main"))
        self.send(peer_id, f"Группа: {ctx.group}\nВыберите студента:", keyboard=kb)

    def show_student_profile(self, peer_id: int, ctx: UserCtx):
        if not (ctx.direction and ctx.group and ctx.student):
            self.show_main(peer_id, "Сначала выберите направление, группу и студента.")
            return
        profile = self.api.get_student_profile(
            self.table_id(), ctx.direction, ctx.student, ctx.group, ctx.selected_date
        )
        status_value = profile.get("status", "") or "-"
        links = profile.get("social_links") or []
        lines = [
            f"👤 {profile.get('fio', ctx.student)}",
            f"📚 Направление: {ctx.direction}",
            f"🏷 Группа: {profile.get('group', ctx.group)}",
            f"🎓 Статус учебы: {status_value}",
            f"📅 Дата замечания: {ctx.selected_date}",
        ]
        if links:
            lines.append("🔗 Соцсети:")
            for link in links:
                lines.append(link)
        else:
            lines.append("🔗 Соцсети: не указаны")
        self.send(peer_id, "\n".join(lines))
        self.show_student_actions(peer_id)

    def show_student_actions(self, peer_id: int):
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("4) Замечаний нет", VkKeyboardColor.POSITIVE, payload=_payload("remark_none"))
        kb.add_button("4) Замечание", VkKeyboardColor.NEGATIVE, payload=_payload("remark_text"))
        kb.add_line()
        kb.add_button("6) Статус: учится", VkKeyboardColor.PRIMARY, payload=_payload("status_study"))
        kb.add_button(
            "6) Статус: отчислен", VkKeyboardColor.SECONDARY, payload=_payload("status_dismissed")
        )
        kb.add_line()
        kb.add_button("5) Выбор даты", VkKeyboardColor.SECONDARY, payload=_payload("date"))
        kb.add_button("Меню", VkKeyboardColor.SECONDARY, payload=_payload("main"))
        self.send(peer_id, "Действия по выбранному студенту:", keyboard=kb)

    def show_date_picker(self, peer_id: int, ctx: UserCtx):
        kb = VkKeyboard(one_time=False, inline=False)
        kb.add_button("Сегодня", VkKeyboardColor.PRIMARY, payload=_payload("date_today"))
        kb.add_button("-7 дней", VkKeyboardColor.SECONDARY, payload=_payload("date_minus7"))
        kb.add_line()
        kb.add_button("+7 дней", VkKeyboardColor.SECONDARY, payload=_payload("date_plus7"))
        kb.add_button("Ввести дату", VkKeyboardColor.SECONDARY, payload=_payload("date_manual"))
        kb.add_line()
        kb.add_button("Назад", VkKeyboardColor.SECONDARY, payload=_payload("main"))
        self.send(peer_id, f"Текущая дата: {ctx.selected_date}", keyboard=kb)

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
        self.show_student_profile(peer_id, ctx)

    def set_status(self, peer_id: int, ctx: UserCtx, status_value: str):
        if not (ctx.direction and ctx.student):
            self.show_main(peer_id, "Сначала выберите студента.")
            return
        self.api.set_student_status(
            self.table_id(), ctx.direction, ctx.student, status_value, ctx.group
        )
        self.send(peer_id, f"✅ Статус обновлён: {status_value}")
        self.show_student_profile(peer_id, ctx)

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
