"""Разбор custom_sheet (v1/v2) для чтения/записи ячеек из бота."""

from typing import Optional, Tuple


def _normalize_sheet_name(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def get_workbook_sheets(content: dict) -> Tuple[list, int]:
    """
    Возвращает (sheets: list, active_index: int).
    content — обычно models.SectionTable.content или Document.content.

    Поддерживает несколько форматов:
      1) {"custom_sheet": {"version": 2, "sheets": [...], "activeSheetIndex": N}}
      2) {"custom_sheet": {"data": [...]}}  (один лист, старый v1)
      3) {"sheets": [...], "activeSheetIndex": N}  (без обёртки custom_sheet)
      4) {"data": [...]}  (один лист без обёртки)
    """
    if not isinstance(content, dict):
        return [], 0

    def _from_wrapper(cs: dict) -> Tuple[list, int]:
        sheets = cs.get("sheets")
        if isinstance(sheets, list) and sheets:
            ai = cs.get("activeSheetIndex") or 0
            try:
                ai = int(ai)
            except Exception:
                ai = 0
            ai = max(0, min(ai, len(sheets) - 1))
            return sheets, ai
        if isinstance(cs.get("data"), list):
            return [cs], 0
        return [], 0

    cs = content.get("custom_sheet")
    if isinstance(cs, dict):
        sheets, ai = _from_wrapper(cs)
        if sheets:
            return sheets, ai

    # Fallback: содержимое лежит прямо в корне
    sheets, ai = _from_wrapper(content)
    if sheets:
        return sheets, ai

    return [], 0


def sheet_display_names(sheets: list) -> list:
    """Имена листов для API; устойчиво к битым элементам в sheets."""
    names = []
    for i, sh in enumerate(sheets or []):
        if isinstance(sh, dict):
            names.append(str(sh.get("name") or f"Лист{i + 1}"))
        else:
            names.append(f"Лист{i + 1}")
    return names


def find_sheet_by_name(sheets: list, sheet_name: Optional[str]):
    if not sheets:
        return None
    if not sheet_name or not str(sheet_name).strip():
        return sheets[0]
    target_raw = str(sheet_name).strip().lower()
    target_norm = _normalize_sheet_name(sheet_name)

    # 1) strict case-insensitive match
    for sh in sheets:
        name = str(sh.get("name") or "").strip().lower()
        if name == target_raw:
            return sh

    # 2) normalized exact match (ignore spaces/punctuations/casing)
    for sh in sheets:
        name_norm = _normalize_sheet_name(sh.get("name") or "")
        if name_norm and name_norm == target_norm:
            return sh

    # 3) unique fuzzy contains match to survive minor renames in archives
    candidates = []
    for sh in sheets:
        name_norm = _normalize_sheet_name(sh.get("name") or "")
        if not name_norm:
            continue
        if target_norm in name_norm or name_norm in target_norm:
            candidates.append(sh)
    if len(candidates) == 1:
        return candidates[0]

    # 4) as a final fallback use the first sheet
    return sheets[0]


def _ensure_cell(data: list, row: int, col: int):
    while len(data) <= row:
        width = max((len(r) for r in data if isinstance(r, list)), default=col + 1)
        width = max(width, col + 1, 10)
        data.append([""] * width)
    r = data[row]
    if not isinstance(r, list):
        r = list(r) if r else []
        data[row] = r
    while len(r) <= col:
        r.append("")


def set_cell_value(
    content: dict, sheet_name: Optional[str], row: int, col: int, value: str
) -> dict:
    """
    Пишет в content.custom_sheet, возвращает обновлённый content (тот же dict).
    row, col — 0-based (0 = первая строка таблицы, обычно заголовки).
    """
    if not isinstance(content, dict):
        content = {}
    if not isinstance(content.get("custom_sheet"), dict):
        content["custom_sheet"] = {}
    cs = content["custom_sheet"]
    sheets, _ = get_workbook_sheets(content)
    if not sheets:
        new_sheet = {
            "name": "Лист1",
            "rows": max(20, row + 1),
            "cols": max(10, col + 1),
            "data": [],
            "styles": {},
        }
        cs["version"] = 2
        cs["activeSheetIndex"] = 0
        cs["sheets"] = [new_sheet]
        for k in (
            "data",
            "rows",
            "cols",
            "styles",
            "colWidths",
            "rowHeights",
            "columnFilters",
        ):
            cs.pop(k, None)
        sheets = cs["sheets"]
    sh = find_sheet_by_name(sheets, sheet_name)
    if not sh:
        sh = sheets[0]
    data = sh.get("data")
    if not isinstance(data, list):
        data = []
        sh["data"] = data
    _ensure_cell(data, row, col)
    data[row][col] = value if value is not None else ""
    return content
