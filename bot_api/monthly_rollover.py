from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bot_api.sheet_utils import get_workbook_sheets
from bot_api.week_column import (
    build_month_week_ranges,
    format_week_range_header,
    parse_date_range_from_header_cell,
)
from sections.models import SectionTable, SectionTableMonthlyArchive


def previous_month(value: date) -> tuple[int, int]:
    first = value.replace(day=1)
    prev = first - timedelta(days=1)
    return prev.year, prev.month


def week_headers_for_month(year: int, month: int) -> list[str]:
    return [
        format_week_range_header(start, end)
        for start, end in build_month_week_ranges(year, month)
    ]


def find_week_columns(sheet_data: list, fallback_col: int) -> list[int]:
    if not sheet_data or not isinstance(sheet_data[0], list):
        return _fallback_week_columns(fallback_col)

    header = sheet_data[0]
    found = []
    today = timezone.localdate()
    for idx, value in enumerate(header):
        if parse_date_range_from_header_cell(value, today):
            found.append(idx)
    if found:
        return found[:4]
    return _fallback_week_columns(fallback_col)


def detect_sheet_month(sheet_data: list, ref_date: Optional[date] = None) -> Optional[tuple[int, int]]:
    if not sheet_data or not isinstance(sheet_data[0], list):
        return None
    ref = ref_date or timezone.localdate()
    months: dict[tuple[int, int], int] = {}
    for value in sheet_data[0]:
        rng = parse_date_range_from_header_cell(value, ref)
        if not rng:
            continue
        start = rng[0]
        year = ref.year
        if ref.month == 1 and start.month == 12:
            year -= 1
        months[(year, start.month)] = months.get((year, start.month), 0) + 1
    if not months:
        return None
    return sorted(months.items(), key=lambda item: item[1], reverse=True)[0][0]


def content_month(content: dict, ref_date: Optional[date] = None) -> Optional[tuple[int, int]]:
    sheets, _ = get_workbook_sheets(content if isinstance(content, dict) else {})
    for sheet in sheets:
        data = sheet.get("data") if isinstance(sheet.get("data"), list) else []
        detected = detect_sheet_month(data, ref_date=ref_date)
        if detected:
            return detected
    return None


def apply_month_headers(content: dict, year: int, month: int, fallback_col: int) -> bool:
    sheets, _ = get_workbook_sheets(content if isinstance(content, dict) else {})
    headers = week_headers_for_month(year, month)
    if len(headers) != 4:
        return False

    changed = False
    for sheet in sheets:
        data = sheet.get("data") if isinstance(sheet.get("data"), list) else []
        if not data:
            continue
        if not isinstance(data[0], list):
            continue

        cols = find_week_columns(data, fallback_col)
        header = data[0]
        for col, label in zip(cols, headers):
            _ensure_row_width(header, col)
            if header[col] != label:
                header[col] = label
                changed = True

        for row in data[1:]:
            if not isinstance(row, list):
                continue
            for col in cols:
                _ensure_row_width(row, col)
                if row[col] not in ("", None):
                    row[col] = ""
                    changed = True
    return changed


def rollover_table_if_needed(
    table: SectionTable,
    *,
    today: Optional[date] = None,
    fallback_col: Optional[int] = None,
    retention_months: int = 3,
) -> dict:
    current = today or timezone.localdate()
    fallback = int(
        fallback_col
        if fallback_col is not None
        else getattr(settings, "BOT_SHEET_REMARK_COL", 11)
    )

    with transaction.atomic():
        locked = SectionTable.objects.select_for_update().get(pk=table.pk)
        content = locked.content if isinstance(locked.content, dict) else {}
        detected = content_month(content, ref_date=current)
        if detected == (current.year, current.month):
            prev_year, prev_month = previous_month(current)
            has_prev_archive = locked.monthly_archives.filter(
                year=prev_year, month=prev_month
            ).exists()
            if not has_prev_archive:
                SectionTableMonthlyArchive.objects.update_or_create(
                    table=locked,
                    year=prev_year,
                    month=prev_month,
                    defaults={"content": deepcopy(content)},
                )
            new_content = deepcopy(content)
            changed = apply_month_headers(new_content, current.year, current.month, fallback)
            if changed:
                locked.content = new_content
                locked.needs_nextcloud_push = True
                locked.save(
                    update_fields=["content", "needs_nextcloud_push", "updated_at"]
                )
            _prune_archives(locked, retention_months)
            if changed:
                return {
                    "ok": True,
                    "changed": True,
                    "reason": "current_month_repaired",
                    "archive_year": prev_year,
                    "archive_month": prev_month,
                    "table_id": locked.pk,
                }
            if not has_prev_archive:
                return {
                    "ok": True,
                    "changed": False,
                    "reason": "current_month_archived",
                    "archive_year": prev_year,
                    "archive_month": prev_month,
                    "table_id": locked.pk,
                }
            return {"ok": True, "changed": False, "reason": "already_current"}

        archive_year, archive_month = detected or previous_month(current)
        SectionTableMonthlyArchive.objects.update_or_create(
            table=locked,
            year=archive_year,
            month=archive_month,
            defaults={"content": deepcopy(content)},
        )

        new_content = deepcopy(content)
        changed = apply_month_headers(new_content, current.year, current.month, fallback)
        if changed:
            locked.content = new_content
            locked.needs_nextcloud_push = True
            locked.save(update_fields=["content", "needs_nextcloud_push", "updated_at"])

        _prune_archives(locked, retention_months)
        return {
            "ok": True,
            "changed": changed,
            "archive_year": archive_year,
            "archive_month": archive_month,
            "table_id": locked.pk,
        }


def _fallback_week_columns(fallback_col: int) -> list[int]:
    end = max(3, int(fallback_col))
    return list(range(end - 3, end + 1))


def _ensure_row_width(row: list, col: int) -> None:
    while len(row) <= col:
        row.append("")


def _prune_archives(table: SectionTable, retention_months: int) -> None:
    keep_ids = list(
        table.monthly_archives.order_by("-year", "-month", "-created_at")
        .values_list("id", flat=True)[: max(0, retention_months)]
    )
    table.monthly_archives.exclude(id__in=keep_ids).delete()
