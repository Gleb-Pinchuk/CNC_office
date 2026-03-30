"""Разбор custom_sheet (v1/v2) для чтения/записи ячеек из бота."""
from typing import Optional, Tuple


def get_workbook_sheets(content: dict) -> Tuple[list, int]:
    """
    Возвращает (sheets: list, active_index: int).
    content — обычно models.SectionTable.content или Document.content.
    """
    if not isinstance(content, dict):
        return [], 0
    cs = content.get('custom_sheet')
    if not isinstance(cs, dict):
        return [], 0
    sheets = cs.get('sheets')
    if isinstance(sheets, list) and sheets:
        ai = cs.get('activeSheetIndex') or 0
        ai = max(0, min(int(ai), len(sheets) - 1))
        return sheets, ai
    if isinstance(cs.get('data'), list):
        return [cs], 0
    return [], 0


def find_sheet_by_name(sheets: list, sheet_name: Optional[str]):
    if not sheets:
        return None
    if not sheet_name or not str(sheet_name).strip():
        return sheets[0]
    target = str(sheet_name).strip().lower()
    for sh in sheets:
        name = str(sh.get('name') or '').strip().lower()
        if name == target:
            return sh
    return None


def _ensure_cell(data: list, row: int, col: int):
    while len(data) <= row:
        width = max((len(r) for r in data if isinstance(r, list)), default=col + 1)
        width = max(width, col + 1, 10)
        data.append([''] * width)
    r = data[row]
    if not isinstance(r, list):
        r = list(r) if r else []
        data[row] = r
    while len(r) <= col:
        r.append('')


def set_cell_value(content: dict, sheet_name: Optional[str], row: int, col: int, value: str) -> dict:
    """
    Пишет в content.custom_sheet, возвращает обновлённый content (тот же dict).
    row, col — 0-based (0 = первая строка таблицы, обычно заголовки).
    """
    if not isinstance(content, dict):
        content = {}
    if not isinstance(content.get('custom_sheet'), dict):
        content['custom_sheet'] = {}
    cs = content['custom_sheet']
    sheets, _ = get_workbook_sheets(content)
    if not sheets:
        new_sheet = {
            'name': 'Лист1',
            'rows': max(20, row + 1),
            'cols': max(10, col + 1),
            'data': [],
            'styles': {},
        }
        cs['version'] = 2
        cs['activeSheetIndex'] = 0
        cs['sheets'] = [new_sheet]
        for k in ('data', 'rows', 'cols', 'styles', 'colWidths', 'rowHeights', 'columnFilters'):
            cs.pop(k, None)
        sheets = cs['sheets']
    sh = find_sheet_by_name(sheets, sheet_name)
    if not sh:
        sh = sheets[0]
    data = sh.get('data')
    if not isinstance(data, list):
        data = []
        sh['data'] = data
    _ensure_cell(data, row, col)
    data[row][col] = value if value is not None else ''
    return content
