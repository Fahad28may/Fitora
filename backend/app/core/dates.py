from datetime import UTC, date, datetime


def age_years(dob: date) -> int:
    today = datetime.now(UTC).date()
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age
