"""Use case: Prevents demo evidence from authorizing a production deployment.

What it does: Requires reviewed, checksum-bound evidence for every deferred release gate.
"""

import hashlib
import json
from datetime import date
from pathlib import Path

REQUIRED_GATES = {
    "representative_corpus": "Approved representative documents and human question/answer labels",
    "retrieval_quality": "Agreed relevance threshold, negative cases and citation accuracy",
    "vector_provider": "Selected provider isolation, filtering, deletion, latency and cost tests",
    "backup_restore": "Database, source-object and selected search-provider restore drills",
    "model_comparison": "Local/hosted quality, latency, token use and reconciled cost comparison",
    "provider_privacy": "Approved hosted data handling, residency, retention and secret management",
    "report_delivery": "SMTP/worker delivery, unsubscribe and uncertain-claim recovery rehearsal",
    "identity_security": "Production identity and tenant isolation security review",
}


def pending_gates(path: str) -> tuple[str, ...]:
    if not path:
        return tuple(REQUIRED_GATES)
    manifest_path = Path(path).resolve()
    try:
        if manifest_path.stat().st_size > 1024 * 1024:
            return tuple(REQUIRED_GATES)
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, dict) or manifest.get("scope") != "production":
            return tuple(REQUIRED_GATES)
        entries = manifest.get("gates", {})
        if not isinstance(entries, dict):
            return tuple(REQUIRED_GATES)
    except (OSError, ValueError):
        return tuple(REQUIRED_GATES)
    pending = []
    for key in REQUIRED_GATES:
        entry = entries.get(key)
        try:
            if not isinstance(entry, dict) or entry.get("status") != "passed":
                raise ValueError("Gate not passed")
            if not isinstance(entry.get("reviewed_by"), str) or not entry["reviewed_by"].strip():
                raise ValueError("Review missing")
            if date.fromisoformat(entry["reviewed_on"]) > date.today():
                raise ValueError("Future review")
            artifact = (manifest_path.parent / entry["evidence_file"]).resolve()
            if not artifact.is_relative_to(manifest_path.parent) or not artifact.is_file():
                raise ValueError("Evidence outside release bundle")
            if not artifact.stat().st_size:
                raise ValueError("Evidence empty")
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Evidence changed")
        except (OSError, ValueError, KeyError, TypeError):
            pending.append(key)
    return tuple(pending)


def require_production_evidence(path: str) -> None:
    pending = pending_gates(path)
    if pending:
        raise ValueError("Production validation is incomplete: " + ", ".join(pending))
