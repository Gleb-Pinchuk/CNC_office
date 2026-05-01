from datetime import date

import pytest

from bot_api.monthly_rollover import (
    apply_month_headers,
    content_month,
    rollover_table_if_needed,
    week_headers_for_month,
)
from sections.models import SectionTable, SectionTableMonthlyArchive


def test_apply_month_headers_updates_headers_and_clears_week_cells():
    content = {
        "custom_sheet": {
            "version": 2,
            "activeSheetIndex": 0,
            "sheets": [
                {
                    "name": "BIM",
                    "data": [
                        [
                            "",
                            "Группа",
                            "ФИО",
                            "Номер телефона",
                            "Телеграм",
                            "Вконтакте",
                            "ТикТок",
                            "Ответственный",
                            "01.04-05.04",
                            "06.04-12.04",
                            "13.04-19.04",
                            "20.04-26.04",
                            "Состояние",
                        ],
                        ["", "BIM-25-1", "Иванов Иван", "", "", "", "", "", "нет", "", "x", "y", "учится"],
                    ],
                }
            ],
        }
    }

    changed = apply_month_headers(content, 2026, 5, fallback_col=11)

    assert changed is True
    row0 = content["custom_sheet"]["sheets"][0]["data"][0]
    assert row0[8:12] == week_headers_for_month(2026, 5)
    row1 = content["custom_sheet"]["sheets"][0]["data"][1]
    assert row1[8:12] == ["", "", "", ""]
    assert row1[12] == "учится"


def test_content_month_detects_previous_year_december_from_january():
    content = {
        "custom_sheet": {
            "sheets": [
                {"name": "BIM", "data": [["09.12-15.12", "16.12-22.12"], ["", ""]]}
            ]
        }
    }

    assert content_month(content, ref_date=date(2027, 1, 1)) == (2026, 12)


@pytest.mark.django_db
def test_rollover_table_archives_previous_month_and_keeps_three_archives():
    from django.contrib.auth import get_user_model

    owner = get_user_model().objects.create_user(username="bot_owner", password="pass")
    table = SectionTable.objects.create(
        owner=owner,
        title="Rangers",
        section_type="rangers",
        content={
            "custom_sheet": {
                "version": 2,
                "activeSheetIndex": 0,
                "sheets": [
                    {
                        "name": "BIM",
                        "data": [
                            ["Группа", "ФИО", "01.04-05.04", "06.04-12.04", "13.04-19.04", "20.04-26.04"],
                            ["BIM-25-1", "Иванов Иван", "", "", "замечание", ""],
                        ],
                    }
                ],
            }
        },
    )

    result = rollover_table_if_needed(table, today=date(2026, 5, 1), fallback_col=5)

    assert result["changed"] is True
    assert SectionTableMonthlyArchive.objects.filter(table=table, year=2026, month=4).exists()
    table.refresh_from_db()
    data = table.content["custom_sheet"]["sheets"][0]["data"]
    assert data[0][2:6] == week_headers_for_month(2026, 5)
    assert data[1][2:6] == ["", "", "", ""]
    assert table.needs_nextcloud_push is True


@pytest.mark.django_db
def test_rollover_repairs_current_month_with_stale_remarks_and_no_archive():
    from django.contrib.auth import get_user_model

    owner = get_user_model().objects.create_user(username="bot_owner_2", password="pass")
    table = SectionTable.objects.create(
        owner=owner,
        title="Rangers current month",
        section_type="rangers",
        content={
            "custom_sheet": {
                "version": 2,
                "activeSheetIndex": 0,
                "sheets": [
                    {
                        "name": "BIM",
                        "data": [
                            ["Группа", "ФИО", "01.05-04.05", "05.05-11.05", "12.05-18.05", "19.05-25.05"],
                            ["BIM-25-1", "Иванов Иван", "старое", "", "старое", ""],
                        ],
                    }
                ],
            }
        },
    )

    result = rollover_table_if_needed(table, today=date(2026, 5, 20), fallback_col=5)

    assert result["changed"] is True
    assert result["reason"] == "current_month_repaired"
    assert SectionTableMonthlyArchive.objects.filter(table=table, year=2026, month=4).exists()
    table.refresh_from_db()
    data = table.content["custom_sheet"]["sheets"][0]["data"]
    assert data[1][2:6] == ["", "", "", ""]
    assert table.needs_nextcloud_push is True
