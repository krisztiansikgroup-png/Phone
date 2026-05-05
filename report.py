"""Generate monthly Excel pontaj (attendance sheet) for Romanian accounting."""
import calendar
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter

from holidays_ro import get_public_holidays, is_public_holiday
from models import STATUSES


_THIN = Side(style="thin")
_MEDIUM = Side(style="medium")
BORDER_ALL = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
BORDER_HEADER = Border(left=_MEDIUM, right=_MEDIUM, top=_MEDIUM, bottom=_MEDIUM)

_STATUS_COLORS = {
    "CO":  "FFF2CC",  # yellow
    "CM":  "FCE4D6",  # light orange
    "CFP": "DDEBF7",  # light blue
    "CIC": "E2EFDA",  # light green
    "DO":  "D9D2E9",  # light purple
    "REC": "D9EAD3",  # green
    "NN":  "F4CCCC",  # red
    "SL":  "CFE2F3",  # sky blue
    "LS":  "EFEFEF",  # grey
}


def _cell(ws, row, col, value="", bold=False, center=True, fill=None,
          border=True, font_size=9, wrap=False):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name="Arial", size=font_size, bold=bold)
    c.alignment = Alignment(
        horizontal="center" if center else "left",
        vertical="center",
        wrap_text=wrap,
    )
    if fill:
        c.fill = PatternFill("solid", fgColor=fill)
    if border:
        c.border = BORDER_ALL
    return c


def generate_pontaj(year: int, month: int, employees: list, records_by_emp: dict) -> bytes:
    """
    employees: list of Employee objects
    records_by_emp: {employee_id: {date: status_code}}
    Returns raw .xlsx bytes.
    """
    wb = Workbook()
    ws = wb.active
    month_name = _month_name_ro(month)
    ws.title = f"Pontaj {month_name} {year}"

    _, num_days = calendar.monthrange(year, month)
    holidays = get_public_holidays(year)
    all_days = [date(year, month, d) for d in range(1, num_days + 1)]

    # --- Title row ---
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4 + num_days + 6)
    title_cell = ws.cell(row=1, column=1,
                         value=f"PONTAJ LUNAR — {month_name.upper()} {year}")
    title_cell.font = Font(name="Arial", size=13, bold=True)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.fill = PatternFill("solid", fgColor="2F5496")
    title_cell.font = Font(name="Arial", size=13, bold=True, color="FFFFFF")
    ws.row_dimensions[1].height = 22

    # --- Column headers row (row 2) ---
    headers_fixed = ["Nr.", "Nume și Prenume", "Funcție", "Departament"]
    for ci, h in enumerate(headers_fixed, start=1):
        _cell(ws, 2, ci, h, bold=True, fill="D6E4F0", font_size=8)

    day_col_start = 5
    for di, d in enumerate(all_days):
        col = day_col_start + di
        is_weekend = d.weekday() >= 5
        is_holiday = d in holidays
        fill = "EFEFEF" if is_weekend else ("CFE2F3" if is_holiday else "FFFFFF")
        _cell(ws, 2, col, d.day, bold=True, fill=fill, font_size=8)

    summary_headers = ["Zile\nLucrate", "CO", "CM", "CFP", "NN", "Alte\nAbsențe"]
    summary_col_start = day_col_start + num_days
    for si, sh in enumerate(summary_headers):
        _cell(ws, 2, summary_col_start + si, sh, bold=True, fill="D6E4F0", font_size=7, wrap=True)

    ws.row_dimensions[2].height = 28

    # --- Day-of-week subheader row (row 3) ---
    _cell(ws, 3, 1, "")
    _cell(ws, 3, 2, "")
    _cell(ws, 3, 3, "")
    _cell(ws, 3, 4, "")
    days_ro = ["Lu", "Ma", "Mi", "Jo", "Vi", "Sâ", "Du"]
    for di, d in enumerate(all_days):
        col = day_col_start + di
        is_weekend = d.weekday() >= 5
        is_holiday = d in holidays
        fill = "EFEFEF" if is_weekend else ("CFE2F3" if is_holiday else "F2F2F2")
        _cell(ws, 3, col, days_ro[d.weekday()], fill=fill, font_size=7)
    for si in range(len(summary_headers)):
        _cell(ws, 3, summary_col_start + si, "")
    ws.row_dimensions[3].height = 14

    # --- Employee rows ---
    for row_idx, emp in enumerate(employees):
        row = 4 + row_idx
        emp_records = records_by_emp.get(emp.id, {})

        _cell(ws, row, 1, row_idx + 1, font_size=8)
        _cell(ws, row, 2, emp.name, center=False, font_size=9)
        _cell(ws, row, 3, emp.position, center=False, font_size=8)
        _cell(ws, row, 4, emp.department, center=False, font_size=8)

        days_worked = 0
        count_co = count_cm = count_cfp = count_nn = count_other = 0

        for di, d in enumerate(all_days):
            col = day_col_start + di
            is_weekend = d.weekday() >= 5
            is_holiday_day = d in holidays

            if is_weekend:
                default = "LS"
            elif is_holiday_day:
                default = "SL"
            else:
                default = "P"

            status = emp_records.get(d, default)

            fill = _STATUS_COLORS.get(status, "FFFFFF")
            if is_weekend or is_holiday_day:
                fill = _STATUS_COLORS.get(status, "EFEFEF" if is_weekend else "CFE2F3")

            display = "" if status in ("P", "LS", "SL") else status
            _cell(ws, row, col, display, fill=fill, font_size=7)

            if status == "P":
                days_worked += 1
            elif status == "CO":
                count_co += 1
            elif status == "CM":
                count_cm += 1
            elif status == "CFP":
                count_cfp += 1
            elif status == "NN":
                count_nn += 1
            elif status not in ("LS", "SL", "P"):
                count_other += 1

        _cell(ws, row, summary_col_start, days_worked, bold=True, fill="E2EFDA", font_size=8)
        _cell(ws, row, summary_col_start + 1, count_co or "", fill="FFF2CC" if count_co else None, font_size=8)
        _cell(ws, row, summary_col_start + 2, count_cm or "", fill="FCE4D6" if count_cm else None, font_size=8)
        _cell(ws, row, summary_col_start + 3, count_cfp or "", fill="DDEBF7" if count_cfp else None, font_size=8)
        _cell(ws, row, summary_col_start + 4, count_nn or "", fill="F4CCCC" if count_nn else None, font_size=8)
        _cell(ws, row, summary_col_start + 5, count_other or "", font_size=8)

        ws.row_dimensions[row].height = 16

    # --- Legend ---
    legend_row = 4 + len(employees) + 1
    ws.merge_cells(start_row=legend_row, start_column=1, end_row=legend_row, end_column=4 + num_days + 6)
    leg = ws.cell(row=legend_row, column=1,
                  value="LEGENDĂ: P=Prezent  CO=Concediu Odihnă  CM=Concediu Medical  "
                        "CFP=Concediu Fără Plată  CIC=Concediu Îngrijire Copil  "
                        "DO=Delegație  REC=Recuperare  NN=Nemotivat  "
                        "SL=Sărbătoare Legală  LS=Liber Săptămânal")
    leg.font = Font(name="Arial", size=7, italic=True)
    leg.alignment = Alignment(horizontal="left", vertical="center")
    leg.fill = PatternFill("solid", fgColor="F2F2F2")
    ws.row_dimensions[legend_row].height = 14

    # --- Column widths ---
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 16
    for di in range(num_days):
        ws.column_dimensions[get_column_letter(day_col_start + di)].width = 3.2
    for si in range(len(summary_headers)):
        ws.column_dimensions[get_column_letter(summary_col_start + si)].width = 6

    ws.freeze_panes = "E4"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _month_name_ro(month: int) -> str:
    names = [
        "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
        "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
    ]
    return names[month - 1]
