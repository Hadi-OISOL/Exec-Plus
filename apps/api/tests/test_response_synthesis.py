"""Check semantic/numerical claim closure, immutable evidence, and bounded fallback."""

import asyncio
import copy
import json
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.conversation import EvidenceAnswer
from execplus.application.services.response_synthesis import (
    ResponseSynthesisService,
    build_fact_packet,
)
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer
from execplus.domain.response_synthesis import render_selection, validate_saved_narrative


def metric(aggregation="sum", name="Revenue"):
    lineage = CalculationLineage(
        uuid4(), uuid4(), uuid4(), "Sales", 6, name, aggregation, (), ("Region = West",), "SELECT 1"
    )
    return VerifiedMetricAnswer(name, Decimal("9007199254740993.000001"), lineage)


def selection(packet):
    return json.dumps({"selections": [{"id": s.id, "variant": 0} for s in packet.statements]})


class Model:
    def __init__(self, content=None, error=None, delay=0):
        self.content, self.error, self.delay = content, error, delay
        self.calls = 0

    async def complete(self, request):
        self.calls += 1
        self.request = request
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return ModelResponse(self.content, "fake", "test")


def test_exact_numbers_scope_and_immutable_input():
    answer = metric()
    before = copy.deepcopy(answer)
    packet = build_fact_packet(answer)
    body = render_selection(packet)
    assert "9007199254740993.000001" in str(body)
    assert "Region = West" in str(body)
    assert "USD" not in str(body)
    assert validate_saved_narrative(packet, body)
    assert answer == before
    changed = build_fact_packet(replace(answer, value=Decimal("1")))
    assert not validate_saved_narrative(changed, body)


@pytest.mark.parametrize(
    "aggregation,name,expected",
    [
        ("count", "*", "matching records"),
        ("count", "Revenue", 'nonmissing values of "Revenue"'),
        ("avg", "Revenue", 'average of "Revenue"'),
    ],
)
def test_aggregation_semantics(aggregation, name, expected):
    assert expected in str(render_selection(build_fact_packet(metric(aggregation, name))))


@pytest.mark.parametrize(
    "bad",
    [
        {},
        [],
        {"selections": []},
        {"selections": [{"id": "F1", "variant": 0}, {"id": "F1", "variant": 0}]},
        {"selections": [{"id": "F1", "variant": True}, {"id": "F2", "variant": 0}]},
        {"selections": [{"id": "F1", "variant": 99}, {"id": "F2", "variant": 0}]},
        {"selections": [{"id": "F1", "variant": 0}, {"id": "unknown", "variant": 0}]},
        {
            "selections": [{"id": "F1", "variant": 0}, {"id": "F2", "variant": 0}],
            "prose": "Revenue caused growth by 9007199254740993.000001",
        },
    ],
)
@pytest.mark.asyncio
async def test_invalid_or_causal_prose_falls_back(bad):
    packet = build_fact_packet(metric())
    model = Model(json.dumps(bad))
    result = await ResponseSynthesisService(model).compose(packet, "Why?")
    assert result.reason == "invalid_response"
    assert result.body() == render_selection(packet)
    assert model.calls == 1


@pytest.mark.asyncio
async def test_valid_reordering_and_variant_preserve_all_evidence():
    packet = build_fact_packet(metric())
    model = Model(
        '{"selections":[{"id":"F2","variant":1},{"id":"F1","variant":0},{"id":"F3","variant":0}]}'
    )
    result = await ResponseSynthesisService(model).compose(packet, "Explain simply")
    assert result.reason == "selected"
    assert validate_saved_narrative(packet, result.body())
    assert "comes to" in result.body()["segments"][0]["text"]


@pytest.mark.parametrize(
    "error,reason",
    [
        (ProviderUnavailableError("private details"), "unavailable"),
        (IngestionError("job_budget", "limit", 422), "budget"),
    ],
)
@pytest.mark.asyncio
async def test_expected_failure_has_deterministic_fallback(error, reason):
    packet = build_fact_packet(metric())
    result = await ResponseSynthesisService(Model(error=error)).compose(packet, "Explain")
    assert result.reason == reason
    assert result.body() == render_selection(packet)


@pytest.mark.asyncio
async def test_timeout_and_disabled_model():
    packet = build_fact_packet(metric())
    result = await ResponseSynthesisService(Model(delay=1), timeout=0.001).compose(
        packet, "Explain"
    )
    assert result.reason == "timeout"
    assert (await ResponseSynthesisService(None).compose(packet, "Explain")).reason == "disabled"


@pytest.mark.parametrize(
    "error", [asyncio.CancelledError(), IngestionError("not_found", "no", 404)]
)
@pytest.mark.asyncio
async def test_cancellation_and_authorization_failure_propagate(error):
    with pytest.raises(type(error)):
        await ResponseSynthesisService(Model(error=error)).compose(
            build_fact_packet(metric()), "Explain"
        )


def test_row_preview_does_not_claim_ranking_or_drop_missing_and_ties():
    lineage = replace(metric().lineage, aggregation="rows")
    result = QueryResult(
        lineage.query_id,
        ("ID", "Revenue"),
        (("a", None), ("b", Decimal("2.00")), ("c", Decimal("2.00")), ("d", Decimal("1.00"))),
        6,
        5,
    )
    body = render_selection(build_fact_packet((result, lineage)))
    text = str(body)
    assert "missing cell" in text
    assert result.rows[1][1] == result.rows[2][1] == Decimal("2.00")
    assert "5 records match" in text and "4 are returned" in text
    assert "does not by itself imply importance" in text
    assert build_fact_packet((replace(result, query_id=uuid4()), lineage)) is None


def test_document_quote_attribution_and_conflict_cannot_be_omitted():
    citation = dict(chunk_id=str(uuid4()), name="Policy", text="The policy allows 10 days.")
    answer = EvidenceAnswer(
        "textual", None, (citation,), "policy", "conflicting", ("Versions differ.",), "fake", ()
    )
    packet = build_fact_packet(answer)
    text = str(render_selection(packet))
    assert "source quotations" in text and "sources conflict" in text
    assert citation["text"] in text
    assert "Versions differ" in text
    body = render_selection(packet)
    body["segments"].pop()
    assert not validate_saved_narrative(packet, body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "The same value proves causation."),
        ("kind", "causal"),
        ("evidence_ids", ["foreign"]),
    ],
)
def test_replay_rejects_modified_claims_and_evidence(field, value):
    packet = build_fact_packet(metric())
    body = render_selection(packet)
    body["segments"][0][field] = value
    assert not validate_saved_narrative(packet, body)


def test_oversized_source_labels_do_not_send_model_packet():
    assert build_fact_packet(metric(name="x" * 20000)) is None


def test_cohort_keeps_filters_units_missingness_and_no_causal_explanation():
    from execplus.application.services.intent_router import PatternAnswer

    evidence = dict(
        query_id=str(uuid4()),
        request={"filters": [{"column": "Year", "value": "2025"}]},
        result=dict(
            version="cohort-comparison-v1",
            target={"column": "Outcome", "value": "Ready"},
            coverage=dict(target_rows=12, other_rows=13, missing_target_rows=1),
            numeric=[
                dict(
                    column="Yield",
                    unit="kg",
                    status="compared",
                    target_mean="3.000000000001",
                    other_mean="2.000000000001",
                    difference="1.000000000000",
                )
            ],
        ),
    )
    packet = build_fact_packet(PatternAnswer(evidence))
    body = render_selection(packet)
    text = str(body)
    assert "3.000000000001 kg" in text
    assert "1.000000000000 kg" in text
    assert "2025" in text and "Year" in text
    assert "missing label" in text and "excluded separately" in text
    assert "do not show what caused" in text
    assert validate_saved_narrative(packet, body)


@pytest.mark.parametrize("unit", ["USD", "%", "kg"])
def test_confirmed_units_preserve_value_and_cannot_be_swapped_on_replay(unit):
    answer = metric()
    packet = build_fact_packet(answer, units={str(answer.lineage.query_id): unit})
    body = render_selection(packet)
    assert f"9007199254740993.000001 {unit}" in str(body)
    assert "no unit is inferred" not in str(body)
    changed = build_fact_packet(answer, units={str(answer.lineage.query_id): "other"})
    assert not validate_saved_narrative(changed, body)


@pytest.mark.parametrize("value", [None, True, float("nan"), Decimal("Infinity")])
def test_invalid_scalar_never_becomes_a_claim(value):
    assert build_fact_packet(replace(metric(), value=value)) is None


def test_record_columns_do_not_inherit_a_metric_unit():
    lineage = replace(metric().lineage, aggregation="rows")
    result = QueryResult(
        lineage.query_id,
        ("Region", "Revenue", "Weight"),
        (("West", Decimal("2.00"), Decimal("8.00")),),
        6,
        1,
    )
    body = render_selection(
        build_fact_packet((result, lineage), units={str(lineage.query_id): "USD"})
    )
    assert "USD" not in str(body)
    assert "2.00" not in str(body) and "8.00" not in str(body)
    assert result.rows[0] == ("West", Decimal("2.00"), Decimal("8.00"))


def test_grouped_aggregate_applies_verified_unit_only_to_value():
    lineage = replace(metric().lineage, grouping=("Region",))
    result = QueryResult(lineage.query_id, ("Region", "__value"), (("West", Decimal("2.00")),), 6)
    body = render_selection(
        build_fact_packet((result, lineage), units={str(lineage.query_id): "USD"})
    )
    assert "2.00 USD" in str(body)
    assert "West USD" not in str(body)


def test_data_only_causal_limit_is_mandatory_without_document_citations():
    data = metric()
    answer = EvidenceAnswer(
        "mixed",
        data,
        (),
        "",
        "data",
        ("These totals do not establish a causal explanation.",),
        "fake",
        (),
    )
    packet = build_fact_packet(answer)
    body = render_selection(packet)
    segment = body["segments"][-1]
    assert segment["text"] == answer.limitations[0]
    assert segment["kind"] == "limitation"
    assert segment["evidence_ids"] == [str(data.lineage.query_id)]
    assert validate_saved_narrative(packet, body)
    body["segments"].pop()
    assert not validate_saved_narrative(packet, body)
