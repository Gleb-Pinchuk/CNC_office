from bot_api.remark_utils import parse_input_date, set_remark_for_date


def test_parse_input_date():
    assert parse_input_date("18.04.2026").isoformat() == "2026-04-18"
    assert parse_input_date("2026-04-18").isoformat() == "2026-04-18"


def test_set_remark_for_date_replaces_same_day():
    d = parse_input_date("10.01.2025")
    assert d
    cell = "09.01.2025: старое\n10.01.2025: было"
    out = set_remark_for_date(cell, d, "новое")
    assert "10.01.2025: новое" in out
    assert "09.01.2025: старое" in out


def test_set_remark_no_text_uses_phrase():
    d = parse_input_date("01.02.2025")
    assert d
    out = set_remark_for_date("", d, None, no_remarks_phrase="замечаний нет")
    assert out == "01.02.2025: замечаний нет"
