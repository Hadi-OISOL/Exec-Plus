"""Use case: Verifies the exact dataset brief and the per-dataset automatic dashboard.

What it does: Compares brief statistics with pandas, checks tile enumeration for sales, survey,
IoT and ledger shapes, the model ranking path and its no-model fallback, without PostgreSQL.
"""

import asyncio
import io
import json
import random
from contextlib import nullcontext
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services import auto_dashboards as service_module
from execplus.application.services.auto_dashboards import AutoDashboardService
from execplus.domain import auto_dashboard as boards
from execplus.domain import dataset_brief as briefs
from execplus.domain.evidence import receipt
from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import CalculationLineage, WorkspaceScope
from execplus.domain.profiling import MISSING_PLACEHOLDERS, TableData, profile_for
from execplus.domain.semantics import dataset_view, plan_query
from execplus.domain.understanding import apply_definition, governed_request, infer_definition
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics


def csv_table(text: str) -> TableData:
    frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    return TableData(tuple(frame.columns), tuple(tuple(row) for row in frame.itertuples(False)))


def sales_csv(seed: int = 3) -> str:
    rng = random.Random(seed)
    lines = ["order_date,region,product,amount,quantity,customer_email"]
    start = date(2024, 1, 1)
    regions = ["North", "South", "East", "West", "north "]
    for index in range(240):
        day = start + timedelta(days=rng.randrange(0, 420))
        amount = "N/A" if index % 37 == 0 else f"{rng.randrange(100, 99999) / 100:.2f}"
        lines.append(
            f"{day.isoformat()},{rng.choice(regions)},P{rng.randrange(1, 7)},{amount},"
            f"{rng.randrange(1, 20)},user{index}@example.test"
        )
    return "\n".join(lines) + "\n"


def survey_csv() -> str:
    rng = random.Random(5)
    lines = ["respondent_id,age_group,department,satisfaction,comment"]
    for index in range(120):
        lines.append(
            f"R{index:04d},{rng.choice(['18-24', '25-34', '35-44', '45+'])},"
            f"{rng.choice(['Sales', 'Ops', 'HR'])},{rng.randrange(1, 6)},"
            f"{rng.choice(['good', 'ok', 'slow service', ''])}"
        )
    return "\n".join(lines) + "\n"


def iot_csv() -> str:
    rng = random.Random(7)
    lines = ["reading_time,sensor,temperature_c,humidity"]
    for hour in range(0, 24 * 30, 6):
        moment = f"2025-03-{1 + hour // 24:02d} {hour % 24:02d}:00:00"
        for sensor in ("S1", "S2", "S3"):
            lines.append(
                f"{moment},{sensor},{rng.randrange(150, 350) / 10:.1f},{rng.randrange(20, 90)}"
            )
    return "\n".join(lines) + "\n"


def ledger_csv() -> str:
    rng = random.Random(11)
    lines = ["entry_date,account,amount,memo"]
    accounts = ["Cash", "Revenue", "Rent", "Payroll", "Supplies", "Tax"]
    for index in range(150):
        day = date(2023, 1, 1) + timedelta(days=rng.randrange(0, 900))
        value = rng.randrange(-50000, 90000) / 100
        lines.append(f"{day},{rng.choice(accounts)},{value:.2f},entry {index}")
    return "\n".join(lines) + "\n"


def context_for(
    table: TableData, units: dict[str, str] | None = None, goal: str = ""
) -> DescriptionContext:
    metadata = profile_for(table, "profile-v4")
    view = replace(
        dataset_view(metadata),
        sources=({"dataset_id": "d", "upload_id": "u", "revision_id": "r"},),
    )
    if units is None:
        return DescriptionContext("file", metadata, view, None, "inferred", goal)
    definition = infer_definition(metadata)
    definition["grain"] = "record"
    for column in definition["columns"]:
        if column["name"] in units:
            column["role"], column["unit"] = "metric", units[column["name"]]
    return DescriptionContext(
        "file", metadata, apply_definition(view, definition), definition, "confirmed", goal
    )


class FakeAnalytics:
    def __init__(self, table: TableData, context: DescriptionContext) -> None:
        self.table, self.context = table, context
        dataset = uuid4()
        self.dataset = dataset
        self.scope = WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset}))
        self.executor = DuckDBQueryExecutor(15, 256)
        self.persisted: list[CalculationLineage] = []

    def descriptive_snapshot(self, actor, workspace_id, dataset_id, upload_id):
        return self.context, self.table, self.scope

    def uow(self):
        return nullcontext(None)

    def _authorize(self, repo, actor, workspace_id):
        return None

    def _persist(self, actor, lineage):
        self.persisted.append(lineage)

    def recheck_description(self, actor, workspace_id, dataset_id, upload_id, sources):
        return None

    async def _execute(self, actor, did, name, scope, table, view, request, route=None):
        request = governed_request(view, table, request)
        plan = plan_query(scope, did, view, request, row_limit=10_000)
        result = await self.executor.execute(plan, scope, table, view)
        lineage = CalculationLineage(
            plan.query_id,
            scope.workspace_id,
            did,
            name,
            len(table.rows),
            request.metric,
            request.aggregation.value,
            request.group_by,
            (),
            plan.sql,
            route,
            receipt(plan, view.sources, result),
        )
        self.persisted.append(lineage)
        return result, lineage


class ScriptedModel:
    def __init__(self, reply):
        self.reply, self.requests = reply, []

    async def complete(self, request):
        self.requests.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        content = self.reply(request) if callable(self.reply) else self.reply
        return ModelResponse(content, "test-model", "scripted")


@pytest.fixture(autouse=True)
def clear_cache():
    service_module._CACHE.clear()
    yield
    service_module._CACHE.clear()


def brief_for(text: str, units=None, goal="", model=None):
    table = csv_table(text)
    context = context_for(table, units, goal)
    analytics = FakeAnalytics(table, context)
    service = AutoDashboardService(None, analytics, ScipyPatternStatistics(), model)
    brief, cards, *_ = asyncio.run(service.brief(None, uuid4(), analytics.dataset, uuid4()))
    return service, analytics, brief, cards


def test_brief_statistics_match_pandas_exactly():
    text = sales_csv()
    _, analytics, brief, _ = brief_for(text)
    frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    columns = {item["name"]: item for item in brief["columns"]}
    assert brief["version"] == "dataset-brief-v1"
    assert brief["dataset"]["rows"] == str(len(frame))
    amounts = frame["amount"].map(
        lambda value: None if value.strip().casefold() in MISSING_PLACEHOLDERS else Decimal(value)
    )
    present = [value for value in amounts if value is not None]
    amount = columns["amount"]
    assert Decimal(amount["sum"]) == sum(present)
    assert Decimal(amount["min"]) == min(present) and Decimal(amount["max"]) == max(present)
    assert amount["missing"] == str(len(amounts) - len(present))
    assert amount["distinct"] == str(len(set(present)))
    assert "na_placeholders" in amount["flags"]
    quantity = frame["quantity"].astype(int)
    assert columns["quantity"]["sum"] == str(quantity.sum())
    assert columns["quantity"]["distinct"] == str(quantity.nunique())
    counts = frame["region"].value_counts()
    top = columns["region"]["top"]
    assert top[0] == [counts.index[0], str(counts.iloc[0])]
    assert columns["region"]["distinct"] == str(frame["region"].nunique())
    assert "label_variants" in columns["region"]["flags"]
    dates = frame["order_date"]
    assert (
        columns["order_date"]["min"] == dates.min() and columns["order_date"]["max"] == dates.max()
    )
    months = pd.to_datetime(dates).dt.strftime("%Y-%m")
    assert brief["date_coverage"]["months_with_data"] == str(months.nunique())
    assert columns["customer_email"]["distinct"] == str(frame["customer_email"].nunique())
    assert all(row["customer_email"] == "(withheld)" for row in brief["samples"]["rows"])
    assert {item["code"] for item in brief["quality"]} >= {"na_placeholders", "label_variants"}
    assert all(item.receipt["outcome"] == "executed" for item in analytics.persisted)
    model_text = briefs.model_view(brief, include_values=False)
    assert "user0@example.test" not in model_text and '"top"' not in model_text
    assert len(model_text) <= briefs.MODEL_CHARS
    assert len(json.dumps(brief)) < 40_000


def test_high_cardinality_columns_fall_back_to_exact_aggregates(monkeypatch):
    monkeypatch.setattr(briefs, "GROUP_LIMIT", 20)
    text = sales_csv()
    _, _, brief, _ = brief_for(text)
    frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    amount = {item["name"]: item for item in brief["columns"]}["amount"]
    present = [Decimal(v) for v in frame["amount"] if v != "N/A"]
    assert amount["distinct"] == "more than 20"
    assert Decimal(amount["sum"]) == sum(present) and Decimal(amount["max"]) == max(present)
    assert amount["present"] == str(len(present))


def kinds(candidates):
    return {item.kind for item in candidates}


def test_sales_with_dates_gets_kpis_trends_rankings_and_shares():
    _, _, brief, cards = brief_for(sales_csv(), {"amount": "PKR", "quantity": "units"})
    candidates = boards.enumerate_candidates(
        context_for(csv_table(sales_csv()), {"amount": "PKR", "quantity": "units"}), brief, cards
    )
    ids = {item.id for item in candidates}
    assert {"kpi", "trend", "top", "category", "volume"} <= kinds(candidates)
    assert "kpi:sum:amount" in ids and "trend:sum:amount:order_date:month" in ids
    assert "customer_email" not in json.dumps([item.columns for item in candidates])


def test_unconfirmed_meaning_offers_only_safe_tiles():
    _, _, brief, cards = brief_for(sales_csv())
    candidates = boards.enumerate_candidates(context_for(csv_table(sales_csv())), brief, cards)
    assert kinds(candidates) <= {"kpi", "category", "volume", "analyst"}
    assert all(
        item.request is None or item.request.aggregation.value == "count" for item in candidates
    )
    assert {item.card["analyst"] for item in candidates if item.card} <= boards.SAFE_ANALYSTS


def test_survey_without_dates_has_no_time_tiles():
    _, _, brief, cards = brief_for(survey_csv(), {"satisfaction": "score"})
    candidates = boards.enumerate_candidates(
        context_for(csv_table(survey_csv()), {"satisfaction": "score"}), brief, cards
    )
    assert brief["date_coverage"] is None
    assert not kinds(candidates) & {"trend", "volume"}
    assert "category:age_group" in {item.id for item in candidates}
    assert not any("respondent_id" in item.columns for item in candidates)


def test_iot_time_series_uses_a_daily_or_weekly_grain():
    units = {"temperature_c": "°C", "humidity": "%"}
    _, _, brief, cards = brief_for(iot_csv(), units)
    candidates = boards.enumerate_candidates(context_for(csv_table(iot_csv()), units), brief, cards)
    trends = [item for item in candidates if item.kind == "trend"]
    assert trends and all(item.request.period in {"day", "week"} for item in trends)


def test_ledger_with_negative_amounts_gets_no_share_tile():
    _, _, brief, cards = brief_for(ledger_csv(), {"amount": "USD"})
    candidates = boards.enumerate_candidates(
        context_for(csv_table(ledger_csv()), {"amount": "USD"}), brief, cards
    )
    amount = {item["name"]: item for item in brief["columns"]}["amount"]
    assert "has_negatives" in amount["flags"]
    assert "share" not in kinds(candidates)
    assert any(item.id.startswith("top:sum:amount:account") for item in candidates)


def build_tiles(service, analytics, brief, cards, context):
    candidates = boards.enumerate_candidates(context, brief, cards)
    picked, selection = asyncio.run(service._select(brief, candidates, context.private_goal))
    tiles, _ = asyncio.run(
        service._tiles(
            None,
            analytics.dataset,
            context,
            analytics.scope,
            analytics.table,
            candidates,
            picked,
            True,
        )
    )
    return candidates, tiles, selection


def test_no_model_uses_the_deterministic_pick_and_different_data_differs():
    units = {"amount": "PKR", "quantity": "units"}
    service, analytics, brief, cards = brief_for(sales_csv(), units)
    _, sales_tiles, selection = build_tiles(
        service, analytics, brief, cards, analytics.context
    )
    assert selection == {"route": boards.ROUTE, "fallback_reason": "not_configured"}
    assert boards.MIN_TILES <= len(sales_tiles) <= boards.MAX_TILES
    total = next(tile for tile in sales_tiles if tile["id"] == "kpi:sum:amount")
    frame = pd.read_csv(io.StringIO(sales_csv()), dtype=str, keep_default_na=False)
    assert Decimal(total["kpi"]["value"]) == sum(Decimal(v) for v in frame["amount"] if v != "N/A")
    assert all(tile["query_ids"] for tile in sales_tiles if tile["kind"] != "analyst")
    service_module._CACHE.clear()
    survey, survey_analytics, survey_brief, survey_cards = brief_for(survey_csv())
    _, survey_tiles, _ = build_tiles(
        survey, survey_analytics, survey_brief, survey_cards, survey_analytics.context
    )
    assert {tile["id"] for tile in sales_tiles}.isdisjoint(
        {tile["id"] for tile in survey_tiles} - {"kpi:rows"}
    )


def test_model_ranks_and_titles_candidates_but_never_numbers():
    units = {"amount": "PKR", "quantity": "units"}

    def reply(request):
        payload = json.loads(request.messages[1].content)
        ids = [item["id"] for item in payload["candidates"]][::-1][:6]
        assert "user0@example.test" not in request.messages[1].content
        return json.dumps(
            {
                "tiles": [
                    {"id": key, "title": "Useful view", "reason": "Fits the goal."} for key in ids
                ]
            }
        )

    model = ScriptedModel(reply)
    service, analytics, brief, cards = brief_for(sales_csv(), units, "grow amount", model)
    candidates, tiles, selection = build_tiles(service, analytics, brief, cards, analytics.context)
    assert selection == {"route": "scripted:test-model", "fallback_reason": None}
    assert [tile["id"] for tile in tiles] == [item.id for item in candidates][::-1][:6]
    assert {tile["title"] for tile in tiles} == {"Useful view"}


@pytest.mark.parametrize(
    "reply",
    [
        "not json",
        json.dumps({"tiles": [{"id": "made:up", "title": "x", "reason": "y"}] * 6}),
        json.dumps({"tiles": [{"id": "kpi:rows", "title": "Total is 999", "reason": "y"}]}),
        ValueError("boom"),
    ],
)
def test_invalid_model_replies_fall_back_to_the_fixed_score(reply):
    service, analytics, brief, cards = brief_for(
        sales_csv(), {"amount": "PKR"}, model=ScriptedModel(reply)
    )
    candidates = boards.enumerate_candidates(analytics.context, brief, cards)
    picked, selection = asyncio.run(service._select(brief, candidates, ""))
    assert selection["fallback_reason"] in {"invalid_response", "provider_error"}
    assert [key for key, _, _ in picked] == boards.deterministic_pick(candidates)


def test_number_in_title_is_rejected_unless_given():
    candidate = boards.Candidate("kpi:rows", "kpi", "Records", "Count.", 1, ())
    many = [candidate] + [
        boards.Candidate(f"c{index}", "kpi", "x", "y", 1, ()) for index in range(5)
    ]
    reply = {"tiles": [{"id": item.id, "title": "View", "reason": "Why"} for item in many]}
    assert len(boards.parse_selection(json.dumps(reply), many)) == 6
    reply["tiles"][0]["title"] = "Records grew 12%"
    with pytest.raises(ValueError):
        boards.parse_selection(json.dumps(reply), many)


def test_grain_follows_date_span():
    assert [boards.grain(days) for days in (10, 100, 400, 2000, 5000)] == [
        "day",
        "week",
        "month",
        "quarter",
        "year",
    ]


def test_brief_is_cached_per_source():
    service, analytics, _, _ = brief_for(sales_csv())
    executed = len(analytics.persisted)
    asyncio.run(service.brief(None, uuid4(), analytics.dataset, uuid4()))
    assert len(analytics.persisted) == executed
    assert service_module.cached_brief(analytics.context.view.sources) is not None


def test_planner_reads_the_cached_brief_without_totals_or_values():
    from execplus.application.services.intent_router import _describe_profile

    table = csv_table(sales_csv())
    context = context_for(table)
    assert _describe_profile(context).startswith("Observed profile metadata")
    _, analytics, _, _ = brief_for(sales_csv())
    text = _describe_profile(analytics.context)
    assert text.startswith("Dataset brief") and "never quote or calculate" in text
    assert '"sum"' not in text and "North" not in text and '"min"' in text
