# -*- coding: utf-8 -*-
"""Собрать xlsx для CNC Office / VK-бота из студенты_ЧПУ_2026 + шаблон рейнджеры2025."""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SRC_DIR = Path(r"c:\Users\ghlie\OneDrive\Рабочий стол\киерстуденты")
STUDENTS = SRC_DIR / "студенты_ЧПУ_2026.xlsx"
TEMPLATE = SRC_DIR / "рейнджеры2025.xlsx"
OUT_DIR = Path(r"C:\temp\CNC_office\data")
OUT_FILE = OUT_DIR / "Рейнджеры_производственная_группа.xlsx"
OUT_COPY = SRC_DIR / "Рейнджеры_производственная_группа.xlsx"

# Формат колонок бота (.env.example):
# FIO=2, GROUP=1, STATUS=12, SOCIAL=4,5,6 (Телеграм, Вконтакте, ТикТок)
HEADER = [
    "№",
    "Группа",
    "ФИО",
    "Номер телефона",
    "Телеграм",
    "Вконтакте",
    "ТикТок",
    "Ответственный",
    "01.09-06.09",
    "07.09-13.09",
    "14.09-20.09",
    "21.09-27.09",
    "Состояние",
]


def _cell(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if s.lower() in {"nan", "none"}:
        return ""
    return s


def build_chpu_rows(df: pd.DataFrame):
    rows = [HEADER]
    for i, r in enumerate(df.itertuples(index=False), start=1):
        # students cols: № Группа ФИО phone TG IG VK TT Resp weeks... Status Consent
        d = r._asdict() if hasattr(r, "_asdict") else None
        # use column names via iloc by position from dataframe
        pass
    # safer: use column access
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        rows.append(
            [
                i,
                _cell(r.get("Группа")),
                _cell(r.get("ФИО")),
                _cell(r.get("Номер телефона")),
                _cell(r.get("Телеграм")),
                _cell(r.get("Вконтакте")),
                _cell(r.get("ТикТок")),
                _cell(r.get("Ответственный")),
                _cell(r.get("01.09-06.09")),
                _cell(r.get("07.09-13.09")),
                _cell(r.get("14.09-20.09")),
                _cell(r.get("21.09-27.09")),
                _cell(r.get("Состояние")) or "учится",
            ]
        )
    return rows


def style_sheet(ws):
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="B4B4B4")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    widths = [6, 14, 36, 18, 22, 28, 28, 30, 14, 14, 14, 14, 12]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def copy_sheet_values(src_ws, dst_ws):
    first = True
    for row in src_ws.iter_rows(values_only=True):
        vals = ["" if v is None else v for v in row]
        if first:
            # шаблон МИКРО иногда без «№» в A1
            if not str(vals[0]).strip() or str(vals[0]).lower() == "nan":
                vals[0] = "№"
            if vals and str(vals[-1]).strip().lower() == "состояние":
                vals[-1] = "Состояние"
            first = False
        dst_ws.append(vals)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    students = pd.read_excel(STUDENTS)
    chpu_rows = build_chpu_rows(students)

    wb = Workbook()
    # ЧПУ first
    ws_chpu = wb.active
    ws_chpu.title = "ЧПУ"
    for row in chpu_rows:
        ws_chpu.append(row)
    style_sheet(ws_chpu)

    # keep other sheets from template
    tpl = load_workbook(TEMPLATE, data_only=True)
    for name in tpl.sheetnames:
        if name.strip().upper() == "ЧПУ":
            continue
        src = tpl[name]
        dst = wb.create_sheet(title=name[:31])
        copy_sheet_values(src, dst)
        # normalize first header cell
        if dst.max_row >= 1:
            style_sheet(dst)

    wb.save(OUT_FILE)
    wb.save(OUT_COPY)
    print(f"CHПУ rows: {len(chpu_rows) - 1}")
    print(f"Sheets: {wb.sheetnames}")
    print(f"Saved: {OUT_FILE}")
    print(f"Copy:  {OUT_COPY}")


if __name__ == "__main__":
    main()
