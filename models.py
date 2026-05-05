from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(120), nullable=False, default="")
    department = db.Column(db.String(120), nullable=False, default="")
    cnp = db.Column(db.String(13), nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True)

    records = db.relationship("AttendanceRecord", backref="employee", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Employee {self.name}>"


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    # P=prezent, CO=concediu odihnă, CM=concediu medical,
    # CFP=concediu fără plată, CIC=concediu îngrijire copil,
    # DO=delegație, REC=recuperare, NN=nemotivat, SL=sărbătoare legală, LS=liber săptămânal
    status = db.Column(db.String(4), nullable=False, default="P")
    notes = db.Column(db.String(255), nullable=True)

    __table_args__ = (db.UniqueConstraint("employee_id", "record_date", name="uq_employee_date"),)

    def __repr__(self):
        return f"<AttendanceRecord {self.employee_id} {self.record_date} {self.status}>"


STATUSES = {
    "P": "Prezent",
    "CO": "Concediu Odihnă",
    "CM": "Concediu Medical",
    "CFP": "Concediu Fără Plată",
    "CIC": "Concediu Îngrijire Copil",
    "DO": "Delegație",
    "REC": "Recuperare",
    "NN": "Nemotivat",
    "SL": "Sărbătoare Legală",
    "LS": "Liber Săptămânal",
}
