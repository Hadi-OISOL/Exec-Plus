"""Use case: Keeps fixed offline evaluation measurements honest.

What it does: Counts distinct checks by dimension, preserves failures/skips and
refuses missing, unexpected or duplicate executions instead of inferring success.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "analysis_evaluation", ROOT / "scripts/check_analysis_evaluation.py"
)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def test_dimensions_count_unique_fixed_checks_without_representative_accuracy_claim():
    cases = (
        runner.EvaluationCase("a", "Numerical", "exact", ("one", "two"), "numerical_correctness"),
        runner.EvaluationCase("b", "Numerical again", "exact", ("one",), "numerical_correctness"),
        runner.EvaluationCase("c", "Citations", "bound", ("three",), "source_citation_validity"),
    )
    result = runner.summarize(
        cases,
        [
            {"node_id": node, "status": "passed", "seconds": 0.01}
            for node in ("one", "two", "three")
        ],
        0,
    )
    assert result["status"] == "passed" and result["unique_tests"] == 3
    numerical = result["measurement_dimensions"]["numerical_correctness"]
    assert numerical["passed_checks"] == numerical["selected_checks"] == 2
    assert "not representative accuracy" in numerical["scope"]


@pytest.mark.parametrize(
    "status", ["failed", "error", "skipped", "missing", "duplicate", "unexpected"]
)
def test_dimensions_never_hide_nonpassing_or_malformed_runs(status):
    case = runner.EvaluationCase("a", "Numerical", "exact", ("one",), "numerical_correctness")
    results = [{"node_id": "one", "status": status, "seconds": 0}]
    if status == "missing":
        results = []
    elif status == "duplicate":
        results = [{"node_id": "one", "status": "passed", "seconds": 0}] * 2
    elif status == "unexpected":
        results = [{"node_id": "other", "status": "passed", "seconds": 0}]
    result = runner.summarize((case,), results, 0)
    assert result["status"] == "failed"
    assert result["measurement_dimensions"]["numerical_correctness"]["passed_checks"] == 0


def test_new_evaluation_preserves_existing_named_cases_and_all_five_dimensions():
    _, previous = runner.read_manifest(ROOT / "docs/next-batch-evaluation-cases.json")
    body, current = runner.read_manifest(ROOT / "docs/two-phase-evaluation-cases.json")
    assert current[: len(previous)] == previous
    assert {case.measurement_dimension for case in current} >= {
        "numerical_correctness",
        "source_citation_validity",
        "unsupported_claim_detection",
        "access_control",
        "replay_consistency",
    }
    assert "does not measure live provider" in body["scope"]
