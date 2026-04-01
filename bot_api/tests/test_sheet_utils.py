import pytest

from bot_api.sheet_utils import get_workbook_sheets, set_cell_value


@pytest.mark.django_db
class TestSheetUtils:
    def test_get_workbook_sheets_v1(self):
        content = {"custom_sheet": {"data": [["A"]], "name": "Лист1"}}
        sheets, active = get_workbook_sheets(content)
        assert active == 0
        assert len(sheets) == 1
        assert sheets[0]["data"][0][0] == "A"

    def test_get_workbook_sheets_v2(self):
        content = {
            "custom_sheet": {
                "version": 2,
                "activeSheetIndex": 0,
                "sheets": [{"name": "S1", "data": [["A"]]}],
            }
        }
        sheets, active = get_workbook_sheets(content)
        assert active == 0
        assert sheets[0]["name"] == "S1"

    def test_set_cell_value_expands_grid(self):
        content = {}
        set_cell_value(content, sheet_name="S1", row=5, col=7, value="X")
        sheets, _ = get_workbook_sheets(content)
        assert len(sheets) == 1
        data = sheets[0]["data"]
        assert data[5][7] == "X"
