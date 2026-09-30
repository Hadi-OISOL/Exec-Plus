"""Use case: Measures eight concurrent demo users against the deployed application.

What it does: Checks analytics, hybrid model plans, citations and replay without logging secrets.
"""

import argparse
import asyncio
import json
import math
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

import httpx

QUESTIONS = (
    ("What is total revenue?", "10000"),
    ("What is total cost?", "2800"),
    ("What is the maximum revenue?", "4000"),
    ("What is the minimum revenue?", "1000"),
    ("What is average revenue?", "2500"),
    ("How many revenue values are there?", "4"),
    ("What is the sum of revenue where revenue is greater than 2000?", "7000"),
    ("What is the sum of cost where cost is greater than 500?", "2400"),
)


async def journey(
    client: httpx.AsyncClient, session: dict[str, Any], account: dict[str, str], number: int
) -> list[dict[str, object]]:
    headers = {"Authorization": f"Bearer {account['token']}"}
    wid, did, uid = (session[key] for key in ("workspace_id", "dataset_id", "upload_id"))
    dataset = f"/workspaces/{wid}/datasets/{did}"
    upload = f"{dataset}/uploads/{uid}"
    question, expected = QUESTIONS[number - 1]
    checks: list[dict[str, object]] = []

    async def request(method: str, path: str, stage: str, body: Any = None) -> Any:
        start = perf_counter()
        response = await client.request(method, path, headers=headers, json=body)
        checks.append(
            {
                "user": number,
                "stage": stage,
                "status": response.status_code,
                "latency_ms": round((perf_counter() - start) * 1000, 2),
            }
        )
        if response.status_code != 200:
            raise ValueError(f"{stage}: HTTP {response.status_code}")
        return response.json()

    try:
        me = await request("GET", "/auth/me", "sign_in")
        if me["email"] != account["email"]:
            raise ValueError("Identity mismatch")
        dashboard = await request("POST", upload + "/dashboard", "dashboard", {})
        if not dashboard["cards"]:
            raise ValueError("Missing dashboard cards")
        answer = await request(
            "POST", upload + "/ask", "model_question", {"question": question}
        )
        if Decimal(str(answer["value"])) != Decimal(expected):
            raise ValueError("Incorrect numerical result")
        query_id = answer["lineage"]["query_id"]
        replay = await request("POST", f"/workspaces/{wid}/queries/{query_id}/replay", "replay", {})
        if Decimal(str(replay["rows"][0][0])) != Decimal(expected):
            raise ValueError("Replay differs from source result")
        summary = await request("POST", upload + "/dashboard/summary", "summary", {})
        if not summary["summary"] or not summary["evidence_ids"]:
            raise ValueError("Summary lacks evidence")
        search = await request(
            "POST",
            dataset + "/knowledge/search",
            "document_search",
            {"query": "Who approves standard refunds?", "limit": 3},
        )
        if not search["passages"]:
            raise ValueError("Missing source passage")
        passage = search["passages"][0]
        if "The customer support lead approves standard refunds." not in passage["text"]:
            raise ValueError("Retrieved evidence does not answer the demo question")
        citation = await request(
            "GET",
            f"/workspaces/{wid}/documents/{passage['document_id']}/chunks/{passage['chunk_id']}",
            "citation",
        )
        if citation["text"] != passage["text"]:
            raise ValueError("Citation differs from the retrieved source")
        checks.append({"user": number, "stage": "complete", "passed": True})
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        checks.append({"user": number, "stage": "complete", "passed": False})
    return checks


async def evaluate(base_url: str, session: dict[str, Any], rounds: int) -> dict[str, Any]:
    if urlsplit(base_url).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Use a loopback address or SSH tunnel for the private demo")
    if session.get("scope") != "private-fictional-demo" or len(session["accounts"]) != 8:
        raise ValueError("Expected the eight-account fictional demo session file")
    results: list[dict[str, Any]] = []
    start = perf_counter()
    async with httpx.AsyncClient(base_url=base_url, timeout=90, trust_env=False) as client:
        for _ in range(rounds):
            batches = await asyncio.gather(
                *(
                    journey(client, session, account, number)
                    for number, account in enumerate(session["accounts"], 1)
                )
            )
            results.extend(item for batch in batches for item in batch)
    latencies = sorted(float(item["latency_ms"]) for item in results if "latency_ms" in item)
    return {
        "scope": "private-fictional-demo",
        "production_evidence": False,
        "concurrent_users": 8,
        "rounds": rounds,
        "journeys_passed": sum(item.get("passed") is True for item in results),
        "journeys_total": rounds * 8,
        "elapsed_seconds": round(perf_counter() - start, 2),
        "request_p95_ms": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
        "checks": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18401")
    parser.add_argument("--rounds", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    session = json.loads(args.sessions.read_text())
    result = asyncio.run(evaluate(args.base_url, session, args.rounds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}))
    if result["journeys_passed"] != result["journeys_total"]:
        parser.exit(1, "Some user journeys failed; inspect the sanitized report.\n")


if __name__ == "__main__":
    main()
