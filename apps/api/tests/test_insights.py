"""Use case: Verifies the automatic analyst team on the reference farm file and small fixtures.

What it does: Checks each analyst against independent recomputation, the cross-checker,
selection-only narration and the assembled insights-v1 payload without PostgreSQL.
"""

import asyncio
import csv
import json
from collections import Counter
from contextlib import nullcontext
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from scipy import stats

from execplus.application.contracts import ModelResponse
from execplus.application.services.insights import build_insights, narrate
from execplus.domain import insights as engine
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import WorkspaceScope
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics

REFERENCE = Path(__file__).resolve().parents[3] / "data/reference-data/test_100rows.csv"
STATISTICS = ScipyPatternStatistics()


def table_from(content: str) -> TableData:
    rows = list(csv.reader(content.splitlines()))
    return TableData(tuple(rows[0]), tuple(tuple(row) for row in rows[1:]))


@pytest.fixture(scope="module")
def farm() -> TableData:
    if not REFERENCE.exists():
        pytest.skip("The ignored reference farm file is not available")
    return table_from(REFERENCE.read_text())


def context_for(table: TableData) -> DescriptionContext:
    metadata = profile(table)
    return DescriptionContext("farm", metadata, dataset_view(metadata), None, "inferred")


def scope_for() -> tuple[WorkspaceScope, object]:
    dataset = uuid4()
    return WorkspaceScope(uuid4(), uuid4(), frozenset({"owner"}), frozenset({dataset})), dataset


class FakeService:
    def __init__(self, table: TableData, context: DescriptionContext | None = None) -> None:
        self.table, self.context = table, context or context_for(table)
        self.scope, self.dataset = scope_for()
        self.executor = DuckDBQueryExecutor(15, 256)
        self.persisted: list = []
        self.rechecked: list = []

    def descriptive_snapshot(self, actor, workspace_id, dataset_id, upload_id):
        return self.context, self.table, self.scope

    def uow(self):
        return nullcontext(None)

    def _authorize(self, repo, actor, workspace_id):
        return None

    def _persist(self, actor, lineage):
        self.persisted.append(lineage)

    def recheck_description(self, actor, workspace_id, dataset_id, upload_id, sources):
        self.rechecked.append(sources)


def payload(table: TableData, model=None, context=None) -> tuple[dict, FakeService]:
    service = FakeService(table, context)
    body = asyncio.run(
        build_insights(
            service,
            object(),
            service.scope.workspace_id,
            service.dataset,
            uuid4(),
            statistics=STATISTICS,
            model=model,
        )
    )
    return body, service


def raw(table: TableData, name: str) -> list[str]:
    index = table.headers.index(name)
    return [row[index] for row in table.rows]


def cards(body: dict) -> dict[str, dict]:
    return {card["id"]: card for card in body["insights"]}


def test_field_selection_skips_identifiers_and_bounds_fields(farm):
    selection = engine.select_fields(context_for(farm))
    assert "id" not in selection.columns
    assert len(selection.measures) == engine.MAX_MEASURES
    assert len(selection.categories) == engine.MAX_CATEGORIES
    assert any("first 6 ranked measures" in item for item in selection.limitations)


def test_reference_file_briefing_is_fully_cross_checked(farm):
    body, service = payload(farm)
    assert body["version"] == "insights-v1"
    assert body["narration"] == {"route": engine.ROUTE, "fallback_reason": "not_configured"}
    assert body["cross_check"]["dropped"] == []
    analysts = Counter(card["analyst"] for card in body["insights"])
    assert analysts == {
        "quality": 1,
        "composition": 3,
        "distribution": 3,
        "segment": 3,
        "relationship": 1,
    }
    for card in body["insights"]:
        assert card["summary"] in card["statements"]
        assert card["cross_check"]["status"] == "verified"
        assert all(check["agrees"] for check in card["cross_check"]["checks"])
        assert card["actions"]
    sql_checks = sum(
        1
        for card in body["insights"]
        for check in card["cross_check"]["checks"]
        if check["query_id"]
    )
    assert len(service.persisted) == 1 + sql_checks <= 1 + engine.MAX_CHECKS
    assert service.persisted[0].aggregation == "analysis"
    assert {lineage.model_route for lineage in service.persisted} == {engine.ROUTE}
    assert {lineage.receipt["outcome"] for lineage in service.persisted} == {"executed"}
    assert service.rechecked == [service.context.view.sources]
    kpis = {item["id"]: item["value"] for item in body["kpis"]}
    assert kpis == {
        "rows": "100",
        "columns": "20",
        "measures": "6",
        "categories": "4",
        "completeness": "100.0",
        "duplicate_rows": "0",
    }
    assert 1 <= len(body["next_actions"]) <= 5
    assert json.loads(json.dumps(body)) == body


def test_composition_counts_and_shares_match_independent_counts(farm):
    body, _ = payload(farm)
    card = cards(body)["composition:Crop_Type"]
    expected = Counter(raw(farm, "Crop_Type"))
    rows = card["chart"]["rows"]
    assert card["chart"]["type"] == "donut"
    assert {row["label"]: int(row["count"]) for row in rows} == expected
    assert sum(Decimal(row["percent"]) for row in rows) == Decimal("100.0")
    leader, count = sorted(expected.items(), key=lambda item: (-item[1], item[0]))[0]
    assert card["summary"].startswith(f"{leader} is the largest Crop_Type group with {count}")


def test_two_value_category_renders_as_pie_with_other_slice_rules():
    table = table_from(
        "kind,value\n" + "".join(f"{'A' if i % 3 else 'B'},{i}\n" for i in range(30))
    )
    card = cards(payload(table)[0])["composition:kind"]
    assert card["chart"]["type"] == "pie"
    assert [row["label"] for row in card["chart"]["rows"]] == ["A", "B"]


def test_distribution_summary_and_histogram_match_raw_values(farm):
    body, _ = payload(farm)
    card = cards(body)["distribution:Previous_Irrigation_mm"]
    values = [Decimal(value) for value in raw(farm, "Previous_Irrigation_mm")]
    evidence = {item["label"]: item["value"] for item in card["evidence"]}
    assert Decimal(evidence["Average"]) == (sum(values) / len(values)).quantize(Decimal("1e-12"))
    assert Decimal(evidence["Minimum"]) == min(values)
    assert Decimal(evidence["Maximum"]) == max(values)
    assert Decimal(evidence["Median"]) == (sorted(values)[49] + sorted(values)[50]) / 2
    histogram = card["chart"]["rows"]
    assert card["chart"]["type"] == "histogram"
    assert sum(int(row["count"]) for row in histogram) == len(values)
    assert histogram[0]["start"] == evidence["Minimum"]
    assert histogram[-1]["end"] == evidence["Maximum"]
    for row in histogram[:-1]:
        inside = [v for v in values if Decimal(row["start"]) <= v < Decimal(row["end"])]
        assert len(inside) == int(row["count"])


def test_segment_gap_matches_independent_group_means(farm):
    body, _ = payload(farm)
    card = next(card for card in body["insights"] if card["analyst"] == "segment")
    _, measure, category = card["id"].split(":")
    groups: dict[str, list[Decimal]] = {}
    for group, value in zip(raw(farm, category), raw(farm, measure), strict=True):
        groups.setdefault(group, []).append(Decimal(value))
    means = {
        group: (sum(values) / len(values)).quantize(Decimal("1e-12"))
        for group, values in groups.items()
        if len(values) >= engine.MIN_GROUP
    }
    evidence = {item["label"]: item["value"] for item in card["evidence"]}
    top = max(means, key=means.__getitem__)
    bottom = min(means, key=means.__getitem__)
    assert evidence["Highest group"] == top and evidence["Lowest group"] == bottom
    assert Decimal(evidence["Gap"]) == means[top] - means[bottom]
    assert {row["label"] for row in card["chart"]["rows"]} == set(means)
    assert "does not show a cause" in " ".join(card["statements"])


def test_relationship_heatmap_matches_scipy_rank_scores(farm):
    body, _ = payload(farm)
    card = cards(body)["relationship:measures"]
    measures = engine.select_fields(context_for(farm)).measures
    rows = card["chart"]["rows"]
    assert card["chart"]["type"] == "heatmap"
    assert len(rows) == len(measures) ** 2
    for row in rows:
        left = [float(value) for value in raw(farm, row["x"])]
        right = [float(value) for value in raw(farm, row["y"])]
        expected = 1.0 if row["x"] == row["y"] else stats.spearmanr(left, right).statistic
        assert abs(float(row["score"]) - expected) <= 1e-6
    assert [check["method"] for check in card["cross_check"]["checks"]] == [
        "python-average-rank-pearson",
        "python-pearson",
    ]


def test_outlier_analyst_flags_extreme_rows_with_exact_boundaries():
    values = [10, 11, 12, 13, 11, 12, 10, 13, 12, 11, 12, 500]
    table = table_from("site,weight\n" + "".join(f"S{i % 2},{v}\n" for i, v in enumerate(values)))
    card = cards(payload(table)[0])["outlier:weight"]
    assert card["chart"]["type"] == "box"
    assert card["chart"]["outliers"] == [{"value": "500", "count": "1"}]
    evidence = {item["label"]: item["value"] for item in card["evidence"]}
    assert evidence["Unusual rows"] == "1"
    action = card["actions"][0]
    assert action["kind"] == "investigate_outliers"
    assert action["payload"] == {
        "type": "anomalies",
        "metric": "weight",
        "filters": [{"column": "weight", "operator": "gte", "value": "500"}],
    }
    assert card["cross_check"]["checks"][0]["secondary"] == "1"


def test_quality_analyst_reports_missing_duplicates_and_negatives():
    table = table_from("city,amount,flag\nA,5,x\nA,5,x\nB,,x\nC,-2,x\nD,4,x\n")
    body, _ = payload(table)
    card = cards(body)["quality:file"]
    text = " ".join(card["statements"])
    assert "1 cells are empty; amount has the most" in text
    assert "1 rows repeat an earlier row" in text
    assert "flag has the same value in every row" in text
    assert "amount has 1 negative values" in text
    checks = {check["label"]: check for check in card["cross_check"]["checks"]}
    assert checks["Nonempty amount values"]["secondary"] == "4"
    assert checks["Repeated rows"]["secondary"] == "1"
    assert checks["Negative amount values"]["secondary"] == "1"
    assert {action["kind"] for action in card["actions"]} >= {
        "check_missing",
        "review_duplicates",
    }
    assert body["insights"][0]["id"] == "quality:file"


def test_quality_analyst_flags_case_and_space_label_variants_without_merging():
    table = table_from(
        "store,sales\nStore 1,5\n store 1 ,3\nStore 2,4\nStore 1,2\nStore 2,7\nStore 3,1\n"
    )
    body, _ = payload(table)
    card = cards(body)["quality:file"]
    text = " ".join(card["statements"])
    assert "store has labels that differ only by capital letters or spaces" in text
    assert "('Store 1' and 'store 1')" in text and "Nothing is merged automatically" in text
    labels = next(action for action in card["actions"] if action["kind"] == "review_labels")
    assert labels["payload"] == {"type": "prepare", "column": "store"}


def test_cross_checker_drops_disagreeing_or_unchecked_cards():
    good = engine.Check("Rows", "3", "count", secondary="3")
    wrong = engine.Check("Rows", "3", "count", secondary="4")
    close = engine.Check("Score", "0.5", "statistic", secondary=repr(0.5 + 1e-9))
    far = engine.Check("Score", "0.5", "statistic", secondary="0.51")
    base = engine.Card("a", "quality", "t", ("s",), (), None, (good,), (), 0.1)
    kept, dropped = engine.cross_check(
        [
            base,
            replace(base, id="b", checks=(good, wrong)),
            replace(base, id="c", checks=(close,)),
            replace(base, id="d", checks=(far,)),
            replace(base, id="e", checks=(engine.Check("Rows", "3", "count"),)),
        ]
    )
    assert [card.id for card in kept] == ["a", "c"]
    assert [item["id"] for item in dropped] == ["b", "d", "e"]
    assert "could not run" in dropped[2]["reason"]


def test_failed_sql_check_removes_card_instead_of_showing_unverified_number(monkeypatch, farm):
    original = engine.check_value

    def tampered(check, rows):
        value = original(check, rows)
        return "999" if check.label.startswith("Rows where Crop_Type") else value

    monkeypatch.setattr("execplus.application.services.insights.check_value", tampered)
    body, _ = payload(farm)
    assert "composition:Crop_Type" not in cards(body)
    assert body["cross_check"]["dropped"][0]["id"] == "composition:Crop_Type"


class Model:
    def __init__(self, reply) -> None:
        self.reply, self.requests = reply, []

    async def complete(self, request):
        self.requests.append(request)
        if isinstance(self.reply, BaseException):
            raise self.reply
        if self.reply == "slow":
            await asyncio.sleep(1)
        content = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        return ModelResponse(content, "deepseek-test", "deepseek")


def sample_cards(farm) -> list[engine.Card]:
    empty = engine.Selection((), (), (), {}, ())
    built, _ = engine.analyse(context_for(farm), empty, (), (), STATISTICS.correlations, {})
    distribution = engine.Card(
        "distribution:x",
        "distribution",
        "x",
        ("first", "second"),
        (),
        None,
        (),
        (engine.action("compare_groups", "Compare x across y", "x:y", type="ask", question="q"),),
        0.5,
    )
    return [*built, distribution]


def test_narrator_only_reorders_and_selects_server_statements(farm):
    found = sample_cards(farm)
    ordered = engine.deterministic_order(found)
    ids = {card.id: f"I{index}" for index, card in enumerate(ordered, 1)}
    reply = {
        "order": [ids["quality:file"], ids["distribution:x"]],
        "headlines": {ids["quality:file"]: "S2", ids["distribution:x"]: "S2"},
        "actions": ["A1"],
    }
    model = Model(reply)
    arranged, actions, narration = asyncio.run(narrate(model, found))
    assert [card.id for card, _ in arranged] == ["quality:file", "distribution:x"]
    assert arranged[1][0].body(arranged[1][1])["summary"] == "second"
    assert narration == {"route": "deepseek:deepseek-test", "fallback_reason": None}
    assert actions[0]["kind"] in engine.ACTION_KINDS
    prompt = model.requests[0].messages[1].content
    assert "first" in prompt and "Compare x across y" in prompt


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ({"order": ["I1"], "headlines": {"I1": "S1"}, "actions": ["A1"]}, "invalid_response"),
        (
            {"order": ["I2", "I1"], "headlines": {"I1": "S1", "I2": "S9"}, "actions": ["A1"]},
            "invalid_response",
        ),
        (
            {
                "order": ["I2", "I1"],
                "headlines": {"I1": "S1", "I2": "S1"},
                "actions": ["A1"],
                "summary": "Revenue rose 40%",
            },
            "invalid_response",
        ),
        ("The best insight is 42", "invalid_response"),
        (ProviderUnavailableError("off"), "model_unavailable"),
        (RuntimeError("boom"), "provider_error"),
        ("slow", "timeout"),
    ],
)
def test_narrator_falls_back_to_deterministic_structure(farm, reply, reason):
    found = sample_cards(farm)
    arranged, actions, narration = asyncio.run(narrate(Model(reply), found, timeout=0.05))
    assert [card.id for card, _ in arranged] == [
        card.id for card in engine.deterministic_order(found)
    ]
    assert all(headline == 0 for _, headline in arranged)
    assert actions == engine.default_next_actions(engine.deterministic_order(found))
    assert narration == {"route": engine.ROUTE, "fallback_reason": reason}


def test_unconfirmed_saved_meaning_blocks_analyst_calculations(farm):
    context = context_for(farm)
    view = replace(context.view, sources=({"upload_id": "u", "understanding_id": "x"},))
    blocked = replace(context, view=view, state="needs_review")
    body, service = payload(farm, context=blocked)
    assert body["insights"] == [] and service.persisted == []
    assert "Review and confirm Data understanding" in body["limitations"][0]
    assert {item["id"]: item["value"] for item in body["kpis"]}["measures"] == "0"


def test_reserved_word_field_is_skipped_without_losing_the_briefing():
    table = table_from("site,load,weight\n" + "".join(f"S{i % 2},{i},{i}\n" for i in range(30)))
    body, _ = payload(table)
    assert "distribution:weight" in cards(body) and "distribution:load" not in cards(body)
    assert "quality:file" in cards(body)
    assert any("reserved query word" in item for item in body["limitations"])


def test_large_files_return_limits_without_analysis():
    table = TableData(("value",), tuple((str(i),) for i in range(engine.MAX_ROWS + 1)))
    body, service = payload(table)
    assert body["insights"] == [] and service.persisted == []
    assert "50,000 rows" in body["limitations"][0]


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("9.291538461538", "9.29"),
        ("81.965", "81.96"),
        ("0.791111111111", "0.791"),
        ("0.0012345", "0.00123"),
        ("-2.675", "-2.68"),
        ("0", "0"),
        ("1500", "1500"),
    ],
)
def test_statement_numbers_use_readable_half_even_rounding(value, shown):
    assert engine._readable(Decimal(value)) == shown


def test_statements_are_readable_while_evidence_and_checks_stay_exact(farm):
    card = cards(payload(farm)[0])["segment:Field_Area_hectare:Crop_Type"]
    evidence = {item["label"]: item["value"] for item in card["evidence"]}
    assert evidence["Highest average"] == "9.291538461538"
    assert "(9.29)" in card["summary"] and "9.2915" not in card["summary"]
    assert card["chart"]["rows"][0]["value"] == "9.291538461538"
    assert card["cross_check"]["checks"][0]["primary"] == "9.291538461538"
