from bot_api.sheet_utils import delete_sheet_row, get_workbook_sheets, insert_sheet_row
from bot_api.trash import find_insert_row_in_group, surname_key


def test_surname_key_uses_first_word():
    assert surname_key("Иванов Иван") == "иванов"
    assert surname_key("  Петров  ") == "петров"


def test_find_insert_row_in_group_alphabetical():
    data = [
        ["grp", "fio"],
        ["5", "Алексеев А"],
        ["5", "Сидоров С"],
        ["6", "Яковлев Я"],
        ["5", "Яшин Я"],
    ]
    # Орлов between Алексеев and Сидоров
    assert (
        find_insert_row_in_group(
            data, fio="Орлов О", group="5", fio_col=1, group_col=0
        )
        == 2
    )
    # Before first in group
    assert (
        find_insert_row_in_group(
            data, fio="Ааа А", group="5", fio_col=1, group_col=0
        )
        == 1
    )
    # After last in group (after Яшин at index 4)
    assert (
        find_insert_row_in_group(
            data, fio="Яяя Я", group="5", fio_col=1, group_col=0
        )
        == 5
    )


def test_delete_and_insert_sheet_row():
    content = {
        "custom_sheet": {
            "version": 2,
            "sheets": [
                {
                    "name": "ЧПУ",
                    "data": [
                        ["g", "fio"],
                        ["5", "A"],
                        ["5", "C"],
                    ],
                    "rows": 3,
                }
            ],
        }
    }
    delete_sheet_row(content, "ЧПУ", 1)
    sheets, _ = get_workbook_sheets(content)
    assert sheets[0]["data"] == [["g", "fio"], ["5", "C"]]
    insert_sheet_row(content, "ЧПУ", 1, ["5", "B"])
    sheets, _ = get_workbook_sheets(content)
    assert sheets[0]["data"][1] == ["5", "B"]
    assert sheets[0]["data"][2] == ["5", "C"]
