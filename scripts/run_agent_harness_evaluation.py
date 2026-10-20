"""Run the frozen agent-harness corpus through an application adapter and score it.

The adapter command receives one synthetic case as JSON on stdin and must return one normalized
observation as JSON on stdout. The runner never stores raw prompts, responses, or credentials.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from evaluate_agent_harness_replays import load_corpus, score

ROOT = Path(__file__).resolve().parents[1]


def unavailable(case_id: str, latency_ms: float, reason: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "outcome": "refusal",
        "intent": f"adapter_{reason}",
        "tools": [],
        "filters": [],
        "values": [],
        "evidence_ids": [],
        "claims": [],
        "model_calls": 0,
        "latency_ms": latency_ms,
        "verified_cost": None,
    }


def run_case(
    command: list[str], dataset: dict[str, Any], case: dict[str, Any], timeout: float
) -> dict[str, Any]:
    request = {
        "version": "agent-harness-adapter-request-v1",
        "dataset": dataset,
        "case": case,
    }
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        latency = (time.perf_counter() - started) * 1000
        if completed.returncode != 0:
            return unavailable(case["id"], latency, "failed")
        if len(completed.stdout) > 1_000_000:
            return unavailable(case["id"], latency, "oversized")
        observation = json.loads(completed.stdout)
        if not isinstance(observation, dict) or observation.get("id") != case["id"]:
            return unavailable(case["id"], latency, "invalid")
        # Wall time is measured by this runner. The adapter cannot under-report it.
        observation["latency_ms"] = latency
        return observation
    except subprocess.TimeoutExpired:
        return unavailable(case["id"], timeout * 1000, "timeout")
    except (OSError, json.JSONDecodeError):
        return unavailable(case["id"], (time.perf_counter() - started) * 1000, "invalid")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path, default=ROOT / "docs/agent-harness-evaluation-corpus.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("offline_scripted", "hosted_synthetic"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--implementation", required=True)
    parser.add_argument("--case-timeout", type=float, default=120)
    parser.add_argument("adapter_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.adapter_command:
        parser.error("Pass an adapter command after --")
    if args.adapter_command[0] == "--":
        args.adapter_command.pop(0)
    if not args.adapter_command or not 0.1 <= args.case_timeout <= 300:
        parser.error("Adapter command and a 0.1-300 second timeout are required")
    try:
        corpus, digest = load_corpus(args.corpus)
        datasets = {item["id"]: item for item in corpus["datasets"]}
        observations = [
            run_case(args.adapter_command, datasets[item["dataset_id"]], item, args.case_timeout)
            for item in corpus["cases"]
        ]
        replay = {
            "version": "agent-harness-replay-v1",
            "evaluation_id": corpus["evaluation_id"],
            "corpus_sha256": digest,
            "run_id": args.run_id,
            "implementation": args.implementation,
            "mode": args.mode,
            "cases": observations,
        }
        result = score(corpus, digest, replay)
        output = args.output.resolve()
        if not output.is_relative_to(ROOT):
            raise ValueError("Output must stay inside the project")
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(output.relative_to(ROOT))],
            cwd=ROOT,
            check=False,
        )
        if ignored.returncode != 0:
            raise ValueError("Output must be a Git-ignored project directory")
        output.mkdir(parents=True, exist_ok=False)
        (output / "replay.json").write_text(json.dumps(replay, indent=2) + "\n")
        (output / "score.json").write_text(json.dumps(result, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"{result['passed_cases']}/{result['case_count']} cases passed ({result['mode']})")
    print(f"Evidence: {output.relative_to(ROOT)}")
    return 0 if result["passed_cases"] == result["case_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
