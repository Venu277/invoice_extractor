from datetime import date
from typing import Any
from sqlalchemy.orm import Query
from app.models.invoice import Invoice


def get_fy_range(fy_year: int, fy_start_month: int = 4) -> tuple[date, date]:
    """
    Returns (start_date, end_date) for a given financial year.
    e.g. fy_year=2024, fy_start_month=4 -> 2024-04-01 to 2025-03-31
    """
    start_date = date(fy_year, fy_start_month, 1)
    # End date is 1 year later minus 1 day
    if fy_start_month == 1:
        end_date = date(fy_year, 12, 31)
    else:
        end_year = fy_year + 1
        end_month = fy_start_month - 1
        # Days in end month
        import calendar
        _, last_day = calendar.monthrange(end_year, end_month)
        end_date = date(end_year, end_month, last_day)
    return start_date, end_date


def get_current_fy(fy_start_month: int = 4, as_of: date | None = None) -> int:
    d = as_of or date.today()
    if d.month >= fy_start_month:
        return d.year
    return d.year - 1


def filter_query_by_period(
    query: Query,
    fy: int | None = None,
    quarter: str | None = None,  # Q1, Q2, Q3, Q4
    month: str | None = None,    # YYYY-MM
    fy_start_month: int = 4
) -> Query:
    """Applies date filtering to an Invoice query based on FY, quarter, or month."""
    if month:
        import calendar
        try:
            parts = month.split("-")
            y, m = int(parts[0]), int(parts[1])
            _, last_day = calendar.monthrange(y, m)
            start_d = date(y, m, 1)
            end_d = date(y, m, last_day)
            return query.filter(Invoice.invoice_date >= start_d, Invoice.invoice_date <= end_d)
        except Exception:
            pass

    if fy:
        start_d, end_d = get_fy_range(fy, fy_start_month)
        if quarter:
            # Quarter mapping based on fy_start_month
            q_num = int(quarter.replace("Q", ""))
            q_start_month = (fy_start_month + (q_num - 1) * 3 - 1) % 12 + 1
            q_start_year = fy if q_start_month >= fy_start_month else fy + 1
            q_end_month = (q_start_month + 2 - 1) % 12 + 1
            q_end_year = fy if q_end_month >= fy_start_month else fy + 1
            import calendar
            _, last_day = calendar.monthrange(q_end_year, q_end_month)
            start_d = date(q_start_year, q_start_month, 1)
            end_d = date(q_end_year, q_end_month, last_day)

        return query.filter(Invoice.invoice_date >= start_d, Invoice.invoice_date <= end_d)

    return query
