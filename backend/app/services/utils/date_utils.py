from datetime import datetime


def rewind_date_range_one_year(date_from: str, date_to: str) -> tuple[str, str]:
    date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
    date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
    return (
        date_from_obj.replace(year=date_from_obj.year - 1).strftime("%Y-%m-%d"),
        date_to_obj.replace(year=date_to_obj.year - 1).strftime("%Y-%m-%d"),
    )
