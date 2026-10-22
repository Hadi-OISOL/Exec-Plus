"""Use case: Keeps the provider-free AI-response evaluation measured and repeatable.

What it does: Runs the labelled routing, model-output, grounding and binding cases and
pins the measured scores, known failures and zero unsafe acceptances.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "offline_responses",
    Path(__file__).resolve().parents[1] / "scripts/evaluate_offline_responses.py",
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


@pytest.fixture(scope="module")
def report():
    return asyncio.run(evaluation.evaluate())


def test_unsafe_model_outputs_and_ungrounded_summaries_are_never_accepted(report):
    summary = report["summary"]
    for category in ("routing", "model_output", "summary_grounding", "answer_binding"):
        assert summary[category]["false_accepts"] == 0, category
    assert summary["model_output"] == {
        "cases": 20,
        "passed": 20,
        "accuracy": 1.0,
        "failed_ids": [],
        "false_accepts": 0,
    }
    assert summary["answer_binding"]["passed"] == 5


def test_every_routed_calculation_matches_the_independent_decimal_oracle(report):
    assert report["summary"]["numeric_agreement"] == {"executed": 16, "agreeing": 16}
    literal = next(case for case in report["cases"] if case["id"] == "M18")
    assert literal["passed"] and literal["rows"] == [[None]]


def test_measured_routing_and_grounding_scores_and_known_failures(report):
    routing = report["summary"]["routing"]
    assert (routing["cases"], routing["passed"], routing["preferred"]) == (24, 23, 22)
    assert routing["accuracy"] >= 0.95
    assert routing["failed_ids"] == ["R20"]
    grounding = report["summary"]["summary_grounding"]
    assert (grounding["passed"], grounding["failed_ids"]) == (9, ["S09"])


def test_share_questions_total_the_measure_instead_of_averaging(report):
    share = next(case for case in report["cases"] if case["id"] == "R21")
    assert share["observed"] == {
        "kind": "numerical",
        "metric": "revenue",
        "aggregation": "sum",
        "group_by": ["region"],
    }
    assert share["numeric"]["agrees"]


def test_report_refuses_to_overwrite_and_rejects_unknown_manifests(tmp_path, monkeypatch):
    existing = tmp_path / "report.json"
    existing.write_text("{}")
    monkeypatch.setattr("sys.argv", ["evaluate", "--output", str(existing)])
    with pytest.raises(SystemExit, match="overwrite"):
        evaluation.main()
    assert existing.read_text() == "{}"
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"version": "other"}))
    with pytest.raises(ValueError, match="Unsupported"):
        asyncio.run(evaluation.evaluate(cases))
