"""Use case: Provides versioned, entirely synthetic onboarding examples.

What it does: Generates finance, sales and inventory CSV bytes without external datasets.
"""

from execplus.domain.ingestion import IngestionError

SAMPLES = (
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
