"""Select complete, server-authored English statements without accepting model claims."""

import json
from dataclasses import dataclass
from typing import Any

VERSION = "verified-narrative-v1"
MAX_STATEMENTS = 20
MAX_PACKET_CHARS = 18000


@dataclass(frozen=True)
class FactStatement:
    id: str
    variants: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class FactPacket:
    statements: tuple[FactStatement, ...]

    def __post_init__(self) -> None:
        if (
            not 1 <= len(self.statements) <= MAX_STATEMENTS
            or len({s.id for s in self.statements}) != len(self.statements)
            or any(
                not s.id
                or not s.evidence_ids
                or not s.variants
                or any(not text or len(text) > 4000 for text in s.variants)
                for s in self.statements
            )
            or len(json.dumps(self.choices())) > MAX_PACKET_CHARS
        ):
            raise ValueError("Invalid or oversized fact packet")

    def choices(self) -> list[dict[str, Any]]:
        return [dict(id=s.id, variants=list(s.variants), kind=s.kind) for s in self.statements]


def render_selection(packet: FactPacket, content: str | None = None) -> dict[str, Any]:
    selections = [dict(id=s.id, variant=0) for s in packet.statements]
    if content is not None:
        if len(content) > 6000:
            raise ValueError("Oversized selection")
        payload = json.loads(content)
        if not isinstance(payload, dict) or set(payload) != {"selections"}:
            raise ValueError("Unexpected selection keys")
        selections = payload["selections"]
        if not isinstance(selections, list) or len(selections) != len(packet.statements):
            raise ValueError("All statements are required")
    bank = {s.id: s for s in packet.statements}
    segments = []
    seen = set()
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) != {"id", "variant"}:
            raise ValueError("Unexpected statement keys")
        key, variant = selection["id"], selection["variant"]
        if (
            not isinstance(key, str)
            or key not in bank
            or key in seen
            or type(variant) is not int
            or not 0 <= variant < len(bank[key].variants)
        ):
            raise ValueError("Unsupported statement or variant")
        seen.add(key)
        statement = bank[key]
        segments.append(
            dict(
                statement_id=key,
                text=statement.variants[variant],
                evidence_ids=list(statement.evidence_ids),
                kind=statement.kind,
            )
        )
    return dict(
        version=VERSION, mode="fallback" if content is None else "selected", segments=segments
    )


def validate_saved_narrative(packet: FactPacket, value: object) -> bool:
    """Rebuilt authorized facts must still exactly support every saved segment."""
    if not isinstance(value, dict) or set(value) != {"version", "mode", "segments"}:
        return False
    if value["version"] != VERSION or value["mode"] not in ("fallback", "selected"):
        return False
    segments = value["segments"]
    if not isinstance(segments, list) or len(segments) != len(packet.statements):
        return False
    bank = {s.id: s for s in packet.statements}
    seen: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) != {
            "statement_id",
            "text",
            "evidence_ids",
            "kind",
        }:
            return False
        key = segment["statement_id"]
        if not isinstance(key, str) or key not in bank or key in seen:
            return False
        seen.add(key)
        statement = bank[key]
        if (
            segment["text"] not in statement.variants
            or segment["evidence_ids"] != list(statement.evidence_ids)
            or segment["kind"] != statement.kind
        ):
            return False
    return True
