"""Слияние текста замечаний по датам (строки вида ДД.ММ.ГГГГ: ...)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional, Tuple

LINE_PREFIX = re.compile(
    r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*:\s*",
    re.UNICODE,
)


def parse_input_date(s: str) -> Optional[date]:
    """Принимает ДД.ММ.ГГГГ, ДД.ММ.ГГ или ГГГГ-ММ-ДД."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _date_key(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _line_date_key(line: str) -> Optional[str]:
    m = LINE_PREFIX.match(line)
    if not m:
        return None
    d, mth, y = int(m.group(1)), int(m.group(2)), m.group(3)
    if len(y) == 2:
        y = int(y)
        y = 2000 + y if y < 70 else 1900 + y
    else:
        y = int(y)
    try:
        return _date_key(date(y, mth, d))
    except ValueError:
        return None


def split_remark_lines(text: str) -> List[str]:
    if not text or not str(text).strip():
        return []
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


def set_remark_for_date(
    current_cell: str,
    target_date: date,
    remark_text: Optional[str],
    *,
    no_remarks_phrase: str = "замечаний нет",
) -> str:
    """
    Для даты target_date заменяет или добавляет строку «ДД.ММ.ГГГГ: текст».
    remark_text None или пустая строка — записывается фраза «замечаний нет».
    """
    key = _date_key(target_date)
    if remark_text and str(remark_text).strip():
        new_line = f"{key}: {str(remark_text).strip()}"
    else:
        new_line = f"{key}: {no_remarks_phrase}"

    lines = split_remark_lines(current_cell)
    kept: List[str] = []
    replaced = False
    for ln in lines:
        dk = _line_date_key(ln)
        if dk == key:
            kept.append(new_line)
            replaced = True
        else:
            kept.append(ln)
    if not replaced:
        kept.append(new_line)
    return "\n".join(kept)
