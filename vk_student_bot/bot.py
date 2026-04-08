"""
VK-бот: работа с таблицей CNC Office (SectionTable) через /api/bot/gateway/.
Секреты только из переменных окружения.
"""

from __future__ import annotations

import json
import os
import random
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

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
        r = requests.post(
            f"{self.base}/bot/gateway/", json=body, headers=_headers(), timeout=60
        )
        if r.status_code >= 400:
            raise RuntimeError(r.text or str(r.status_code))
        return r.json()

    def lookup_table(self) -> dict:
        return self.post(
            "lookup_table",
            {
                "section_type": CNC_SECTION_TYPE,
                "title_contains": CNC_TABLE_TITLE_FRAGMENT,
            },
        )


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


api = CNCApi(CNC_API_BASE)

# глобальное состояние сессии
user_states: Dict[int, dict] = {}
user_note_col: Dict[int, int] = {}
_table_cache: Dict[str, Any] = {}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _social_url(value: Any, platform: str) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "-":
        return "-"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    cleaned = raw.lstrip("@").strip()
    if not cleaned:
        return "-"
    if platform == "telegram":
        return f"https://t.me/{cleaned}"
    if platform == "vk":
        return f"https://vk.com/{cleaned}"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{cleaned}"
    return raw


def _table_id() -> int:
    table_id = _table_cache.get("id") or _table_cache.get("table_id")
    if table_id:
        return int(table_id)
    info = api.lookup_table()
    _table_cache.update(info)
    table_id = _table_cache.get("id") or _table_cache.get("table_id")
    if not table_id:
        raise RuntimeError("table_id not found")
    return int(table_id)


def _resolve_sheet_click(text: str) -> Optional[str]:
    names = _table_cache.get("sheet_names") or []
    if not names:
        try:
            info = api.lookup_table()
            _table_cache.update(info)
            names = _table_cache.get("sheet_names") or []
        except Exception:
            return None

    raw = (text or "").strip()
    if not raw:
        return None
    raw_low = raw.lower()
    for name in names:
        n = str(name or "").strip()
        if not n:
            continue
        if raw == n or raw_low == n.lower():
            return n
    return None


def _get_user_val(user_id: int, key: str) -> Optional[Any]:
    return user_states.get(user_id, {}).get(key)


def _sheet_rows(user_id: int) -> List[List[Any]]:
    """Текущий лист-направление (worksheet) для конкретного пользователя."""
    sh = _get_user_val(user_id, "current_spreadsheet")
    if not sh:
        return []
    return api.get_sheet_data(_table_id(), sh)


def _detect_col(headers: List[str], keywords: List[str], default_idx: int) -> int:
    low = [str(h or "").strip().lower() for h in headers]
    for i, h in enumerate(low):
        for kw in keywords:
            if kw in h:
                return i
    return default_idx


def _group_col(headers: List[str]) -> int:
    return _detect_col(headers, ["груп"], GROUP_COL_DEFAULT)


def _fio_col(headers: List[str]) -> int:
    return _detect_col(headers, ["фио"], FIO_COL_DEFAULT)


def _status_col(headers: List[str]) -> int:
    # если нет явного совпадения — используем 12-й столбец по ТЗ
    idx = _detect_col(headers, ["учится", "отчисл", "статус"], STATUS_COL_DEFAULT)
    return idx


def get_groups_list(user_id: int) -> List[str]:
    """Группы берём из 2-го столбца (B) текущего листа пользователя."""
    rows = _sheet_rows(user_id)
    if len(rows) < 2:
        return []
    headers = [str(x or "").strip() for x in (rows[0] or [])]
    gc = _group_col(headers)
    groups = []
    seen = set()
    for r in rows[1:]:
        if gc < len(r):
            g = str(r[gc] or "").strip()
            if g and g.lower() not in seen:
                seen.add(g.lower())
                groups.append(g)
    return groups


def get_students_map(user_id: int, group_value: Optional[str]) -> List[Tuple[int, str]]:
    """
    Возвращает список (sheet_row_index, fio). sheet_row_index — индекс строки в листе (0-based).
    """
    rows = _sheet_rows(user_id)
    if len(rows) < 2:
        return []
    headers = [str(x or "").strip() for x in (rows[0] or [])]
    gc = _group_col(headers)
    fc = _fio_col(headers)
    target = (group_value or "").strip().lower()
    out: List[Tuple[int, str]] = []
    for idx in range(1, len(rows)):
        r = rows[idx] or []
        g = str(r[gc] or "").strip().lower() if gc < len(r) else ""
        if target and g != target:
            continue
        fio = str(r[fc] or "").strip() if fc < len(r) else ""
        if fio:
            out.append((idx, fio))
    return out


def header_row(user_id: int) -> List[str]:
    rows = _sheet_rows(user_id)
    if not rows:
        return []
    return [str(x or "").strip() for x in (rows[0] or [])]


def get_student_by_number(
    user_id: int, row_number: int, note_col: Optional[int] = None
) -> str:
    sh = _get_user_val(user_id, "current_spreadsheet")
    rows = _sheet_rows(user_id)
    if len(rows) < 2:
        return "❌ В таблице нет данных!"
    group = _get_user_val(user_id, "current_group")
    students_map = get_students_map(user_id, group)
    if row_number < 1 or row_number > len(students_map):
        return f"❌ Студент #{row_number} не найден. Всего: {len(students_map)}"
    headers = rows[0] if rows[0] else []
    sheet_row_idx = students_map[row_number - 1][0]
    student_row = rows[sheet_row_idx]
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
    telegram_url = _social_url(data.get("Телеграм", "-"), "telegram")
    vk_url = _social_url(data.get("Вконтакте", "-"), "vk")
    tiktok_raw = data.get("ТикТок", data.get("Тикток", "-"))
    tiktok_url = _social_url(tiktok_raw, "tiktok")
    msg = (
        f"🔍 Студент #{row_number}\n\n"
        f"🎓 Направление (лист): {sh or '—'}\n"
        f"📋 Группа: {group or '—'}\n"
        f"👤 ФИО: {data.get('ФИО', '-')}\n"
        f"📱 Телефон: {phone}\n"
        f"📱 Telegram: {telegram_url}\n"
        f"💬 ВКонтакте: {vk_url}\n"
        f"🎵 TikTok: {tiktok_url}\n"
        f"📅 Неделя (колонка): {week_range if week_range else 'Не определена'}\n"
        f"📝 Замечание: {current_note or 'Нет'}"
    )
    return msg


def write_note(
    user_id: int,
    row_number: int,
    note_text: str,
) -> str:
    tid = _table_id()
    sh = _get_user_val(user_id, "current_spreadsheet")
    rows = _sheet_rows(user_id)
    if len(rows) < 2:
        return "❌ В таблице нет данных!"
    group = _get_user_val(user_id, "current_group")
    students_map = get_students_map(user_id, group)
    if row_number < 1 or row_number > len(students_map):
        return f"❌ Студент #{row_number} не найден!"
    hdr_list = [str(h or "") for h in (rows[0] or [])]
    col_num, week_range = get_current_week_column_meta(hdr_list)
    c = user_note_col.get(user_id)
    try:
        c = int(c) if c is not None else None
    except (TypeError, ValueError):
        c = None
    if c is None or c < 0 or c >= len(hdr_list):
        c = col_num
    if c is None:
        return "❌ Не выбрана колонка недели. Нажмите «📅 Колонка даты»."
    sheet_row_idx = students_map[row_number - 1][0]
    api.set_cell(tid, sh, sheet_row_idx, c, note_text)
    headers = [str(h or "") for h in (rows[0] or [])]
    fio = students_map[row_number - 1][1]
    return (
        f"✅ Замечание записано!\n\n"
        f"🎓 Лист: {sh}\n"
        f"📋 Группа: {group or '—'}\n"
        f"👤 Студент: {fio}\n"
        f"📅 Колонка: {headers[c] if c < len(headers) else c}\n"
        f"📝 Текст: {note_text}"
    )


def write_status(user_id: int, row_number: int, status_text: str) -> str:
    tid = _table_id()
    sh = _get_user_val(user_id, "current_spreadsheet")
    rows = _sheet_rows(user_id)
    if len(rows) < 2:
        return "❌ В таблице нет данных!"
    hdr = [str(h or "") for h in (rows[0] or [])]
    c = _status_col(hdr)
    group = _get_user_val(user_id, "current_group")
    students_map = get_students_map(user_id, group)
    if row_number < 1 or row_number > len(students_map):
        return f"❌ Студент #{row_number} не найден!"
    sheet_row_idx = students_map[row_number - 1][0]
    api.set_cell(tid, sh, sheet_row_idx, c, status_text)
    fio = students_map[row_number - 1][1]
    return f"✅ Статус обновлён: {status_text}\n👤 {fio}\n📋 {hdr[c]}"


def parse_student_button(text: str) -> Tuple[Optional[int], Optional[str]]:
    m = re.match(r"^(\d+)\.\s*(.+)$", text.strip())
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, None


def get_main_keyboard() -> str:
    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "🎓 Направления"}, "color": "primary"},
                {"action": {"type": "text", "label": "📋 Группы"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "👤 Студент"}, "color": "primary"},
                {"action": {"type": "text", "label": "📝 Замечание"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "📅 Колонка даты"}, "color": "primary"},
                {"action": {"type": "text", "label": "🎓 Статус учёбы"}, "color": "primary"},
            ],
            [{"action": {"type": "text", "label": "ℹ️ Помощь"}, "color": "secondary"}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def get_directions_keyboard(sheet_names: List[str]) -> str:
    dirs = [n for n in sheet_names if n.lower() in {s.lower() for s in SPREADSHEETS}]
    if not dirs:
        dirs = sheet_names[:4] or sheet_names
    buttons = []
    if dirs:
        buttons.append(
            [{"action": {"type": "text", "label": n}, "color": "primary"} for n in dirs]
        )
    buttons.append([{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}])
    return json.dumps({"one_time": False, "inline": False, "buttons": buttons}, ensure_ascii=False)


def get_groups_keyboard(groups: List[str]) -> str:
    buttons = []
    for i in range(0, len(groups), 2):
        row = [{"action": {"type": "text", "label": groups[i + j]}, "color": "primary"} for j in range(2) if i + j < len(groups)]
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
    return json.dumps({"one_time": False, "inline": False, "buttons": [[{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}]]}, ensure_ascii=False)


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
    return json.dumps({"one_time": False, "inline": False, "buttons": [[{"action": {"type": "text", "label": "✅ Учится"}, "color": "positive"}, {"action": {"type": "text", "label": "⛔ Отчислен"}, "color": "negative"}], [{"action": {"type": "text", "label": "🔙 Назад"}, "color": "secondary"}]]}, ensure_ascii=False)


def send_vk_message(vk, user_id: int, message: str, keyboard: Optional[str] = None) -> None:
    params = {"user_id": user_id, "message": message, "random_id": random.randint(0, 2**31)}
    try:
        if keyboard:
            params["keyboard"] = keyboard
        vk.messages.send(**params)
    except Exception:
        params.pop("keyboard", None)
        vk.messages.send(**params)


def parse_week_columns(headers: List[str], today: date) -> List[Tuple[int, str, Optional[date], Optional[date]]]:
    out = []
    y = today.year
    ddm = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?")
    range_dash = re.compile(r"(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\s*\.?\s*[-–]\s*(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)")

    def to_date(s: str) -> Optional[date]:
        s = s.strip()
        m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", s)
        if m:
            d, mo, yy = m.groups()
            fmt = "%d.%m.%Y" if len(yy) == 4 else "%d.%m.%y"
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                return None
        m2 = re.match(r"^(\d{1,2})\.(\d{1,2})$", s)
        if not m2:
            return None
        d, mo = m2.groups()
        try:
            return date(int(y), int(mo), int(d))
        except ValueError:
            return None

    for c, raw in enumerate(headers):
        h = str(raw or "").strip()
        if not h:
            continue
        m = range_dash.search(h)
        if m:
            left, right = m.group(1), m.group(2)
            ds, de = to_date(left), to_date(right)
            if ds and de:
                if ds <= de:
                    out.append((c, h, ds, de))
                else:
                    if not re.search(r"\.\d{4}\b|\.\d{2}\b", left) and not re.search(r"\.\d{4}\b|\.\d{2}\b", right):
                        try:
                            de2 = date(ds.year + 1, de.month, de.day)
                            out.append((c, h, ds, de2))
                        except ValueError:
                            pass
                continue
        parts = ddm.findall(h)
        if len(parts) < 1:
            continue

        def build(idx: int) -> Optional[date]:
            d_s, m_s, y_s = parts[idx]
            if y_s:
                fmt = "%d.%m.%Y" if len(y_s) == 4 else "%d.%m.%y"
                try:
                    return datetime.strptime(f"{d_s}.{m_s}.{y_s}", fmt).date()
                except ValueError:
                    return None
            try:
                return date(y, int(m_s), int(d_s))
            except ValueError:
                return None

        ds = build(0)
        de = build(1) if len(parts) > 1 else ds
        if not ds or not de:
            continue
        if de < ds:
            try:
                de = date(ds.year + 1, de.month, de.day)
            except ValueError:
                continue
        out.append((c, h, ds, de))
    return out


def get_current_week_column_meta(headers: List[str]) -> Tuple[Optional[int], Optional[str]]:
    today = _tz_now().date()
    parsed = parse_week_columns(headers, today)
    for col, label, ds, de in parsed:
        if ds and de and ds <= today <= de:
            return col, label
    past = [(de, col, label) for col, label, ds, de in parsed if ds and de and de < today]
    if past:
        _, col, label = max(past, key=lambda x: x[0])
        return col, label
    future = [(ds, col, label) for col, label, ds, de in parsed if ds and de and ds > today]
    if future:
        _, col, label = min(future, key=lambda x: x[0])
        return col, label
    return None, None


def main() -> None:
    if not VK_TOKEN or not VK_GROUP_ID:
        raise SystemExit("Задайте VK_TOKEN и VK_GROUP_ID")
    if not CNC_BOT_SECRET:
        raise SystemExit("Задайте CNC_BOT_SECRET")

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)
    print("🤖 VK бот CNC Office запущен")

    try:
        info = api.lookup_table()
        _table_cache.update(info)
    except Exception as e:
        print("⚠️ lookup_table:", e)

    for event in longpoll.listen():
        try:
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            message = event.obj.message
            user_id = message["from_id"]
            text = (message.get("text") or "").strip()
            text_lower = _normalize_text(text)

            if user_id not in user_states:
                user_states[user_id] = {}
            st = user_states[user_id]

            if ("в меню" in text_lower) or (text_lower == "назад") or (
                "назад" in text_lower and "⬅" not in text and "🔙" in text
            ):
                cur_sh = st.get("current_spreadsheet")
                cur_gr = st.get("current_group")
                user_states[user_id] = {"current_spreadsheet": cur_sh, "current_group": cur_gr}
                send_vk_message(vk, user_id, "Меню", get_main_keyboard())
                continue

            act = st.get("action")


            if act == "pick_week_col":
                opts = st.get("options", [])
                n_pick = None
                if text.isdigit():
                    n_pick = int(text)
                else:
                    mm = re.match(r"^(\d+)\.", text)
                    if mm:
                        n_pick = int(mm.group(1))
                if n_pick and 1 <= n_pick <= len(opts):
                    col, lab = opts[n_pick - 1]
                    user_note_col[user_id] = col
                    st["action"] = None
                    send_vk_message(vk, user_id, f"✅ Колонка: {lab}", get_main_keyboard())
                    continue

            if act in ("get_student", "write_note", "pick_student_status"):
                if "впер" in text_lower:
                    st["page"] = st.get("page", 0) + 1
                    send_vk_message(vk, user_id, "Следующая страница:", get_students_keyboard(st["students"], st["page"]))
                    continue
                if "назад" in text_lower and "меню" not in text_lower:
                    st["page"] = max(0, st.get("page", 0) - 1)
                    send_vk_message(vk, user_id, "Предыдущая страница:", get_students_keyboard(st["students"], st["page"]))
                    continue

                sn, _ = parse_student_button(text)
                if not sn and text.isdigit():
                    sn = int(text)

                if sn:
                    if act == "get_student":
                        nc = user_note_col.get(user_id)
                        res = get_student_by_number(user_id, sn, nc)
                        send_vk_message(vk, user_id, res, get_main_keyboard())
                        st["action"] = None
                    elif act == "write_note":
                        st["action"] = "write_note_text"
                        st["row"] = sn
                        send_vk_message(vk, user_id, f"✍️ Введите текст замечания для студента #{sn}:", get_back_keyboard())
                    elif act == "pick_student_status":
                        st["action"] = "set_status"
                        st["row"] = sn
                        send_vk_message(vk, user_id, "Выберите статус:", get_status_keyboard())
                    continue

            if act == "write_note_text":
                res = write_note(user_id, st.get("row"), text)
                send_vk_message(vk, user_id, res, get_main_keyboard())
                st["action"] = None
                continue

            if act == "set_status":
                code = "Отчислен" if "отчислен" in text_lower else "Учится" if "учится" in text_lower else None
                if code:
                    res = write_status(user_id, st.get("row"), code)
                    send_vk_message(vk, user_id, res, get_main_keyboard())
                    st["action"] = None
                    continue

            if "направлен" in text_lower:
                names = _table_cache.get("sheet_names") or []
                if not names:
                    try:
                        info = api.lookup_table()
                        _table_cache.update(info)
                        names = _table_cache.get("sheet_names") or []
                    except Exception as err:
                        send_vk_message(
                            vk,
                            user_id,
                            f"⚠️ Не удалось загрузить направления: {err}",
                            get_main_keyboard(),
                        )
                        continue
                if not names:
                    send_vk_message(vk, user_id, "⚠️ Список направлений пуст.", get_main_keyboard())
                    continue
                send_vk_message(vk, user_id, "Выберите направление:", get_directions_keyboard(names))
                continue

            if "групп" in text_lower and "статус" not in text_lower:
                if not st.get("current_spreadsheet"):
                    send_vk_message(vk, user_id, "⚠️ Выберите направление.")
                    continue
                groups = get_groups_list(user_id)
                send_vk_message(vk, user_id, "Выберите группу:", get_groups_keyboard(groups))
                continue

            if "колонк" in text_lower and "дат" in text_lower:
                hdr = header_row(user_id)
                opts = [(c, lab) for c, lab, _, _ in parse_week_columns(hdr, _tz_now().date())]
                if not opts:
                    opts = [(i, h) for i, h in enumerate(hdr) if h and re.search(r"\d", h)]
                if not opts:
                    send_vk_message(vk, user_id, "❌ Колонки не найдены.")
                    continue
                st["action"] = "pick_week_col"
                st["options"] = opts
                lines = "\n".join([f"{i+1}. {lab}" for i, (_, lab) in enumerate(opts[:12])])
                send_vk_message(vk, user_id, f"Выберите колонку:\n{lines}", get_week_choice_keyboard(opts))
                continue

            if "студент" in text_lower:
                if not st.get("current_group"):
                    send_vk_message(vk, user_id, "⚠️ Выберите группу.")
                    continue
                s_map = get_students_map(user_id, st.get("current_group"))
                students = [(i + 1, fio) for i, (_, fio) in enumerate(s_map)]
                st.update({"action": "get_student", "students": students, "page": 0})
                send_vk_message(vk, user_id, "Выберите студента:", get_students_keyboard(students, 0))
                continue

            if "замечан" in text_lower:
                if not st.get("current_group"):
                    send_vk_message(vk, user_id, "⚠️ Выберите группу.")
                    continue
                s_map = get_students_map(user_id, st.get("current_group"))
                students = [(i + 1, fio) for i, (_, fio) in enumerate(s_map)]
                st.update({"action": "write_note", "students": students, "page": 0})
                send_vk_message(vk, user_id, "Выберите студента:", get_students_keyboard(students, 0))
                continue

            if "статус" in text_lower and "уч" in text_lower:
                if not st.get("current_group"):
                    send_vk_message(vk, user_id, "⚠️ Выберите группу.")
                    continue
                s_map = get_students_map(user_id, st.get("current_group"))
                students = [(i + 1, fio) for i, (_, fio) in enumerate(s_map)]
                st.update({"action": "pick_student_status", "students": students, "page": 0})
                send_vk_message(vk, user_id, "Выберите студента:", get_students_keyboard(students, 0))
                continue

            if "помощ" in text_lower:
                send_vk_message(vk, user_id, "Бот для работы с таблицами CNC Office.", get_main_keyboard())
                continue

            chosen_sheet = _resolve_sheet_click(text)
            if chosen_sheet:
                st.update({"current_spreadsheet": chosen_sheet, "current_group": None})
                user_note_col.pop(user_id, None)
                send_vk_message(vk, user_id, f"✅ Направление: {chosen_sheet}", get_main_keyboard())
                continue

            if st.get("current_spreadsheet"):
                try:
                    groups = get_groups_list(user_id)
                except Exception:
                    groups = []
                if text in groups:
                    st["current_group"] = text
                    user_note_col.pop(user_id, None)
                    send_vk_message(vk, user_id, f"✅ Группа: {text}", get_main_keyboard())
                    continue

            send_vk_message(vk, user_id, "⚠️ Неизвестная команда. Используйте кнопки.", get_main_keyboard())
        except Exception as e:
            print("❌ Error:", e)
            try:
                if 'vk' in locals() and 'user_id' in locals():
                    send_vk_message(vk, user_id, f"⚠️ Ошибка обработки: {e}")
            except Exception:
                pass

if __name__ == "__main__":
    main()
