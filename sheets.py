"""
Google Sheets integration — writes Foaie Colectivă de Prezență live.

Setup (one-time):
  1. Go to https://console.cloud.google.com → New project
  2. Enable "Google Sheets API" and "Google Drive API"
  3. Create a Service Account → download JSON key
  4. Set env var: GOOGLE_CREDENTIALS_FILE=/path/to/key.json
  5. Create a Google Sheet and share it (Editor) with the service account email
  6. Set env var: GOOGLE_SHEET_ID=<the sheet ID from the URL>
  7. Share the sheet with your accountant (Viewer role)
"""
import calendar
import json
import os
from datetime import date, timedelta

from holidays_ro import get_public_holidays

_MONTH_NAMES = [
    "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]

STATUS_TO_FOAIE = {
    "P":   8,
    "LS":  "X",
    "SL":  "X",
    "CO":  "Co",
    "CM":  "Bo",
    "CFP": "NN",
    "CIC": "S",
    "DO":  "D",
    "REC": 8,
    "NN":  "NN",
}


def _gspread_client():
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")
    if not creds_file:
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_FILE env var not set. "
            "See sheets.py docstring for setup instructions."
        )
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    return gspread.authorize(creds)


def _sheet_title(year: int, month: int) -> str:
    return f"{year}-{_MONTH_NAMES[month - 1]}"


def sync_month_to_sheets(year: int, month: int,
                          employees: list, records_by_emp: dict) -> str:
    """
    Write one month of attendance data to Google Sheets.
    Returns the spreadsheet URL.
    """
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError(
            "GOOGLE_SHEET_ID env var not set. "
            "Create a Google Sheet and set its ID."
        )

    gc = _gspread_client()
    spreadsheet = gc.open_by_key(sheet_id)

    title = _sheet_title(year, month)
    try:
        ws = spreadsheet.worksheet(title)
    except Exception:
        ws = spreadsheet.add_worksheet(title=title, rows=30, cols=36)

    _, num_days = calendar.monthrange(year, month)
    holidays = get_public_holidays(year)
    all_days = [date(year, month, d) for d in range(1, num_days + 1)]
    working_days = sum(1 for d in all_days
                       if d.weekday() < 5 and d not in holidays)

    # Build the full grid as a list-of-lists
    # Col layout: [Nr, Nume, blank, day1..dayN, TOTAL]
    total_col_idx = 3 + num_days   # 0-based index of TOTAL column

    rows = []

    # Row 1: company
    r1 = ["Unitatea: S.C. PIESE TRANSILVANE S.R.L."] + [""] * (total_col_idx)
    rows.append(r1)

    # Row 2: title
    r2 = ["FOAIE COLECTIVĂ DE PREZENȚĂ"] + [""] * (total_col_idx)
    rows.append(r2)

    # Row 3: month / working days / total header
    r3 = [f"Pe luna: {_MONTH_NAMES[month-1].upper()} {year}", "", ""]
    r3 += [""] * num_days
    r3.append("TOTAL ORE")
    mid = num_days // 2
    r3[3 + mid] = f"{working_days} zile lucrătoare"
    rows.append(r3)

    # Row 4: column headers
    r4 = ["Nr.", "Nume și Prenume", "ORE ZILNICE"]
    r4 += [""] * num_days
    r4.append("")
    rows.append(r4)

    # Row 5: day numbers
    r5 = ["", "", ""] + [d.day for d in all_days] + [""]
    rows.append(r5)

    # Employee rows
    for idx, emp in enumerate(employees):
        emp_records = records_by_emp.get(emp.id, {})
        row = [f"{idx + 1}.", emp.name, ""]
        total_hours = 0
        for d in all_days:
            is_weekend = d.weekday() >= 5
            is_holiday = d in holidays
            if is_weekend:
                default = "LS"
            elif is_holiday:
                default = "SL"
            else:
                default = "P"
            status = emp_records.get(d, default)
            foaie = STATUS_TO_FOAIE.get(status, 8)
            if foaie == 8:
                total_hours += 8
            row.append(foaie)
        row.append(total_hours)
        rows.append(row)

    # Legend rows
    for text in [
        "Co-concediu de odihnă",
        "Bo-boală",
        "D-delegație",
        "S-suspendat",
        "NN-nelucrat, neplătit",
    ]:
        rows.append(["", text] + [""] * (total_col_idx - 1))

    ws.clear()
    ws.update(range_name="A1", values=rows)

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def is_sheets_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_CREDENTIALS_FILE")
        and os.environ.get("GOOGLE_SHEET_ID")
    )


def get_sheet_url() -> str | None:
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else None
