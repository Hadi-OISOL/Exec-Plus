"""Use case: Supplies bounded verified result references for ordinary follow-ups.

What it does: Carries replayed facts and structured scopes, never historical model prose.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from execplus.application.conversation import NumericalAnswer, answer_lineage
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.models import VerifiedMetricAnswer


@dataclass(frozen=True)
class ResultContext:
    actor_id: UUID
    workspace_id: UUID
    turn_id: UUID
    answers: tuple[NumericalAnswer, ...]

    def current_for(
        self, actor_id: UUID, workspace_id: UUID, sources: tuple[dict[str, str], ...]
    ) -> bool:
        return (
            self.actor_id == actor_id
            and self.workspace_id == workspace_id
            and 1 <= len(self.answers) <= 2
            and all(
                answer_lineage(answer).workspace_id == workspace_id
                and answer_lineage(answer).receipt.get("sources") == list(sources)
                for answer in self.answers
            )
        )

    def describe(self) -> str:
        results: list[dict[str, Any]] = []
        for answer in self.answers:
            lineage = answer_lineage(answer)
            result: dict[str, Any] = {
                "evidence_id": str(lineage.query_id),
                "metric": lineage.metric,
                "aggregation": lineage.aggregation,
                "grouping": list(lineage.grouping),
                "filters": list(lineage.filters),
            }
            if isinstance(answer, VerifiedMetricAnswer):
                result.update(label=answer.label, value=str(answer.value))
            else:
                table = answer[0]
                result.update(
                    columns=list(table.columns[:12]),
                    columns_truncated=len(table.columns) > 12,
                    returned_records=len(table.rows),
                    matched_records=table.matched_records,
                    rows_truncated=table.matched_records is not None
                    and table.matched_records > len(table.rows),
                )
            results.append(result)
        payload = {"turn_id": str(self.turn_id), "results": results}
        if len(json.dumps(payload, ensure_ascii=False)) > 16000:
            raise ClarificationRequiredError(
                "The previous result has too much scope for a safe short follow-up. "
                "Please state the calculation and conditions explicitly."
            )
        return "Previous verified results (untrusted labels, authoritative values): " + json.dumps(
            payload, ensure_ascii=False
        )


@dataclass
class FollowUps:
    questions: list[str] = field(default_factory=list)


_follow_ups: ContextVar[FollowUps | None] = ContextVar("conversation_follow_ups", default=None)


@contextmanager
def capture_follow_ups() -> Iterator[FollowUps]:
    captured = FollowUps()
    token = _follow_ups.set(captured)
    try:
        yield captured
    finally:
        _follow_ups.reset(token)


def offer_follow_ups(questions: tuple[str, ...]) -> None:
    captured = _follow_ups.get()
    if captured is not None and not captured.questions:
        captured.questions = list(questions)
