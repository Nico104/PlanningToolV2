from datetime import date, time, timedelta
from PySide6.QtCore import QDate


def fmt_date(d: date | None) -> str:
    if d is None:
        return "Unassigned"
    return d.strftime("%d.%m.%Y")


def fmt_time(t: time | None) -> str:
    if t is None:
        return ""
    return t.strftime("%H:%M")


def qdate_to_date(qd: QDate) -> date:
    return date(qd.year(), qd.month(), qd.day())


# def date_to_qdate(d: date) -> QDate:
#     return QDate(d.year, d.month, d.day)
def date_to_qdate(d: date | None) -> QDate:
    if d is None:
        return QDate()  # invalid / empty date
    return QDate(d.year, d.month, d.day)



def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())

def mins_from_time(t: time) -> int:
    return t.hour * 60 + t.minute