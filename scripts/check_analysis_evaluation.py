"""Use case: Repeats a fixed internal analytics failure-case evaluation.

What it does: Runs exact deduplicated regression nodes and retains failures, skips and timing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    title: str
    expected_behavior: str
    node_ids: tuple[str, ...]
    measurement_dimension: str = "behavioral_regression"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Manifest {name} must be nonempty text.")
    return value


def read_manifest(path: Path) -> tuple[dict[str, Any], tuple[EvaluationCase, ...]]:
    content = path.read_bytes()
    body = json.loads(content)
    if not isinstance(body, dict) or body.get("version") != "analysis-evaluation-cases-v1":
        raise ValueError("Unsupported evaluation manifest.")
    _text(body.get("evaluation_id"), "evaluation_id")
    _text(body.get("scope"), "scope")
    rows = body.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("The manifest must declare evaluation cases.")
    cases = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each manifest case must be an object.")
        nodes = row.get("node_ids")
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("Each case must name exact pytest node IDs.")
        for node in nodes:
            node = _text(node, "node_id")
            filename, separator, name = node.partition("::")
            source = (ROOT / filename).resolve()
            if (
                not separator
                or not name
                or "\n" in node
                or not filename.startswith(("apps/api/tests/", "tests/"))
                or not filename.endswith(".py")
                or not source.is_relative_to(ROOT)
                or not source.is_file()
            ):
                raise ValueError(f"Invalid pytest node ID: {node}")
        if len(set(nodes)) != len(nodes):
            raise ValueError("A case contains duplicate node IDs.")
        cases.append(
            EvaluationCase(
                _text(row.get("id"), "case id"),
                _text(row.get("title"), "title"),
                _text(row.get("expected_behavior"), "expected_behavior"),
                tuple(nodes),
                _text(row.get("measurement_dimension", "behavioral_regression"), "dimension"),
            )
        )
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique.")
    body["manifest_sha256"] = hashlib.sha256(content).hexdigest()
    return body, tuple(cases)


def junit_results(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    results = []
    for case in root.iter("testcase"):
        # Pytest's xunit2 report stores the repo-relative module plus exact parameterized name.
        module = case.get("classname", "").replace(".", "/")
        node_id = module + ".py::" + case.get("name", "")
        status = (
            "failed"
            if case.find("failure") is not None
            else "error"
            if case.find("error") is not None
            else "skipped"
            if case.find("skipped") is not None
            else "passed"
        )
        results.append(dict(node_id=node_id, status=status, seconds=float(case.get("time", "0"))))
    return results


def summarize(
    cases: tuple[EvaluationCase, ...], results: list[dict[str, Any]], returncode: int
) -> dict[str, Any]:
    selected = set(node for case in cases for node in case.node_ids)
    frequencies = Counter(result["node_id"] for result in results)
    by_node = {result["node_id"]: result for result in results}
    missing = sorted(selected - set(by_node))
    unexpected = sorted(set(by_node) - selected)
    duplicates = sorted(node for node, count in frequencies.items() if count > 1)
    case_reports = []
    for case in cases:
        checks = [
            by_node.get(node, dict(node_id=node, status="missing", seconds=0))
            for node in case.node_ids
        ]
        counts = Counter(check["status"] for check in checks)
        case_reports.append(
            dict(
                id=case.id,
                title=case.title,
                expected_behavior=case.expected_behavior,
                status="passed"
                if all(check["status"] == "passed" for check in checks)
                and not set(case.node_ids).intersection(duplicates)
                else "failed",
                passed=counts["passed"],
                selected=len(checks),
                seconds=round(sum(check["seconds"] for check in checks), 6),
                checks=checks,
            )
        )
    counts = Counter(result["status"] for result in results)
    dimensions = {}
    for dimension in sorted({case.measurement_dimension for case in cases}):
        dimension_nodes = {
            node
            for case in cases
            if case.measurement_dimension == dimension
            for node in case.node_ids
        }
        dimensions[dimension] = {
            "selected_checks": len(dimension_nodes),
            "passed_checks": sum(
                by_node.get(node, {}).get("status") == "passed" and frequencies[node] == 1
                for node in dimension_nodes
            ),
            "scope": "Fixed synthetic regression checks, not representative accuracy.",
        }
    passed = (
        returncode == 0
        and not missing
        and not unexpected
        and not duplicates
        and counts["passed"] == len(selected)
        and len(results) == len(selected)
    )
    return dict(
        status="passed" if passed else "failed",
        unique_tests=len(selected),
        recorded_tests=len(results),
        passed_tests=counts["passed"],
        failed_tests=counts["failed"],
        errors=counts["error"],
        skipped_tests=counts["skipped"],
        missing=missing,
        unexpected=unexpected,
        duplicate_results=duplicates,
        pytest_returncode=returncode,
        cases=case_reports,
        measurement_dimensions=dimensions,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "docs/analysis-evaluation-cases.json"
    )
    parser.add_argument("--output", type=Path, required=True, help="New ignored evidence directory")
    parser.add_argument("--timeout", type=int, default=900, help="Maximum total test seconds")
    args = parser.parse_args()
    if not os.environ.get("EXECPLUS_TEST_DATABASE_URL"):
        parser.error("Set EXECPLUS_TEST_DATABASE_URL; skipped integration checks are not accepted.")
    if not 1 <= args.timeout <= 3600:
        parser.error("--timeout must be between 1 and 3600 seconds.")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("--output must be an ignored directory inside this project.")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", str(output.relative_to(ROOT))], cwd=ROOT
    )
    if ignored.returncode != 0:
        parser.error("--output must be Git-ignored; evaluation reports stay local.")
    try:
        manifest, cases = read_manifest(args.manifest)
        output.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError) as failure:
        parser.error(str(failure))
    nodes = list(dict.fromkeys(node for case in cases for node in case.node_ids))
    xml_path = output / "junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "junit_family=xunit2",
        "--junitxml=" + str(xml_path),
        *nodes,
    ]
    started = time.monotonic()
    error = None
    try:
        with (output / "pytest.log").open("w") as log:
            completed = subprocess.run(
                command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout
            )
        returncode = completed.returncode
    except subprocess.TimeoutExpired:
        returncode, error = 124, "The declared evaluation deadline elapsed."
    try:
        results = junit_results(xml_path)
    except (OSError, ET.ParseError, ValueError):
        results = []
        error = error or "The pytest JUnit report is missing or invalid; no passes inferred."
    report = dict(
        version="analysis-evaluation-result-v1",
        evaluation_id=manifest["evaluation_id"],
        scope=manifest["scope"],
        representative_model_quality=False,
        manifest_sha256=manifest["manifest_sha256"],
        elapsed_seconds=round(time.monotonic() - started, 6),
        runner_error=error,
        **summarize(cases, results, returncode),
    )
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{report['status']}: {report['passed_tests']}/{report['unique_tests']} exact checks, "
        f"{len(cases)} fixed cases, {report['skipped_tests']} skipped."
    )
    print(f"Evidence: {output.relative_to(ROOT) / 'summary.json'}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
