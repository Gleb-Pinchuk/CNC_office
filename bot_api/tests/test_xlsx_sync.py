"""Юнит-тесты без БД: round-trip .xlsx ↔ custom_sheet."""

from bot_api.xlsx_sync import (
    build_custom_sheet_v2,
    content_to_excel_bytes,
    excel_bytes_to_content,
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
