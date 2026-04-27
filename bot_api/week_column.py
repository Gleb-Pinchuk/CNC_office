"""Определение колонки замечаний по дате недели из заголовка листа."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

DATE_TOKEN = re.compile(r"(\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})")
SHORT_DATE_RANGE = re.compile(
    r"(?<!\d)(\d{1,2})[.](\d{1,2})\s*[-–—]\s*(\d{1,2})[.](\d{1,2})(?![.\d])"
)
SHORT_DATE_TOKEN = re.compile(r"(?<!\d)(\d{1,2})[.](\d{1,2})(?![.\d])")


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


def _parse_short_date(day: str, month: str, target_date: date) -> Optional[date]:
    try:
        return date(target_date.year, int(month), int(day))
    except ValueError:
        return None


def parse_date_range_from_header_cell(value, target_date: date) -> Optional[tuple[date, date]]:
    """Возвращает диапазон дат из заголовка, включая форматы вроде 20.04-26.04."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    short_range = SHORT_DATE_RANGE.search(raw)
    if short_range:
        start = _parse_short_date(short_range.group(1), short_range.group(2), target_date)
        end = _parse_short_date(short_range.group(3), short_range.group(4), target_date)
        if start and end:
            if end < start:
                end = date(end.year + 1, end.month, end.day)
            return start, end

    full_dates = []
    for token in DATE_TOKEN.findall(raw):
        parsed = _parse_date_token(token)
        if parsed:
            full_dates.append(parsed)
    if len(full_dates) >= 2:
        start, end = full_dates[0], full_dates[-1]
        return (start, end) if start <= end else (end, start)
    if len(full_dates) == 1:
        return full_dates[0], full_dates[0]

    short_dates = [
        _parse_short_date(day, month, target_date)
        for day, month in SHORT_DATE_TOKEN.findall(raw)
    ]
    short_dates = [d for d in short_dates if d]
    if not short_dates:
        return None
    start, end = short_dates[0], short_dates[-1]
    # Диапазон может пересекать Новый год: 29.12-04.01.
    if end < start:
        end = date(end.year + 1, end.month, end.day)
    return start, end


def pick_week_col_by_date(sheet_data: list, target_date: date) -> Optional[int]:
    """
    Возвращает индекс колонки с датой из заголовка:
    1) сначала колонка, диапазон которой содержит target_date;
    2) затем колонка из той же ISO-недели, что target_date;
    3) для дат после последнего диапазона - последняя датированная колонка.
    """
    if not sheet_data or not isinstance(sheet_data[0], list):
        return None
    header = sheet_data[0]
    candidates = []
    for idx, val in enumerate(header):
        rng = parse_date_range_from_header_cell(val, target_date)
        if rng:
            candidates.append((idx, rng[0], rng[1]))
    if not candidates:
        return None

    containing = [
        (idx, start, end) for idx, start, end in candidates if start <= target_date <= end
    ]
    if containing:
        containing.sort(key=lambda x: (x[2] - x[1]).days)
        return containing[0][0]

    target_iso = target_date.isocalendar()[:2]  # (year, week)
    same_week = [
        (idx, start, end)
        for idx, start, end in candidates
        if start.isocalendar()[:2] == target_iso or end.isocalendar()[:2] == target_iso
    ]
    if same_week:
        same_week.sort(key=lambda x: min(abs((x[1] - target_date).days), abs((x[2] - target_date).days)))
        return same_week[0][0]

    candidates.sort(key=lambda x: x[1])
    if target_date > candidates[-1][2]:
        return candidates[-1][0]
    if target_date < candidates[0][1]:
        return candidates[0][0]

    candidates.sort(key=lambda x: min(abs((x[1] - target_date).days), abs((x[2] - target_date).days)))
    return candidates[0][0]

