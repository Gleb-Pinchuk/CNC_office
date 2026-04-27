"""Поиск строк студентов в листе custom_sheet (данные Handsontable)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def normalize_cell(row: list, idx: int) -> str:
    if idx < 0 or idx >= len(row):
        return ""
    v = row[idx]
    return "" if v is None else str(v).strip()


def iter_data_rows(sheet_data: List[List[Any]], header_rows: int = 1):
    """Индекс строки в data (0-based), как в set_cell."""
    for i in range(header_rows, len(sheet_data)):
        yield i, sheet_data[i]


def list_groups(
    sheet_data: List[List[Any]],
    group_col: int,
    header_rows: int = 1,
) -> List[str]:
    seen = set()
    out: List[str] = []
    for _, row in iter_data_rows(sheet_data, header_rows):
        g = normalize_cell(row, group_col).lower()
        if not g:
            continue
        if g not in seen:
            seen.add(g)
            out.append(normalize_cell(row, group_col))
    return sorted(out, key=lambda x: x.lower())


def search_students(
    sheet_data: List[List[Any]],
    *,
    fio_col: int,
    group_col: int,
    status_col: int,
    group_filter: Optional[str] = None,
    query: Optional[str] = None,
    skip_dismissed: bool = True,
    header_rows: int = 1,
) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    gf = (group_filter or "").strip().lower()
    results: List[Dict[str, Any]] = []
    for row_idx, row in iter_data_rows(sheet_data, header_rows):
        if not row or all(not str(c).strip() for c in row if c is not None):
            continue
        fio = normalize_cell(row, fio_col)
        grp = normalize_cell(row, group_col)
        status = normalize_cell(row, status_col)
        if skip_dismissed and status and "отчислен" in status.lower():
            continue
        if gf and grp.lower() != gf and gf not in grp.lower():
            continue
        if q and q not in fio.lower():
            continue
        if fio:
            results.append(
                {
                    "row_index": row_idx,
                    "fio": fio,
                    "group": grp,
                    "status": status,
                }
            )
    return results


def find_one_student_row(
    sheet_data: List[List[Any]],
    student_fio: str,
    *,
    fio_col: int,
    group_col: int,
    status_col: int,
    group_filter: Optional[str] = None,
    skip_dismissed: bool = True,
    header_rows: int = 1,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Поиск по подстроке ФИО (как в старом боте).
    Возвращает (первая_строка, все_совпадения).
    """
    q = student_fio.strip().lower()
    if not q:
        return None, []
    matches = search_students(
        sheet_data,
        fio_col=fio_col,
        group_col=group_col,
        status_col=status_col,
        group_filter=group_filter,
        query=q,
        skip_dismissed=skip_dismissed,
        header_rows=header_rows,
    )
    if not matches:
        loose = search_students(
            sheet_data,
            fio_col=fio_col,
            group_col=group_col,
            status_col=status_col,
            group_filter=group_filter,
            query=None,
            skip_dismissed=skip_dismissed,
            header_rows=header_rows,
        )
        matches = [
            m
            for m in loose
            if q in m["fio"].lower() or m["fio"].lower() in q
        ]
    if not matches:
        return None, []
    return matches[0], matches
