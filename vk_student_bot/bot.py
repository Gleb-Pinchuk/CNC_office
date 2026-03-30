"""
VK-бот: работа с таблицей CNC Office (SectionTable) через /api/bot/gateway/.
Секреты только из переменных окружения.
"""
from __future__ import annotations

import json
import os
import random
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

# --- env ---
VK_TOKEN = os.getenv("VK_TOKEN", "").strip()
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", "0"))
CNC_API_BASE = os.getenv("CNC_API_BASE", "http://web:8000/api").rstrip("/")
CNC_BOT_SECRET = os.getenv("CNC_BOT_SECRET", os.getenv("CNC_BOT_API_SECRET", "")).strip()
CNC_SECTION_TYPE = os.getenv("CNC_SECTION_TYPE", "rangers").strip()
CNC_TABLE_TITLE_FRAGMENT = os.getenv("CNC_TABLE_TITLE_FRAGMENT", "киберрейнджеры").strip()
DIRS_RAW = os.getenv("CNC_DIRECTION_SHEETS", "ЧПУ,РОБО,Аэро,микро")
SPREADSHEETS = [x.strip() for x in DIRS_RAW.split(",") if x.strip()]
TZ_NAME = os.getenv("TIMEZONE", "Europe/Moscow")

FIO_COL = 2  # колонка ФИО (0-based), как в исходном боте


def _tz_now() -> datetime:
    if ZoneInfo:
        return datetime.now(tz=ZoneInfo(TZ_NAME))
    return datetime.now()


def _headers() -> dict:
    return {"Content-Type": "application/json", "X-CNC-Bot-Token": CNC_BOT_SECRET}


class CNCApi:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def post(self, action: str, payload: dict) -> dict:
        body = {"action": action, **payload}
        r = requests.post(f"{self.base}/bot/gateway/", json=body, headers=_headers(), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(r.text or str(r.status_code))
        return r.json()

    def lookup_table(self) -> dict:
        return self.post(
            "lookup_table",
            {"section_type": CNC_SECTION_TYPE, "title_contains": CNC_TABLE_TITLE_FRAGMENT},
        )

    def get_sheet_data(self, table_id: int, sheet_name: Optional[str]) -> List[List[Any]]:
        data = self.post(
            "get_sheet_data",
            {"table_id": table_id, "sheet_name": sheet_name or ""},
        )
        return data.get("data") or []

    def set_cell(self, table_id: int, sheet_name: Optional[str], row: int, col: int, value: str) -> None:
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


api = CNCApi(CNC_API_BASE)

# глобальное состояние сессии (как в исходном скрипте)
current_spreadsheet: Optional[str] = None  # имя листа-«файла» направления; в CNC = выбранный лист
current_group: Optional[str] = None  # в CNC совпадает с листом или под-листом
user_states: Dict[int, dict] = {}
user_note_col: Dict[int, int] = {}
_table_cache: Dict[str, Any] = {}


def _sheet_names_map() -> dict:
    return {n.lower(): n for n in (_table_cache.get("sheet_names") or [])}


def _resolve_sheet_click(text: str) -> Optional[str]:
    m = _sheet_names_map()
    key = text.strip().lower()
    return m.get(key)


def _table_id() -> int:
    if "id" not in _table_cache:
        info = api.lookup_table()
        _table_cache.update(info)
    return int(_table_cache["id"])


# --- клавиатуры VK ---

def get_main_keyboard() -> str:
    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": [
            [{"action": {"type": "text", "label": "🎓 Направления"}, "color": "primary"},
             {"action": {"type": "text", "label": "📋 Группы"}, "color": "primary"}],
            [{"action": {"type": "text", "label": "👤 Студент"}, "color": "primary"},
             {"action": {"type": "text", "label": "📝 Замечание"}, "color": "primary"}],
            [{"action": {"type": "text", "label": "📅 Колонка даты"}, "color": "primary"},
             {"action": {"type": "text", "label": "🎓 Статус учёбы"}, "color": "primary"}],
            [{"action": {"type": "text", "label": "ℹ️ Помощь"}, "color": "secondary"}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def get_directions_keyboard(sheet_names: List[str]) -> str:
    dirs = [n for n in sheet_names if n.lower() in {s.lower() for s in SPREADSHEETS}]
    if not dirs:
        dirs = sheet_names[:4] or sheet_names
    buttons = [[{"action": {"type": "text", "label": n}, "color": "primary"} for n in dirs]]
    buttons.append([{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}])
    return json.dumps({"one_time": False, "inline": False, "buttons": buttons}, ensure_ascii=False)


def get_groups_keyboard(groups: List[str]) -> str:
    buttons = []
    for i in range(0, len(groups), 2):
        row = [{"action": {"type": "text", "label": groups[i + j]}, "color": "primary"}
               for j in range(2) if i + j < len(groups)]
        buttons.append(row)
    buttons.append([{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}])
    return json.dumps({"one_time": False, "inline": False, "buttons": buttons}, ensure_ascii=False)


def get_students_keyboard(students, page=0, per_page=10) -> str:
    start = page * per_page
    end = start + per_page
    page_students = students[start:end]
    buttons = []
    for i in range(0, len(page_students), 2):
        row = []
        for j in range(2):
            if i + j < len(page_students):
                num, name = page_students[i + j]
                display_name = name[:20] + "..." if len(name) > 20 else name
                row.append({"action": {"type": "text", "label": f"{num}. {display_name}"}, "color": "primary"})
        buttons.append(row)
    nav_row = []
    if page > 0:
        nav_row.append({"action": {"type": "text", "label": "⬅️ Назад"}, "color": "secondary"})
    if end < len(students):
        nav_row.append({"action": {"type": "text", "label": "Вперёд ➡️"}, "color": "secondary"})
    if nav_row:
        buttons.append(nav_row)
    buttons.append([{"action": {"type": "text", "label": "🔙 В меню"}, "color": "secondary"}])
    return json.dumps({"one_time": False, "inline": False, "buttons": buttons}, ensure_ascii=False)


def get_back_keyboard() -> str:
    return json.dumps(
        {"one_time": False, "inline": False, "buttons": [[{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}]]},
        ensure_ascii=False,
    )


def get_week_choice_keyboard(options: List[Tuple[int, str]]) -> str:
    buttons = []
    row = []
    for i, (col, label) in enumerate(options[:8]):
        short = (label[:28] + "…") if len(label) > 30 else label
        row.append({"action": {"type": "text", "label": f"{i+1}. {short}"}, "color": "primary"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}])
    return json.dumps({"one_time": False, "inline": False, "buttons": buttons}, ensure_ascii=False)


def get_status_keyboard() -> str:
    return json.dumps(
        {"one_time": False, "inline": False,
         "buttons": [
             [{"action": {"type": "text", "label": "✅ Учится"}, "color": "positive"},
              {"action": {"type": "text", "label": "⛔ Отчислен"}, "color": "negative"}],
             [{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}],
         ]},
        ensure_ascii=False,
    )


def send_vk_message(vk, user_id: int, message: str, keyboard: Optional[str] = None) -> None:
    params = {"user_id": user_id, "message": message, "random_id": random.randint(0, 2 ** 31)}
    if keyboard:
        params["keyboard"] = keyboard
    vk.messages.send(**params)


def parse_week_columns(headers: List[str], today: date) -> List[Tuple[int, str, Optional[date], Optional[date]]]:
    """Возвращает список (col_idx, заголовок, start_date, end_date)."""
    out: List[Tuple[int, str, Optional[date], Optional[date]]] = []
    y = today.year
    for c, raw in enumerate(headers):
        h = str(raw or "").strip()
        if not h:
            continue
        # dd.mm.yyyy - dd.mm.yyyy
        m = re.search(r"(\d{1,2}\.\d{1,2}\.(\d{4}))\s*[-–]\s*(\d{1,2}\.\d{1,2}\.(\d{4}))", h)
        if m:
            try:
                ds = datetime.strptime(m.group(1), "%d.%m.%Y").date()
                de = datetime.strptime(m.group(3), "%d.%m.%Y").date()
                out.append((c, h, ds, de))
            except ValueError:
                continue
            continue
        # dd.mm - dd.mm (год текущий / перенос через Новый год)
        m2 = re.search(r"(\d{1,2}\.\d{1,2})\s*[-–]\s*(\d{1,2}\.\d{1,2})", h)
        if m2:
            try:
                a, b = m2.group(1), m2.group(2)
                ds = datetime.strptime(f"{a}.{y}", "%d.%m.%Y").date()
                de = datetime.strptime(f"{b}.{y}", "%d.%m.%Y").date()
                if de < ds:
                    de = de.replace(year=y + 1)
                out.append((c, h, ds, de))
            except ValueError:
                continue
    return out


def get_current_week_column_meta(headers: List[str]) -> Tuple[Optional[int], Optional[str]]:
    today = _tz_now().date()
    for col, label, ds, de in parse_week_columns(headers, today):
        if ds and de and ds <= today <= de:
            return col, label
    return None, None


def find_status_column_index(headers: List[str]) -> Optional[int]:
    for c, h in enumerate(headers):
        t = str(h or "").lower()
        if "учится" in t or "отчисл" in t or "статус" in t:
            return c
    return None


def get_students_list(group_name: Optional[str]) -> List[Tuple[int, str]]:
    tid = _table_id()
    rows = api.get_sheet_data(tid, group_name or current_group or current_spreadsheet)
    if len(rows) < 2:
        return []
    students = []
    for i, row in enumerate(rows[1:], 1):
        if len(row) > FIO_COL:
            fio = str(row[FIO_COL]).strip()
            if fio:
                students.append((i, fio))
    return students


def header_row(sheet_name: Optional[str]) -> List[str]:
    rows = api.get_sheet_data(_table_id(), sheet_name or current_group or current_spreadsheet)
    if not rows:
        return []
    return [str(x or "").strip() for x in rows[0]]


def get_student_by_number(row_number: int, group_name: Optional[str], note_col: Optional[int] = None) -> str:
    tid = _table_id()
    sh = group_name or current_group or current_spreadsheet
    rows = api.get_sheet_data(tid, sh)
    if len(rows) < 2:
        return "❌ В таблице нет данных!"
    if row_number < 1 or row_number >= len(rows):
        return f"❌ Студент #{row_number} не найден. Всего строк: {len(rows)-1}"
    headers = rows[0] if rows[0] else []
    student_row = rows[row_number]
    data = {}
    for i, header in enumerate(headers):
        if i < len(student_row):
            data[str(header)] = student_row[i]
    hdr_list = [str(h or "") for h in headers]
    col_num, week_range = get_current_week_column_meta(hdr_list)
    use_col = note_col if note_col is not None else col_num
    current_note = ""
    if use_col is not None and use_col < len(student_row):
        current_note = str(student_row[use_col] or "")
    phone = data.get("Номер телефона") or data.get("Телефон") or "-"
    msg = (
        f"🔍 Студент #{row_number}\n\n"
        f"📋 Лист: {sh or '—'}\n"
        f"👤 ФИО: {data.get('ФИО', '-')}\n"
        f"📱 Телефон: {phone}\n"
        f"📱 Telegram: {data.get('Телеграм', '-')}\n"
        f"💬 ВКонтакте: {data.get('Вконтакте', '-')}\n"
        f"🎵 TikTok: {data.get('ТикТок', data.get('Тикток', '-'))}\n"
        f"📅 Неделя (колонка): {week_range if week_range else 'Не определена'}\n"
        f"📝 Замечание: {current_note or 'Нет'}"
    )
    return msg


def write_note(
    row_number: int,
    note_text: str,
    group_name: Optional[str],
    user_id: Optional[int] = None,
) -> str:
    tid = _table_id()
    sh = group_name or current_group or current_spreadsheet
    rows = api.get_sheet_data(tid, sh)
    if len(rows) < 2:
        return "❌ В таблице нет данных!"
    if row_number < 1 or row_number >= len(rows):
        return f"❌ Студент #{row_number} не найден!"
    hdr_list = [str(h or "") for h in (rows[0] or [])]
    col_num, week_range = get_current_week_column_meta(hdr_list)
    c = user_note_col.get(user_id) if user_id is not None else None
    if c is None:
        c = col_num
    if c is None:
        return "❌ Не выбрана колонка недели. Нажмите «📅 Колонка даты»."
    api.set_cell(tid, sh, row_number, c, note_text)
    fio = rows[row_number][FIO_COL] if len(rows[row_number]) > FIO_COL else "—"
    return (
        f"✅ Замечание записано!\n\n"
        f"📋 Лист: {sh}\n"
        f"👤 Студент: {fio}\n"
        f"📅 Колонка: {hdr_list[c] if c < len(hdr_list) else c}\n"
        f"📝 Текст: {note_text}"
    )


def write_status(row_number: int, status_text: str, group_name: Optional[str]) -> str:
    tid = _table_id()
    sh = group_name or current_group or current_spreadsheet
    rows = api.get_sheet_data(tid, sh)
    if len(rows) < 2:
        return "❌ В таблице нет данных!"
    hdr = [str(h or "") for h in (rows[0] or [])]
    c = find_status_column_index(hdr)
    if c is None:
        return "❌ Не найдена колонка статуса (ожидаются слова «учится» / «отчисл» в заголовке)."
    api.set_cell(tid, sh, row_number, c, status_text)
    fio = rows[row_number][FIO_COL] if len(rows[row_number]) > FIO_COL else "—"
    return f"✅ Статус обновлён: {status_text}\n👤 {fio}\n📋 {hdr[c]}"


def parse_student_button(text: str) -> Tuple[Optional[int], Optional[str]]:
    m = re.match(r"^(\d+)\.\s*(.+)$", text.strip())
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, None


def main() -> None:
    global current_spreadsheet, current_group
    if not VK_TOKEN or not VK_GROUP_ID:
        raise SystemExit("Задайте VK_TOKEN и VK_GROUP_ID")
    if not CNC_BOT_SECRET:
        raise SystemExit("Задайте CNC_BOT_SECRET (как CNC_BOT_API_SECRET в Django)")

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)
    print("🤖 VK бот CNC Office запущен")

    try:
        info = api.lookup_table()
        _table_cache.update(info)
        print("📎 Таблица:", info.get("title"), "id=", info.get("id"), "листы:", info.get("sheet_names"))
    except Exception as e:
        print("⚠️ lookup_table:", e)

    for event in longpoll.listen():
        try:
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            message = event.obj.message
            user_id = message["from_id"]
            text = (message.get("text") or "").strip()
            text_lower = text.lower()
            print(f"📨 {user_id}: {text}")

            if user_id in user_states:
                st = user_states[user_id]
                act = st.get("action")

                if act == "pick_week_col":
                    opts: List[Tuple[int, str]] = st.get("options", [])
                    if text_lower in ("🔙 назад", "🔙 в меню"):
                        del user_states[user_id]
                        send_vk_message(vk, user_id, "Меню", get_main_keyboard())
                        continue
                    n_pick = None
                    if text.strip().isdigit():
                        n_pick = int(text.strip())
                    else:
                        mm = re.match(r"^(\d+)\.", text.strip())
                        if mm:
                            n_pick = int(mm.group(1))
                    if n_pick is not None and 1 <= n_pick <= len(opts):
                        col, lab = opts[n_pick - 1]
                        user_note_col[user_id] = col
                        del user_states[user_id]
                        send_vk_message(
                            vk,
                            user_id,
                            f"✅ Для замечаний используется колонка:\n{lab}",
                            get_main_keyboard(),
                        )
                        continue
                    send_vk_message(vk, user_id, "Введите номер колонки из списка или Назад.", get_back_keyboard())
                    continue

                if act == "write_note":
                    sn, _ = parse_student_button(text)
                    if sn:
                        send_vk_message(
                            vk,
                            user_id,
                            f"✍️ Введите текст замечания для строки {sn}:",
                            get_back_keyboard(),
                        )
                        user_states[user_id] = {
                            "action": "write_note_text",
                            "row": sn,
                        }
                        continue
                    parts = text.split(maxsplit=1)
                    if len(parts) >= 2 and parts[0].isdigit():
                        row = int(parts[0])
                        note = parts[1]
                        res = write_note(row, note, current_group, user_id=user_id)
                        send_vk_message(vk, user_id, res, get_main_keyboard())
                        del user_states[user_id]
                        continue
                    send_vk_message(vk, user_id, "⚠️ Номер и текст, например: `5 Не посещает`", get_back_keyboard())
                    del user_states[user_id]
                    continue

                if act == "write_note_text":
                    row = st["row"]
                    res = write_note(row, text, current_group, user_id=user_id)
                    send_vk_message(vk, user_id, res, get_main_keyboard())
                    del user_states[user_id]
                    continue

                if act == "set_status":
                    if "отчислен" in text_lower:
                        code = "Отчислен"
                    elif "учится" in text_lower:
                        code = "Учится"
                    else:
                        send_vk_message(vk, user_id, "Нажмите кнопку статуса.", get_status_keyboard())
                        continue
                    row = st["row"]
                    msg = write_status(row, code, current_group)
                    send_vk_message(vk, user_id, msg, get_main_keyboard())
                    del user_states[user_id]
                    continue

                if act == "get_student":
                    if text_lower == "вперёд ➡️":
                        st["page"] = st.get("page", 0) + 1
                    elif text_lower == "⬅️ назад":
                        st["page"] = max(0, st.get("page", 0) - 1)
                    else:
                        sn, _ = parse_student_button(text)
                        if sn:
                            nc = user_note_col.get(user_id)
                            send_vk_message(vk, user_id, get_student_by_number(sn, current_group, nc), get_main_keyboard())
                            del user_states[user_id]
                            continue
                        if text.strip().isdigit():
                            sn = int(text.strip())
                            send_vk_message(
                                vk,
                                user_id,
                                get_student_by_number(sn, current_group, user_note_col.get(user_id)),
                                get_main_keyboard(),
                            )
                            del user_states[user_id]
                            continue
                    students = st.get("students", [])
                    p = st.get("page", 0)
                    send_vk_message(
                        vk,
                        user_id,
                        f"👤 Студенты ({current_group}):\n\nВыберите номер или фамилию:",
                        get_students_keyboard(students, p),
                    )
                    continue

                if act == "pick_student_status":
                    sn, _ = parse_student_button(text)
                    if not sn and text.strip().isdigit():
                        sn = int(text.strip())
                    if sn:
                        user_states[user_id] = {"action": "set_status", "row": sn}
                        send_vk_message(vk, user_id, f"Строка {sn}. Выберите статус:", get_status_keyboard())
                    else:
                        send_vk_message(
                            vk,
                            user_id,
                            "Выберите студента кнопкой.",
                            get_students_keyboard(st.get("students", []), 0),
                        )
                    continue

                del user_states[user_id]
                send_vk_message(vk, user_id, "Меню", get_main_keyboard())
                continue

            # --- верхнее меню ---
            if text_lower in ("🎓 направления", "/table"):
                names = _table_cache.get("sheet_names") or []
                if not names:
                    try:
                        info = api.lookup_table()
                        _table_cache.update(info)
                        names = info.get("sheet_names") or []
                    except Exception as e:
                        send_vk_message(vk, user_id, f"❌ API: {e}", get_main_keyboard())
                        continue
                send_vk_message(vk, user_id, "🎓 Выберите направление (лист):", get_directions_keyboard(names))

            elif text_lower in ("📋 группы", "/groups"):
                try:
                    info = api.lookup_table()
                    _table_cache.update(info)
                    names = info.get("sheet_names") or []
                except Exception as e:
                    send_vk_message(vk, user_id, f"❌ {e}", get_main_keyboard())
                    continue
                main_set = {s.lower() for s in SPREADSHEETS}
                groups = [n for n in names if n.lower() not in main_set] or names
                if groups:
                    send_vk_message(vk, user_id, "📋 Выберите группу (лист):", get_groups_keyboard(groups))
                else:
                    send_vk_message(vk, user_id, "❌ Нет листов", get_main_keyboard())

            elif text_lower in ("📅 колонка даты",):
                hdr = header_row(current_group or current_spreadsheet)
                opts = [(c, lab) for c, lab, _, _ in parse_week_columns(hdr, _tz_now().date())]
                if not opts:
                    # любые заголовки с цифрами — на крайний случай
                    opts = [(i, h) for i, h in enumerate(hdr) if h and re.search(r"\d", h)]
                if not opts:
                    send_vk_message(vk, user_id, "❌ Не найдены заголовки с датами (формат 01.01-07.01 или с годом).", get_main_keyboard())
                    continue
                user_states[user_id] = {"action": "pick_week_col", "options": opts}
                lines = "\n".join([f"{i+1}. {lab}" for i, (_, lab) in enumerate(opts[:12])])
                send_vk_message(
                    vk,
                    user_id,
                    f"📅 Выберите колонку для замечаний (номер или кнопку):\n{lines}",
                    get_week_choice_keyboard(opts),
                )

            elif text_lower in ("🎓 статус учёбы",):
                if not current_group:
                    send_vk_message(vk, user_id, "⚠️ Сначала выберите группу (лист).", get_main_keyboard())
                    continue
                students = get_students_list(current_group)
                if not students:
                    send_vk_message(vk, user_id, "❌ Нет студентов", get_back_keyboard())
                    continue
                send_vk_message(
                    vk,
                    user_id,
                    "Выберите студента, затем статус:\n" + "\n".join(f"{n}. {name}" for n, name in students[:10]),
                    get_students_keyboard(students, 0),
                )
                user_states[user_id] = {"action": "pick_student_status", "students": students}

            elif text_lower in ("👤 студент", "/get"):
                if not current_group:
                    send_vk_message(vk, user_id, "⚠️ Сначала выберите направление/группу.", get_main_keyboard())
                    continue
                students = get_students_list(current_group)
                if students:
                    user_states[user_id] = {"action": "get_student", "students": students, "page": 0}
                    send_vk_message(
                        vk,
                        user_id,
                        f"👤 Студенты ({current_group}):\nВведите номер или нажмите кнопку:",
                        get_students_keyboard(students, 0),
                    )
                else:
                    send_vk_message(vk, user_id, "❌ Нет студентов", get_back_keyboard())

            elif text_lower in ("📝 замечание", "/note"):
                if not current_group:
                    send_vk_message(vk, user_id, "⚠️ Сначала выберите группу.", get_main_keyboard())
                    continue
                students = get_students_list(current_group)
                if not students:
                    send_vk_message(vk, user_id, "❌ Нет студентов", get_back_keyboard())
                    continue
                user_states[user_id] = {"action": "write_note", "students": students}
                send_vk_message(
                    vk,
                    user_id,
                    "📝 Введите номер и текст или выберите фамилию\nПример: `5 Не посещает`",
                    get_students_keyboard(students, 0),
                )

            elif text_lower in ("ℹ️ помощь", "/help", "/start", "начать"):
                help_text = (
                    "🤖 Бот CNC Office (без Google)\n\n"
                    f"📌 Листы-направления: {', '.join(SPREADSHEETS)}\n"
                    f"📋 Текущий лист: {current_group or '—'}\n\n"
                    "• Сначала «Направления» или «Группы» — выбор листа.\n"
                    "• «Колонка даты» — в какой столбец писать замечания.\n"
                    "• «Замечание» / «Студент» — как раньше.\n"
                    "• «Статус учёбы» — кнопки Учится/Отчислен (колонка с «учится/отчисл»).\n"
                    "Заголовки недель: 01.01-07.01 или 01.01.2026-07.01.2026."
                )
                send_vk_message(vk, user_id, help_text, get_main_keyboard())

            elif text_lower in ("🔙 назад", "🔙 в меню"):
                send_vk_message(vk, user_id, "Меню", get_main_keyboard())

            elif text.isdigit() and current_group:
                try:
                    row = int(text)
                    send_vk_message(
                        vk,
                        user_id,
                        get_student_by_number(row, current_group, user_note_col.get(user_id)),
                        get_main_keyboard(),
                    )
                except Exception:
                    send_vk_message(vk, user_id, "Ошибка", get_main_keyboard())

            else:
                chosen = _resolve_sheet_click(text)
                if chosen:
                    current_spreadsheet = chosen
                    current_group = chosen
                    send_vk_message(vk, user_id, f"✅ Выбран лист: {chosen}", get_main_keyboard())
                else:
                    send_vk_message(vk, user_id, "Используйте кнопки или /помощь", get_main_keyboard())

        except Exception as e:
            print("❌", e)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
