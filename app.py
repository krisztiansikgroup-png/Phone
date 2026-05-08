import calendar
import os
from datetime import date, timedelta

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from io import BytesIO

from models import STATUSES, AttendanceRecord, Employee, db
from holidays_ro import get_public_holidays, is_working_day
from report import generate_foaie, _MONTH_NAMES

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pontaj.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "pontaj-secret-ro-2024")
db.init_app(app)

with app.app_context():
    db.create_all()


@app.context_processor
def inject_today():
    return {"today": date.today()}


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_ym(year_str, month_str):
    try:
        y, m = int(year_str), int(month_str)
        assert 2000 <= y <= 2100 and 1 <= m <= 12
        return y, m
    except Exception:
        abort(400)


def _month_days(year, month):
    _, num = calendar.monthrange(year, month)
    return [date(year, month, d) for d in range(1, num + 1)]


def _records_map(year, month):
    """Return {employee_id: {date: status}} for the given month."""
    first = date(year, month, 1)
    _, num = calendar.monthrange(year, month)
    last = date(year, month, num)
    rows = AttendanceRecord.query.filter(
        AttendanceRecord.record_date >= first,
        AttendanceRecord.record_date <= last,
    ).all()
    result = {}
    for r in rows:
        result.setdefault(r.employee_id, {})[r.record_date] = r.status
    return result


def _last_day_of_month(year, month):
    _, num = calendar.monthrange(year, month)
    return date(year, month, num)


# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    today = date.today()
    return redirect(url_for("attendance", year=today.year, month=today.month))


# ── employees ────────────────────────────────────────────────────────────────

@app.route("/angajati")
def employees():
    emps = Employee.query.order_by(Employee.name).all()
    return render_template("employees.html", employees=emps)


@app.route("/angajati/nou", methods=["GET", "POST"])
def employee_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Numele este obligatoriu.", "danger")
            return redirect(url_for("employee_new"))
        emp = Employee(
            name=name,
            position=request.form.get("position", "").strip(),
            department=request.form.get("department", "").strip(),
            cnp=request.form.get("cnp", "").strip(),
        )
        db.session.add(emp)
        db.session.commit()
        flash(f'Angajatul „{emp.name}" a fost adăugat.', "success")
        return redirect(url_for("employees"))
    return render_template("employee_form.html", emp=None)


@app.route("/angajati/<int:emp_id>/editeaza", methods=["GET", "POST"])
def employee_edit(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Numele este obligatoriu.", "danger")
            return redirect(url_for("employee_edit", emp_id=emp_id))
        emp.name = name
        emp.position = request.form.get("position", "").strip()
        emp.department = request.form.get("department", "").strip()
        emp.cnp = request.form.get("cnp", "").strip()
        emp.active = "active" in request.form
        db.session.commit()
        flash(f'Angajatul „{emp.name}" a fost actualizat.', "success")
        return redirect(url_for("employees"))
    return render_template("employee_form.html", emp=emp)


@app.route("/angajati/<int:emp_id>/sterge", methods=["POST"])
def employee_delete(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    name = emp.name
    db.session.delete(emp)
    db.session.commit()
    flash(f'Angajatul „{name}" a fost șters.', "warning")
    return redirect(url_for("employees"))


# ── attendance ────────────────────────────────────────────────────────────────

@app.route("/pontaj/<int:year>/<int:month>")
def attendance(year, month):
    year, month = _parse_ym(str(year), str(month))
    employees = Employee.query.filter_by(active=True).order_by(Employee.name).all()
    days = _month_days(year, month)
    holidays = get_public_holidays(year)
    records = _records_map(year, month)

    prev_month = date(year, month, 1) - timedelta(days=1)
    next_month_day = _last_day_of_month(year, month) + timedelta(days=1)

    return render_template(
        "attendance.html",
        year=year,
        month=month,
        month_name=_MONTH_NAMES[month - 1],
        employees=employees,
        days=days,
        holidays=holidays,
        records=records,
        statuses=STATUSES,
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month_day.year,
        next_month=next_month_day.month,
        last_day=_last_day_of_month(year, month),
        sheets_configured=_sheets_configured(),
        sheet_url=_sheet_url(),
    )


@app.route("/pontaj/<int:year>/<int:month>/salveaza", methods=["POST"])
def attendance_save(year, month):
    year, month = _parse_ym(str(year), str(month))
    days = _month_days(year, month)
    holidays = get_public_holidays(year)
    employees = Employee.query.filter_by(active=True).all()

    for emp in employees:
        for d in days:
            key = f"status_{emp.id}_{d.isoformat()}"
            raw = request.form.get(key, "").strip()

            if d.weekday() >= 5:
                default = "LS"
            elif d in holidays:
                default = "SL"
            else:
                default = "P"

            status = raw if raw in STATUSES else default

            rec = AttendanceRecord.query.filter_by(
                employee_id=emp.id, record_date=d
            ).first()
            if rec:
                rec.status = status
            else:
                db.session.add(AttendanceRecord(
                    employee_id=emp.id,
                    record_date=d,
                    status=status,
                ))
    db.session.commit()
    flash("Pontajul a fost salvat cu succes.", "success")
    return redirect(url_for("attendance", year=year, month=month))


# ── report export ─────────────────────────────────────────────────────────────

@app.route("/pontaj/<int:year>/<int:month>/export")
def export_pontaj(year, month):
    year, month = _parse_ym(str(year), str(month))
    employees = Employee.query.filter_by(active=True).order_by(Employee.name).all()
    records = _records_map(year, month)
    xlsx_bytes = generate_foaie(year, month, employees, records)
    month_name = _MONTH_NAMES[month - 1]
    filename = f"Foaie_Prezenta_{month_name}_{year}.xlsx"
    return send_file(
        BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# ── quick bulk-fill helper ────────────────────────────────────────────────────

@app.route("/pontaj/<int:year>/<int:month>/initializeaza", methods=["POST"])
def attendance_init(year, month):
    """Pre-fill all working days as P, weekends as LS, holidays as SL."""
    year, month = _parse_ym(str(year), str(month))
    days = _month_days(year, month)
    holidays = get_public_holidays(year)
    employees = Employee.query.filter_by(active=True).all()

    for emp in employees:
        for d in days:
            existing = AttendanceRecord.query.filter_by(
                employee_id=emp.id, record_date=d
            ).first()
            if existing:
                continue
            if d.weekday() >= 5:
                status = "LS"
            elif d in holidays:
                status = "SL"
            else:
                status = "P"
            db.session.add(AttendanceRecord(employee_id=emp.id, record_date=d, status=status))
    db.session.commit()
    flash("Pontajul a fost inițializat cu zilele lucrătoare implicite.", "info")
    return redirect(url_for("attendance", year=year, month=month))


# ── scan / AI form reader ─────────────────────────────────────────────────────

@app.route("/pontaj/<int:year>/<int:month>/scan", methods=["POST"])
def scan_leave_form(year, month):
    """Accept an uploaded photo of a leave-request form; parse with Claude vision."""
    year, month = _parse_ym(str(year), str(month))

    if "image" not in request.files or request.files["image"].filename == "":
        return jsonify(error="Nicio imagine furnizată."), 400

    img_file = request.files["image"]
    image_bytes = img_file.read()
    mime_type = img_file.mimetype or "image/jpeg"

    try:
        from scan import extract_leave_from_image
        extracted = extract_leave_from_image(image_bytes, mime_type)
    except Exception as exc:
        return jsonify(error=f"Eroare la analiza imaginii: {str(exc)}"), 500

    # validate required fields
    for field in ("employee_name", "leave_type", "start_date", "end_date"):
        if not extracted.get(field):
            return jsonify(
                error=f"Nu s-a putut extrage câmpul «{field}» din imagine. "
                      f"Confidence: {extracted.get('confidence','?')}. "
                      f"Note: {extracted.get('notes','')}"
            ), 422

    leave_type = extracted["leave_type"]
    if leave_type not in STATUSES:
        return jsonify(error=f"Tip concediu necunoscut: {leave_type}"), 422

    try:
        from datetime import datetime as dt
        start = dt.strptime(extracted["start_date"], "%Y-%m-%d").date()
        end = dt.strptime(extracted["end_date"], "%Y-%m-%d").date()
    except ValueError:
        return jsonify(error="Format de dată invalid extras din imagine."), 422

    if start > end:
        return jsonify(error="Data de start este după data de sfârșit."), 422

    # find employee by fuzzy name match (case-insensitive, partial)
    emp_name_q = extracted["employee_name"].strip().lower()
    employees = Employee.query.filter_by(active=True).all()
    matched = None
    for emp in employees:
        if emp_name_q in emp.name.lower() or emp.name.lower() in emp_name_q:
            matched = emp
            break
    # second pass: any word match
    if not matched:
        query_words = set(emp_name_q.split())
        for emp in employees:
            emp_words = set(emp.name.lower().split())
            if query_words & emp_words:
                matched = emp
                break

    if not matched:
        return jsonify(
            error=f"Angajatul «{extracted['employee_name']}» nu a fost găsit în sistem. "
                  f"Verificați că este adăugat în lista de angajați."
        ), 404

    # apply leave status to all days in range that fall in this month
    holidays = get_public_holidays(year)
    days_updated = 0
    warnings = []

    current = start
    while current <= end:
        if current.year == year and current.month == month:
            if current.weekday() >= 5:
                warnings.append(f"{current.isoformat()} este weekend")
            elif current in holidays:
                warnings.append(f"{current.isoformat()} este sărbătoare legală")
            else:
                rec = AttendanceRecord.query.filter_by(
                    employee_id=matched.id, record_date=current
                ).first()
                if rec:
                    rec.status = leave_type
                else:
                    db.session.add(AttendanceRecord(
                        employee_id=matched.id,
                        record_date=current,
                        status=leave_type,
                    ))
                days_updated += 1
        current += timedelta(days=1)

    db.session.commit()

    return jsonify(
        employee=matched.name,
        leave_type=f"{leave_type} ({STATUSES[leave_type]})",
        start_date=start.strftime("%d.%m.%Y"),
        end_date=end.strftime("%d.%m.%Y"),
        days_updated=days_updated,
        confidence=extracted.get("confidence"),
        warnings="; ".join(warnings) if warnings else None,
    )


# ── Google Sheets helpers ─────────────────────────────────────────────────────

def _sheets_configured():
    from sheets import is_sheets_configured
    return is_sheets_configured()


def _sheet_url():
    from sheets import get_sheet_url
    return get_sheet_url()


@app.route("/pontaj/<int:year>/<int:month>/sync-sheets", methods=["POST"])
def sync_to_sheets(year, month):
    year, month = _parse_ym(str(year), str(month))
    employees = Employee.query.filter_by(active=True).order_by(Employee.name).all()
    records = _records_map(year, month)
    try:
        from sheets import sync_month_to_sheets
        url = sync_month_to_sheets(year, month, employees, records)
        flash(f'Pontajul a fost sincronizat cu Google Sheets. '
              f'<a href="{url}" target="_blank">Deschide foaia</a>', "success")
    except Exception as exc:
        flash(f"Eroare sincronizare Google Sheets: {exc}", "danger")
    return redirect(url_for("attendance", year=year, month=month))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
