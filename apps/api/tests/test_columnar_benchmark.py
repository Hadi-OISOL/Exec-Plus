"""Use case: Runs the heavy 1M/10M-row columnar measurements on demand.

What it does: Skips unless EXECPLUS_RUN_BENCHMARKS=1; then generates synthetic CSVs, measures
ingest and queries, and requires every answer to match exact integer arithmetic.
"""

import os
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.skipif(
        os.environ.get("EXECPLUS_RUN_BENCHMARKS") != "1",
        reason="Set EXECPLUS_RUN_BENCHMARKS=1 to run heavy columnar measurements",
    ),
]


@pytest.mark.parametrize("rows", [1_000_000, 10_000_000])
def test_columnar_benchmark_is_exact(rows, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from benchmark_columnar import run

    report = run(rows, Path(os.environ.get("EXECPLUS_BENCHMARK_DIR", tmp_path)))
    assert report["conversion_errors"] == {}
    assert all(entry["exact"] for entry in report["queries"].values()), report
