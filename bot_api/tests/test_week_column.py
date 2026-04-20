from datetime import date

from bot_api.week_column import parse_date_from_header_cell, pick_week_col_by_date


def test_parse_date_from_header_cell():
    assert parse_date_from_header_cell("15.04.2026").isoformat() == "2026-04-15"
    assert parse_date_from_header_cell("Неделя 22-04-26").isoformat() == "2026-04-22"


def test_pick_week_col_by_date_prefers_same_iso_week():
    data = [
        ["ФИО", "Группа", "15.04.2026", "22.04.2026"],
        ["Иванов", "Г1", "", ""],
    ]
    assert pick_week_col_by_date(data, date(2026, 4, 21)) == 3
    assert pick_week_col_by_date(data, date(2026, 4, 14)) == 2

