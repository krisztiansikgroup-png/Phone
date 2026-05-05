"""Romanian public holidays calculator (Legea nr. 53/2003 - Codul Muncii)."""
from datetime import date, timedelta


def _easter(year: int) -> date:
    """Compute Orthodox Easter using the Julian calendar algorithm."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    # Julian to Gregorian offset (13 days for 20th-21st century)
    julian = date(year, month, day)
    return julian + timedelta(days=13)


def get_public_holidays(year: int) -> dict[date, str]:
    """Return all Romanian public holidays for a given year."""
    easter = _easter(year)
    holidays = {
        date(year, 1, 1): "Anul Nou",
        date(year, 1, 2): "Anul Nou (a doua zi)",
        date(year, 1, 24): "Unirea Principatelor Române",
        easter - timedelta(days=2): "Vinerea Mare",
        easter: "Paștele (prima zi)",
        easter + timedelta(days=1): "Paștele (a doua zi)",
        date(year, 5, 1): "Ziua Muncii",
        date(year, 5, 3): "Ziua Mondială a Libertății Presei",
        easter + timedelta(days=49): "Rusaliile (prima zi)",
        easter + timedelta(days=50): "Rusaliile (a doua zi)",
        date(year, 6, 1): "Ziua Copilului",
        date(year, 8, 15): "Adormirea Maicii Domnului",
        date(year, 11, 30): "Sfântul Andrei",
        date(year, 12, 1): "Ziua Națională",
        date(year, 12, 25): "Crăciunul (prima zi)",
        date(year, 12, 26): "Crăciunul (a doua zi)",
    }
    return holidays


def is_public_holiday(d: date) -> bool:
    return d in get_public_holidays(d.year)


def is_working_day(d: date) -> bool:
    """Return True if the date is a working day (Mon-Fri, not a public holiday)."""
    return d.weekday() < 5 and not is_public_holiday(d)
