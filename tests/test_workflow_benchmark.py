"""Use case: Keeps local performance evidence repeatable and explicit.

What it does: Verifies identical retained input bytes, exact workload timing
calculations and refusal to overwrite earlier evidence or modified fixtures.
"""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "workflow_benchmark", Path(__file__).resolve().parents[1] / "scripts/benchmark_data_workflow.py"
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_benchmark_fixture_bytes_survive_rerun_and_refuse_changed_inputs(tmp_path):
    first = benchmark.fixture_bytes(tmp_path)
    second = benchmark.fixture_bytes(tmp_path)
    assert first == second and len(first[2]) == 3000
    (tmp_path / "sales.csv").write_bytes(b"user edited")
    with pytest.raises(ValueError, match="differs"):
        benchmark.fixture_bytes(tmp_path)
    assert (tmp_path / "sales.csv").read_bytes() == b"user edited"


def test_benchmark_reports_first_warm_serial_rate_and_checks_every_result(monkeypatch):
    moments = iter([0, 0.004, 1, 1.002, 2, 2.006, 3, 3.004])
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(moments))
    report = {"measurements": {}}
    checked = []
    assert benchmark.measure(report, "work", lambda: "exact", checked.append) == "exact"
    result = report["measurements"]["work"]
    assert result["first_ms"] == result["warm_median_ms"] == 4
    assert result["warm_ms"] == [2, 6, 4]
    assert result["warm_serial_operations_per_second"] == 250
    assert checked == ["exact"] * 4


def test_benchmark_refuses_existing_report_before_environment_or_infrastructure(tmp_path):
    output = tmp_path / "before.json"
    output.write_text("retained before")
    with pytest.raises(ValueError, match="retained"):
        benchmark.run(tmp_path, output, tmp_path / "fixtures")
    assert output.read_text() == "retained before"
