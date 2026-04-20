"""Определение колонки замечаний по дате недели из заголовка листа."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

DATE_TOKEN = re.compile(r"(\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})")


def _parse_date_token(token: str) -> Optional[date]:
    token = token.strip()
    if not token:
        return None
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def parse_date_from_header_cell(value) -> Optional[date]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    direct = _parse_date_token(raw)
    if direct:
        return direct
    m = DATE_TOKEN.search(raw)
    if not m:
        return None
    return _parse_date_token(m.group(1))


def pick_week_col_by_date(sheet_data: list, target_date: date) -> Optional[int]:
    """
    Возвращает индекс колонки с датой из заголовка:
    1) сначала колонка из той же ISO-недели, что target_date
    2) иначе ближайшая по абсолютной разнице дней.
    """
    if not sheet_data or not isinstance(sheet_data[0], list):
        return None
    header = sheet_data[0]
    candidates = []
    for idx, val in enumerate(header):
        d = parse_date_from_header_cell(val)
        if d:
            candidates.append((idx, d))
    if not candidates:
        return None

    target_iso = target_date.isocalendar()[:2]  # (year, week)
    same_week = [(idx, d) for idx, d in candidates if d.isocalendar()[:2] == target_iso]
    pool = same_week or candidates
    pool.sort(key=lambda x: abs((x[1] - target_date).days))
    return pool[0][0]

