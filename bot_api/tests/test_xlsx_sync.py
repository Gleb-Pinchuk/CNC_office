"""Юнит-тесты без БД: round-trip .xlsx ↔ custom_sheet."""

from bot_api.xlsx_sync import (
    build_custom_sheet_v2,
    content_to_excel_bytes,
    excel_bytes_to_content,
    merge_content_into_excel_bytes,
)


def test_xlsx_roundtrip_basic():
    content = build_custom_sheet_v2(
        [{"name": "Лист1", "data": [["ФИО", "Группа"], ["Иванов", "ИВТ-1"]]}]
    )
    raw = content_to_excel_bytes(content)
    back = excel_bytes_to_content(raw)
    sh = back["custom_sheet"]["sheets"][0]["data"]
    assert sh[0][0] == "ФИО"
    assert sh[1][0] == "Иванов"


def test_merge_preserves_unmanaged_sheets():
    base = build_custom_sheet_v2(
        [
            {"name": "ЧПУ", "data": [["ФИО", "Замечания"], ["Иванов", ""]]},
            {"name": "Служебный", "data": [["A1"]]},
        ]
    )
    base_raw = content_to_excel_bytes(base)

    # Меняем только первый лист, второй должен сохраниться как есть.
    changed = build_custom_sheet_v2(
        [{"name": "ЧПУ", "data": [["ФИО", "Замечания"], ["Иванов", "опоздал"]]}]
    )
    merged_raw = merge_content_into_excel_bytes(base_raw, changed)
    merged = excel_bytes_to_content(merged_raw)
    sheets = {s["name"]: s["data"] for s in merged["custom_sheet"]["sheets"]}

    assert sheets["ЧПУ"][1][1] == "опоздал"
    assert sheets["Служебный"][0][0] == "A1"
