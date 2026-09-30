"""Use case: Verifies offline candidate trials cannot bypass product evidence checks.

What it does: Exercises exact Parquet parity, fixed fictional judge inputs and malformed feedback.
"""

import importlib
import json
from pathlib import Path

import pytest

from execplus.application.contracts import ModelResponse
from execplus.domain.errors import ProviderUnavailableError


@pytest.fixture
def evaluations(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("evaluate_representations"), importlib.import_module(
        "evaluate_advisory_judge"
    )


def test_parquet_candidate_preserves_signed_decimals_missing_values_and_large_ids(evaluations):
    representations, _ = evaluations
    baseline = representations.storage_worker(101, "baseline", 1)
    parquet = representations.storage_worker(101, "parquet", 1)
    assert baseline["result"] == parquet["result"]
    assert int(parquet["result"][1][0][0]) > 9007199254740991
    assert parquet["derived_bytes"] > 0
    assert parquet["preparation_ms"] > 0


class JudgeModel:
    def __init__(self, payload=None, failure=False):
        self.payload = payload
        self.failure = failure
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        if self.failure:
            raise ProviderUnavailableError("Private endpoint details")
        return ModelResponse(json.dumps(self.payload), "fixture-model", "fixture", 20, 5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"issues": ["approve_access"], "evidence_ids": ["f1"]},
        {"issues": [], "evidence_ids": [], "answer": "100"},
        {"issues": ["missing_filter"], "evidence_ids": ["private-document"]},
        {"issues": ["missing_filter", "missing_filter"], "evidence_ids": ["f1"]},
        {"issues": {"missing_filter": True}, "evidence_ids": ["f1"]},
        [],
    ],
)
async def test_judge_rejects_malformed_feedback_without_free_form_output(evaluations, payload):
    _, judge = evaluations
    result = await judge.evaluate_case(JudgeModel(payload), "city-missing")
    assert result["status"] == "invalid"
    assert not result["passed"]
    assert result["issues"] == []
    assert "answer" not in result


@pytest.mark.asyncio
async def test_judge_outage_is_explicit_and_does_not_retry_or_leak_errors(evaluations):
    _, judge = evaluations
    model = JudgeModel(failure=True)
    result = await judge.evaluate_case(model, "city-missing")
    assert result["status"] == "unavailable"
    assert len(model.requests) == 1
    assert "Private endpoint" not in json.dumps(result)


@pytest.mark.asyncio
async def test_judge_only_accepts_fixed_fictional_ids_and_labels_injection_failure(evaluations):
    _, judge = evaluations
    model = JudgeModel({"issues": [], "evidence_ids": []})
    with pytest.raises(ValueError, match="fictional"):
        await judge.evaluate_case(model, "Private customer passage should not be submitted")
    assert model.requests == []
    result = await judge.evaluate_case(model, "injection")
    assert not result["passed"]
    assert result["expected"] == ["missing_filter"]
    assert "untrusted" in model.requests[0].messages[0].content
    assert "expected" not in model.requests[0].messages[-1].content
    assert judge.review_metadata(None)["reviewed"] is False


@pytest.mark.asyncio
async def test_judge_reports_false_alarms_and_misses_without_runtime_adoption(evaluations):
    _, judge = evaluations
    result = await judge.evaluate(
        JudgeModel({"issues": [], "evidence_ids": []}), {"reviewed": False}
    )
    assert result["missed_errors"] == 6
    assert result["false_alarms"] == 0
    assert result["input_tokens"] == 240
    assert result["output_tokens"] == 60
    assert not result["adopted"]
    assert result["runtime_answer_changes"] == 0


def review_record(judge):
    return {
        "scope": "synthetic-judge-label-review",
        "reviewer": "Fictional test reviewer",
        "reviewed_on": "2026-09-01",
        "approved_case_ids": list(judge.CASES),
        **judge.evidence_identity(),
    }


def test_review_is_bound_to_actual_labels_and_rubric(evaluations, tmp_path, monkeypatch):
    _, judge = evaluations
    path = tmp_path / "review.json"
    payload = review_record(judge)
    path.write_text(json.dumps(payload))
    metadata = judge.review_metadata(path)
    assert metadata["reviewed"]
    assert metadata["reviewer"] == "Fictional test reviewer"
    changed = dict(judge.CASES)
    changed["city-missing"] = (*changed["city-missing"][:2], "wrong_meaning")
    monkeypatch.setattr(judge, "CASES", changed)
    with pytest.raises(ValueError, match="labels"):
        judge.review_metadata(path)


@pytest.mark.parametrize(
    "patch",
    [
        {"rubric_sha256": "changed"},
        {"scope": "production"},
        {"reviewer": " "},
        {"reviewer": True},
        {"reviewed_on": "2099-01-01"},
        {"reviewed_on": "not-a-date"},
        {"reviewed_on": None},
        {"approved_case_ids": []},
    ],
)
def test_review_rejects_stale_incomplete_or_malformed_records(evaluations, tmp_path, patch):
    _, judge = evaluations
    path = tmp_path / "review.json"
    path.write_text(json.dumps({**review_record(judge), **patch}))
    with pytest.raises(ValueError, match="Review"):
        judge.review_metadata(path)


@pytest.mark.asyncio
async def test_report_keeps_old_evidence_and_explains_rejection(evaluations, tmp_path):
    _, judge = evaluations
    report = await judge.evaluate(
        JudgeModel({"issues": [], "evidence_ids": []}), {"reviewed": False}
    )
    assert report["decision"] == "do_not_adopt"
    assert "human_label_review_missing" in report["rejection_reasons"]
    assert "defect_label_recall_below_threshold" in report["rejection_reasons"]
    assert "spending_budget_not_approved" in report["rejection_reasons"]
    assert report["evidence_identity"] == judge.evidence_identity()
    path = tmp_path / "report.json"
    judge.write_report(path, report)
    previous = path.read_bytes()
    with pytest.raises(FileExistsError):
        judge.write_report(path, {"adopted": True})
    assert path.read_bytes() == previous


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        lambda cases: cases.pop(),
        lambda cases: cases.append(cases[0]),
        lambda cases: cases[0].update(expected=[]),
        lambda cases: cases[0].update(latency_ms=float("nan")),
        lambda cases: cases[0].update(input_tokens=-1),
        lambda cases: cases[0].update(status="ignored"),
        lambda cases: cases[0].update(issues=["approve_access"]),
        lambda cases: cases[0].update(passed=True),
    ],
)
async def test_scoring_refuses_missing_or_changed_observations(evaluations, mutation):
    _, judge = evaluations
    model = JudgeModel({"issues": [], "evidence_ids": []})
    cases = [await judge.evaluate_case(model, key) for key in judge.CASES]
    mutation(cases)
    with pytest.raises(ValueError):
        judge.summarize(cases, {"reviewed": False})


@pytest.mark.asyncio
async def test_judge_timeout_is_visible_without_repeating_call(evaluations, monkeypatch):
    _, judge = evaluations
    model = JudgeModel({"issues": [], "evidence_ids": []})

    async def timeout(awaitable, timeout):
        await awaitable
        raise judge.asyncio.TimeoutError

    monkeypatch.setattr(judge.asyncio, "wait_for", timeout)
    result = await judge.evaluate_case(model, "city-correct")
    assert result["status"] == "unavailable"
    assert not result["passed"]
    assert len(model.requests) == 1
