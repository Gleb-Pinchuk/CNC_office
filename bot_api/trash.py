"""Корзина отчисленных студентов: позиция вставки и TTL."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, List, Optional

from django.utils import timezone

from bot_api.student_sheet import iter_data_rows, normalize_cell

TRASH_TTL_DAYS = 30


def trash_expires_at(*, deleted_at=None):
    base = deleted_at or timezone.now()
    return base + timedelta(days=TRASH_TTL_DAYS)


def surname_key(fio: str) -> str:
    parts = str(fio or "").strip().split()
    return (parts[0] if parts else str(fio or "")).casefold()


def find_insert_row_in_group(
    sheet_data: List[List[Any]],
    *,
    fio: str,
    group: str,
    fio_col: int,
    group_col: int,
    header_rows: int = 1,
) -> int:
    """
    Индекс строки для вставки по алфавиту фамилии внутри той же группы.
    Если группы нет — в конец листа.
    """
    key = surname_key(fio)
    group_l = (group or "").strip().lower()
    insert_at: Optional[int] = None
    last_in_group: Optional[int] = None
    for row_idx, row in iter_data_rows(sheet_data, header_rows):
        if not isinstance(row, list):
            continue
        grp = normalize_cell(row, group_col)
        if not group_l:
            continue
        if grp.lower() != group_l and group_l not in grp.lower():
            continue
        last_in_group = row_idx
        other_fio = normalize_cell(row, fio_col)
        if surname_key(other_fio) > key:
            insert_at = row_idx
            break
    if insert_at is not None:
        return insert_at
    if last_in_group is not None:
        return last_in_group + 1
    return max(header_rows, len(sheet_data))
