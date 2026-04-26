from datetime import date

from bot_api.week_column import (
    parse_date_from_header_cell,
    parse_date_range_from_header_cell,
    pick_week_col_by_date,
)


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


def test_parse_date_range_from_header_cell_without_year():
    assert parse_date_range_from_header_cell("20.04-26.04", date(2026, 4, 26)) == (
        date(2026, 4, 20),
        date(2026, 4, 26),
    )


def test_pick_week_col_by_date_uses_last_available_week_for_later_date():
    data = [
        ["ФИО", "Группа", "Статус", "13.04-19.04", "20.04-26.04", "Статус учебы"],
        ["Иванов", "Г1", "учится", "", "", "учится"],
    ]

    assert pick_week_col_by_date(data, date(2026, 4, 26)) == 4
    assert pick_week_col_by_date(data, date(2026, 4, 27)) == 4

