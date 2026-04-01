import pytest

pytest.importorskip("openpyxl")

from api.xlsx_export import export_custom_sheet_to_xlsx_bytes


@pytest.mark.django_db
class TestXlsxExport:
    def test_export_v1_single_sheet(self):
        content = {
            "custom_sheet": {
                "name": "Лист1",
                "data": [["Hello"]],
                "styles": {
                    "0:0": {
                        "bold": True,
                        "textColor": "#ff0000",
                        "fillColor": "#00ff00",
                        "align": "center",
                    }
                },
            }
        }
        b = export_custom_sheet_to_xlsx_bytes("T", content)
        assert isinstance(b, (bytes, bytearray))
        assert len(b) > 200

    def test_export_v2_multi_sheet(self):
        content = {
            "custom_sheet": {
                "version": 2,
                "activeSheetIndex": 0,
                "sheets": [
                    {"name": "S1", "data": [["A"]]},
                    {"name": "S2", "data": [["B"]]},
                ],
            }
        }
        b = export_custom_sheet_to_xlsx_bytes("T", content)
        assert len(b) > 200
