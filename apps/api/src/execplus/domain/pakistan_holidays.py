"""Use case: Supplies an offline, versioned table of Pakistan fixed-date public holidays.

What it does: Lists the gazetted fixed-date federal holidays for a bounded year range so
forecasts can use a holiday indicator without any network call. Moon-sighting holidays
(Eid-ul-Fitr, Eid-ul-Adha, Ashura, Eid Milad-un-Nabi) are excluded and must be declared.
"""

from datetime import date

CALENDAR_ID = "pk-public-fixed-v1"
FIRST_YEAR = 2020
LAST_YEAR = 2030
SOURCE = (
    "Government of Pakistan, Cabinet Division annual public-holiday circulars "
    "(for example the 2025 circular dated 23 December 2024)."
)
FIXED = (
    ("Kashmir Solidarity Day", 2, 5, FIRST_YEAR),
    ("Pakistan Day", 3, 23, FIRST_YEAR),
    ("Labour Day", 5, 1, FIRST_YEAR),
    ("Youm-e-Takbeer", 5, 28, 2024),
    ("Independence Day", 8, 14, FIRST_YEAR),
    ("Iqbal Day", 11, 9, 2022),
    ("Quaid-e-Azam Day / Christmas", 12, 25, FIRST_YEAR),
)
LIMITATIONS = (
    "Fixed-date federal holidays only; Eid, Ashura and Eid Milad-un-Nabi depend on moon "
    "sighting and must be declared as holiday dates.",
    "Years after the latest checked circular assume the same fixed dates; provincial, "
    "optional and one-off holidays are not included.",
)


def catalog() -> dict[str, object]:
    return dict(
        id=CALENDAR_ID,
        label="Pakistan fixed-date public holidays",
        first_year=FIRST_YEAR,
        last_year=LAST_YEAR,
        source=SOURCE,
        holidays=[
            dict(name=name, month=month, day=day, from_year=first)
            for name, month, day, first in FIXED
        ],
        limitations=list(LIMITATIONS),
    )


def holidays(start: date, end: date) -> tuple[date, ...]:
    if start.year < FIRST_YEAR or end.year > LAST_YEAR:
        raise ValueError("outside table years")
    return tuple(
        sorted(
            date(year, month, day)
            for year in range(start.year, end.year + 1)
            for _, month, day, first in FIXED
            if year >= first and start <= date(year, month, day) <= end
        )
    )
