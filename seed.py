"""
Run once to populate the employees table from the existing Excel data.
  python seed.py
"""
from app import app, db
from models import Employee

EMPLOYEES = [
    # (name, position, department, active)
    ("Sándor Krisztián-Lajos",     "Director",       "",  True),
    ("Dobos Levente-Szilveszter",  "Agent Vânzări",  "",  True),
    ("Bíró Botond",                "",               "",  True),
    ("Haidu Attila",               "",               "",  True),
    ("Deák Eszter",                "",               "",  True),
    ("Szalai Csaba",               "",               "",  True),
    ("Mariana Petre",              "",               "",  True),   # angajată din Aprilie 2026
    ("Tókos Enikő",                "",               "",  False),  # nu mai lucrează
]

with app.app_context():
    db.create_all()
    existing = {e.name for e in Employee.query.all()}
    added = 0
    for name, position, department, active in EMPLOYEES:
        if name not in existing:
            db.session.add(Employee(
                name=name,
                position=position,
                department=department,
                active=active,
            ))
            added += 1
        else:
            # update active status if already present
            emp = Employee.query.filter_by(name=name).first()
            emp.active = active
    db.session.commit()
    print(f"Done — {added} angajați adăugați, lista actualizată.")
    for emp in Employee.query.order_by(Employee.active.desc(), Employee.name).all():
        status = "✓ activ" if emp.active else "✗ inactiv"
        print(f"  {status}  {emp.name}")
