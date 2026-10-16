"""Use case: Provides versioned, entirely synthetic onboarding examples.

What it does: Generates finance, sales and inventory CSV bytes without external datasets.
"""

from datetime import date, timedelta

from execplus.domain.demo_samples import actions_csv, retail_csv
from execplus.domain.ingestion import IngestionError

SAMPLES = (
    {
        "id": "retail-v1",
        "name": "Retail demo",
        "version": 1,
        "description": (
            "Entirely fictional daily retail operations: 1,095 rows, three regions and "
            "365 complete days in 2025. Explore patterns, grouped relationships, unusual "
            "support volumes, daily forecasts and explicit what-if assumptions. "
            "Review units and meanings before calculating."
        ),
    },
    {
        "id": "actions-v1",
        "name": "Decision demo",
        "version": 1,
        "description": (
            "Six fictional actions with declared USD costs, assumed USD benefits and "
            "staff hours. Try a budget of 1,000 USD, ten staff hours and at most one "
            "of each action. Benefits are assumptions, not predictions."
        ),
    },
    {
        "id": "forecast-v1",
        "name": "Forecasting sample",
        "version": 1,
        "description": (
            "Fictional daily revenue in PKR and order counts for 90 complete days in 2024. "
            "Confirm the units and daily coverage before forecasting."
        ),
    },
    {
        "id": "cities-v1",
        "name": "City sales sample",
        "version": 1,
        "description": "Fictional city sales across Karachi, Lahore and Islamabad.",
    },
    {
        "id": "finance-v1",
        "name": "Finance sample",
        "version": 1,
        "description": (
            "Synthetic monthly income and costs; includes a missing cost to explore quality checks."
        ),
    },
    {
        "id": "sales-v1",
        "name": "Sales sample",
        "version": 1,
        "description": (
            "Synthetic orders by region; "
            "includes whitespace and a repeated order to preview cleaning."
        ),
    },
    {
        "id": "inventory-v1",
        "name": "Inventory sample",
        "version": 1,
        "description": "Synthetic stock counts and prices for three fictional products.",
    },
)


def sample_csv(sample_id: str) -> bytes:
    if sample_id == "retail-v1":
        return retail_csv()
    if sample_id == "actions-v1":
        return actions_csv()
    if sample_id == "forecast-v1":
        return (
            "date,revenue,orders,city\n"
            + "\n".join(
                f"{date(2024, 1, 1) + timedelta(days=index)},"
                f"{1000 + index * 8 + (index % 7) * 20}.25,{20 + index % 7},Karachi"
                for index in range(90)
            )
            + "\n"
        ).encode()
    if sample_id == "cities-v1":
        cities = ("Karachi", "Lahore", "Islamabad")
        channels = ("Direct", "Partner", "Online", "Direct")
        return (
            "order_id,date,city,channel,revenue,cost\n"
            + "\n".join(
                f"CITY{i:03d},2026-09-{i:02d},{cities[(i - 1) % 3]},"
                f"{channels[(i - 1) % 4]},{i * 125}.25,{i * 60}.10"
                for i in range(1, 25)
            )
            + "\n"
        ).encode()
    if sample_id == "finance-v1":
        return (
            "date,category,revenue,cost\n"
            + "\n".join(
                f"2026-{month:02d}-01,Services,{month * 1000},{month * 400 if month != 3 else ''}"
                for month in range(1, 5)
            )
            + "\n"
        ).encode()
    if sample_id == "sales-v1":
        return (
            b"order_id,date,region,amount\nS001,2026-01-01, North ,100\n"
            b"S002,2026-01-02,South,200\nS002,2026-01-02,South,200\n"
        )
    if sample_id == "inventory-v1":
        return (
            "sku,date,stock,price\n"
            + "\n".join(f"DEMO{i},2026-01-01,{i * 10},{i * 5}.50" for i in range(1, 4))
            + "\n"
        ).encode()
    raise IngestionError("not_found", "Choose an available sample version.", 404)
