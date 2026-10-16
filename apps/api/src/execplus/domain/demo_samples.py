"""Use case: Generates reproducible fictional data for the guided ExecPlus demo.

What it does: Supplies complete retail histories and declared action assumptions, without files.
"""

import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO

RETAIL_COLUMNS = (
    "Record_ID",
    "Date",
    "Region",
    "Campaign",
    "Week_Part",
    "Orders",
    "Revenue_USD",
    "Ad_Spend_USD",
    "Visits",
    "Returns",
    "Delivery_Hours",
    "Discount_pct",
    "Support_Tickets",
)

ACTION_COLUMNS = ("Action", "Cost_USD", "Benefit_USD", "Staff_Hours")


def _jitter(day: int, region: str, field: str, width: int) -> int:
    seed = f"execplus-retail-v1/{day}/{region}/{field}".encode()
    return int.from_bytes(sha256(seed).digest()[:4], "big") % (2 * width + 1) - width


def _money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def _encode(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def retail_csv() -> bytes:
    regions = (("North", 130, 80, 200), ("Central", 95, 60, 700), ("South", 70, 40, 1200))
    weekly = (0, 4, 8, 12, 25, 35, 20)
    unusual = {(73, "North"): 180, (181, "Central"): 240, (286, "South"): 300}
    rows: list[tuple[str, ...]] = []
    for index in range(365):
        day = date(2025, 1, 1) + timedelta(days=index)
        promotion = index % 28 >= 21
        for region_index, (region, base_orders, price, base_ads) in enumerate(regions):
            demand = weekly[day.weekday()] + index // 14 + (14 if promotion else 0)
            orders = base_orders + demand + _jitter(index, region, "orders", 9)
            discount = (15 if promotion else 5) + _jitter(index, region, "discount", 1)
            revenue_cents = orders * price * (100 - discount)
            ads_cents = (base_ads + demand * 4 + _jitter(index, region, "ads", 15)) * 100
            visits = orders * 18 + _jitter(index, region, "visits", 100)
            returns = orders // 25 + 2 + _jitter(index, region, "returns", 2)
            delivery_tenths = (
                360 - region_index * 60 + demand * 2 + _jitter(index, region, "delivery", 60)
            )
            tickets = unusual.get(
                (index, region), 12 + region_index * 6 + _jitter(index, region, "tickets", 4)
            )
            rows.append(
                (
                    f"DEMO-{day:%Y%m%d}-{region.upper()}",
                    day.isoformat(),
                    region,
                    "Promotion" if promotion else "Standard",
                    "Weekend" if day.weekday() >= 5 else "Weekday",
                    str(orders),
                    _money(revenue_cents),
                    _money(ads_cents),
                    str(visits),
                    str(returns),
                    f"{delivery_tenths // 10}.{delivery_tenths % 10}",
                    str(discount),
                    str(tickets),
                )
            )
    return _encode(RETAIL_COLUMNS, rows)


def actions_csv() -> bytes:
    rows: list[tuple[str, ...]] = [
        ("Tracking setup", "200.00", "15.00", "2"),
        ("Email campaign", "300.00", "60.00", "3"),
        ("Search ads", "500.00", "85.00", "4"),
        ("Social ads", "400.00", "70.00", "4"),
        ("Checkout training", "250.00", "45.00", "3"),
        ("Support shift", "150.00", "20.00", "2"),
    ]
    return _encode(ACTION_COLUMNS, rows)
