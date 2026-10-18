"""Root-only hosted harness check using new fictional accounts and fixed tasks.

The script records calculation/context correctness separately from verified-narrative
selection. It never stores passwords or bearer tokens and always attempts account
disable/session revocation. Preparing this file does not authorize running it.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import httpx

SOURCE = b"order_id,region,sales,discount\nA1,West,10,5\nA2,West,10,\nA3,East,7,0\nA4,East,,10\n"
QUESTIONS = (
    ("single_total", "What are total sales?"),
    ("verified_followup", "Explain that simply"),
    ("compound", "Give me total sales and count the orders."),
    ("tied_extrema", "Which records have the highest sales?"),
)


def _value(answer):
    return answer.get("value") if isinstance(answer, dict) else None


def _query_id(answer):
    if not isinstance(answer, dict):
        return None
    lineage = answer.get("lineage")
    return lineage.get("query_id") if isinstance(lineage, dict) else None


def score(results, synthesis):
    by_id = {item["id"]: item for item in results}
    single = by_id["single_total"].get("answer") or {}
    followup = by_id["verified_followup"].get("answer") or {}
    compound = by_id["compound"].get("answer") or {}
    extrema = by_id["tied_extrema"].get("answer") or {}
    followup_data = followup.get("data") if isinstance(followup, dict) else None
    compound_data = compound.get("data") if isinstance(compound, dict) else None
    additional = compound.get("additional_data", []) if isinstance(compound, dict) else []
    compound_second = additional[0] if len(additional) == 1 else None
    rows = extrema.get("rows", []) if isinstance(extrema, dict) else []
    columns = extrema.get("columns", []) if isinstance(extrema, dict) else []
    ids = (
        {str(row[columns.index("order_id")]) for row in rows}
        if "order_id" in columns and all(isinstance(row, list) for row in rows)
        else set()
    )
    checks = {
        "single_total": str(_value(single)) == "27",
        "verified_followup": (
            str(_value(followup_data)) == "27"
            and _query_id(followup_data) is not None
            and _query_id(followup_data) == _query_id(single)
        ),
        "compound": (
            str(_value(compound_data)) == "27"
            and str(_value(compound_second)) == "4"
            and _query_id(compound_data) != _query_id(compound_second)
        ),
        "tied_extrema": ids == {"A1", "A2"} and extrema.get("matched_records") == 2,
    }
    narratives = [
        item.get("answer", {}).get("narrative")
        for item in results
        if isinstance(item.get("answer"), dict)
    ]
    modes = [item.get("mode") for item in narratives if isinstance(item, dict)]
    synthesis_ok = (
        len(modes) == len(results) and all(mode in {"selected", "fallback"} for mode in modes)
        if synthesis == "enabled"
        else not modes
    )
    return checks, {
        "expected": synthesis,
        "observed_modes": modes,
        "selected": modes.count("selected"),
        "fallback": modes.count("fallback"),
        "matched_expectation": synthesis_ok,
    }



def wait_for_job(read, timeout=100):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        state = read()
        if state["status"] in {"succeeded", "failed", "cancelled", "expired"}:
            return state
        if state["status"] not in {"queued", "claimed", "running", "cancelling"}:
            raise ValueError("Unknown job state")
        sleep(0.5)
    raise TimeoutError("Synthetic job did not finish within the polling deadline")


def verify(client, output, *, stage, synthesis, origin, release):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Retain prior verification evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.touch(mode=0o600, exist_ok=False)
    started = monotonic()
    actors, last, results = [], {}, []
    report = {
        "version": "hosted-agent-harness-v1",
        "stage": stage,
        "release": release,
        "scope": "New fictional accounts and four fixed natural-language jobs only.",
        "representative_model_quality": False,
        "source_sha256": hashlib.sha256(SOURCE).hexdigest(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cases": [],
        "accounts": [],
        "cleanup": [],
        "passed": False,
    }

    def persist():
        temporary = output.with_name(output.name + "." + uuid4().hex + ".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        temporary.replace(output)

    def call(method, path, actor=None, expected=200, **kwargs):
        allowed_auth = {
            "/auth/options",
            "/auth/register",
            "/auth/login",
            "/auth/me",
            "/auth/disable",
        }
        own = tuple(
            f"/workspaces/{item['workspace_id']}/" for item in actors if item.get("workspace_id")
        )
        if path not in allowed_auth and path != "/workspaces" and not path.startswith(own):
            raise ValueError("Route is outside generated-account scope")
        if any(term in path for term in ("/connectors", "/webhooks", "/google", "/sources")):
            raise ValueError("External integrations are excluded")
        headers = {"Origin": origin, **kwargs.pop("headers", {})}
        if actor:
            headers["Authorization"] = "Bearer " + actor["token"]
        last.clear()
        last.update(method=method, path=path, expected=expected)
        response = client.request(method, path, headers=headers, **kwargs)
        last["actual"] = response.status_code
        if response.status_code != expected:
            raise AssertionError("Unexpected HTTP status; inspect redacted request metadata")
        return response

    def account(label):
        actor = {
            "email": f"agent-harness-{uuid4().hex}@example.test",
            "password": secrets.token_urlsafe(32),
            "label": label,
        }
        actors.append(actor)
        call(
            "POST",
            "/auth/register",
            expected=202,
            json={
                "email": actor["email"],
                "password": actor["password"],
                "display_name": "Fictional harness verifier",
                "workspace_name": "Fictional harness " + label,
            },
        )
        session = call(
            "POST", "/auth/login", json={"email": actor["email"], "password": actor["password"]}
        ).json()
        actor.update(token=session["token"], user_id=session["user"]["id"])
        actor["workspace_id"] = call("GET", "/workspaces", actor).json()[0]["id"]
        report["accounts"].append(
            {"label": label, "user_id": actor["user_id"], "workspace_id": actor["workspace_id"]}
        )
        persist()
        return actor

    def run_job(case_id, question):
        submitted = call(
            "POST",
            thread + "/jobs",
            owner,
            expected=202,
            json={"question": question, "request_id": str(uuid4())},
        ).json()
        path = prefix + "/jobs/" + submitted["id"]
        call("GET", path, outsider, expected=404)
        state = wait_for_job(lambda: call("GET", path, owner).json())
        entry = {"id": case_id, "status": state["status"], "attempts": state["attempts"]}
        if state["status"] == "succeeded":
            result = call("GET", path + "/result", owner).json()
            answer = result.get("answer")
            results.append({"id": case_id, "answer": answer})
            narrative = answer.get("narrative") if isinstance(answer, dict) else None
            entry.update(
                answer_kind=answer.get("kind", "numerical") if isinstance(answer, dict) else None,
                model_route=result["turn"].get("model_route"),
                narrative_mode=narrative.get("mode") if isinstance(narrative, dict) else None,
                turn_id=result["turn"]["id"],
            )
            turn_path = thread + "/turns/" + result["turn"]["id"] + "/answer"
            assert call("GET", turn_path, owner).json() == answer
            call("GET", turn_path, outsider, expected=404)
        else:
            results.append({"id": case_id, "answer": None})
            entry["failure_code"] = state.get("failure_code")
        report["cases"].append(entry)
        persist()

    persist()
    failure = None
    try:
        assert call("GET", "/auth/options").json()["local_registration_enabled"]
        owner, outsider = account("owner"), account("outsider")
        prefix = "/workspaces/" + owner["workspace_id"]
        did = call(
            "POST",
            prefix + "/datasets",
            owner,
            expected=201,
            json={"name": "Fictional agent harness"},
        ).json()["id"]
        uid = call(
            "POST",
            prefix + f"/datasets/{did}/uploads",
            owner,
            expected=201,
            params={"filename": "fictional-agent-harness.csv"},
            content=SOURCE,
            headers={"Content-Type": "text/csv"},
        ).json()["id"]
        root = prefix + f"/datasets/{did}/uploads/{uid}"
        current = call("GET", root + "/understanding", owner).json()
        definition = current["definition"]
        definition.update(
            domain="sales",
            grain="order",
            description="Synthetic orders for bounded harness verification.",
        )
        for column in definition["columns"]:
            name = column["name"]
            column.update(
                role="identifier"
                if name == "order_id"
                else "metric"
                if name in {"sales", "discount"}
                else "dimension",
                meaning="Fictional " + name,
                unit="",
                currency="USD" if name in {"sales", "discount"} else "",
                unit_column="",
            )
        call(
            "POST",
            root + "/understanding",
            owner,
            expected=201,
            json={
                "revision_id": current["revision_id"],
                "expected_version": current["version"],
                "state": "confirmed",
                "definition": definition,
            },
        )
        tid = call("POST", root + "/threads", owner, expected=201).json()["id"]
        thread = prefix + "/threads/" + tid
        for case_id, question in QUESTIONS:
            run_job(case_id, question)
        checks, synthesis_result = score(results, synthesis)
        report["task_checks"] = checks
        report["synthesis"] = synthesis_result
        required = {"single_total", "tied_extrema"} if stage == "before" else set(checks)
        report["task_gate_passed"] = (
            all(checks[name] for name in required) and synthesis_result["matched_expectation"]
        )
    except BaseException as error:
        failure = error
        report["failure"] = {"type": type(error).__name__, "request": dict(last)}
        raise
    finally:
        for actor in actors:
            entry = {"label": actor["label"], "user_id": actor.get("user_id"), "status": "pending"}
            report["cleanup"].append(entry)
            try:
                if not actor.get("token"):
                    session = call(
                        "POST",
                        "/auth/login",
                        json={"email": actor["email"], "password": actor["password"]},
                    ).json()
                    actor.update(token=session["token"], user_id=session["user"]["id"])
                call(
                    "POST",
                    "/auth/disable",
                    actor,
                    expected=204,
                    json={"password": actor["password"], "confirmed": True},
                )
                call("GET", "/auth/me", actor, expected=401)
                entry["status"] = "disabled_and_session_revoked"
            except Exception as cleanup_error:
                entry.update(
                    status="failed", error_type=type(cleanup_error).__name__, request=dict(last)
                )
            persist()
        cleanup_ok = all(
            item["status"] == "disabled_and_session_revoked" for item in report["cleanup"]
        )
        report["passed"] = bool(failure is None and report.get("task_gate_passed") and cleanup_ok)
        report["elapsed_seconds"] = round(monotonic() - started, 3)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        persist()
        if failure is None and not cleanup_ok:
            raise RuntimeError("Synthetic account cleanup failed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, choices=["http://127.0.0.1:18401"])
    parser.add_argument(
        "--origin", default="http://localhost:18400", choices=["http://localhost:18400"]
    )
    parser.add_argument("--stage", required=True, choices=["before", "after"])
    parser.add_argument("--expect-synthesis", required=True, choices=["enabled", "disabled"])
    parser.add_argument("--confirmed-private-release", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{16}", args.confirmed_private_release):
        raise SystemExit("Use the exact root-verified release identifier")
    with httpx.Client(base_url=args.base_url, timeout=20, follow_redirects=False) as session:
        result = verify(
            session,
            args.output,
            stage=args.stage,
            synthesis=args.expect_synthesis,
            origin=args.origin,
            release=args.confirmed_private_release,
        )
    if not result["passed"]:
        raise SystemExit("Hosted harness checks did not meet the declared stage expectations")
