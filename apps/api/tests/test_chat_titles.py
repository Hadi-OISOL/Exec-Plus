"""Use case: Proves chat titles come from the owner's first turn deterministically.

What it does: Checks plan-based subjects, the dataset suffix, length cap, question fallback and
that a user-set name always wins over a derived title.
"""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from execplus.domain.threads import Thread, ThreadSummary, context_title


@pytest.mark.parametrize(
    ("metric", "aggregation", "grouping", "expected"),
    [
        ("revenue", "sum", ("region",), "Total revenue by region — Retail sales"),
        ("unit_price", "avg", (), "Average unit price — Retail sales"),
        ("*", "count", ("store_city",), "Record count by store city — Retail sales"),
        ("(all columns)", "rows", (), "Records — Retail sales"),
        (
            "cost",
            "max",
            ("date:month", "region", "x"),
            "Highest cost by date month and region — Retail sales",
        ),
    ],
)
def test_title_names_the_measure_grouping_and_dataset(metric, aggregation, grouping, expected):
    assert context_title("ignored", metric, aggregation, grouping, "Retail sales") == expected


def test_title_is_capped_and_drops_the_dataset_before_the_subject():
    title = context_title("q", "net_revenue_after_returns", "sum", ("sales_region",), "A" * 40)
    assert title == "Total net revenue after returns by sales region"
    assert len(context_title("q", "m" * 90, "sum", (), "D")) == 60


def test_title_falls_back_to_the_first_seven_question_words():
    assert (
        context_title("  How  many crops failed?  ", None, None, (), "Farm")
        == "How many crops failed?"
    )
    assert (
        context_title("one two three four five six seven eight", "x", "analysis", (), "D")
        == "one two three four five six seven…"
    )
    assert context_title(None, None, None, (), "Farm") == "New chat"


def test_a_user_name_always_wins_and_derived_titles_are_stable():
    now = datetime.now(timezone.utc)
    thread = Thread(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), now)
    summary = ThreadSummary(thread, "Revenue?", now, 1, "Sales", "s.csv", "revenue", "sum", ())
    assert summary.display_title == summary.display_title == "Total revenue — Sales"
    assert replace(summary, thread=replace(thread, title="Mine")).display_title == "Mine"
