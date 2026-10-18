"""Build presentation facts from authorized immutable calculation definitions."""

from functools import partial
from typing import cast
from uuid import UUID

from execplus.application.conversation import EvidenceAnswer, NumericalAnswer, answer_lineage
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.forecasts import read_complete
from execplus.application.services.intent_router import PatternAnswer
from execplus.application.services.response_synthesis import build_fact_packet
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer
from execplus.domain.response_synthesis import FactPacket


def data_answers(answer: object) -> tuple[NumericalAnswer, ...]:
    if isinstance(answer, EvidenceAnswer):
        return ((answer.data,) if answer.data is not None else ()) + answer.additional_data
    if isinstance(answer, VerifiedMetricAnswer):
        return (answer,)
    if (
        isinstance(answer, tuple)
        and len(answer) == 2
        and isinstance(answer[0], QueryResult)
        and isinstance(answer[1], CalculationLineage)
    ):
        return (cast(NumericalAnswer, answer),)
    return ()


def receipt_sources(data: NumericalAnswer) -> list[dict[str, str]]:
    raw = answer_lineage(data).receipt.get("sources", [])
    if not isinstance(raw, list) or any(
        not isinstance(item, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in item.items())
        for item in raw
    ):
        raise IngestionError("lineage_mismatch", "The saved source references are invalid.", 409)
    return cast(list[dict[str, str]], raw)


def narrative_sources(answer: object) -> tuple[dict[str, str], ...]:
    if isinstance(answer, EvidenceAnswer):
        return answer.sources
    if isinstance(answer, PatternAnswer):
        return tuple(answer.evidence["sources"])
    sources: list[dict[str, str]] = []
    for data in data_answers(answer):
        for source in receipt_sources(data):
            if source not in sources:
                sources.append(source)
    return tuple(sources)


async def authorized_fact_packet(
    analytics: AnalyticsService, actor: User, wid: UUID, answer: object, *, current: bool = False
) -> FactPacket | None:
    sources = narrative_sources(answer)
    if not sources:
        return None
    contexts = {}
    for source in sources:
        did, uid = UUID(source["dataset_id"]), UUID(source["upload_id"])
        if current:
            await read_complete(
                partial(analytics.recheck_description, actor, wid, did, uid, (source,))
            )
        context = await read_complete(partial(analytics.describe, actor, wid, did, uid, source))
        contexts[(did, uid)] = context
    units: dict[str, str] = {}
    for data in data_answers(answer):
        lineage = answer_lineage(data)
        refs = receipt_sources(data)
        if len(refs) != 1 or lineage.aggregation == "count":
            continue
        source = refs[0]
        definition_context = contexts.get((UUID(source["dataset_id"]), UUID(source["upload_id"])))
        if definition_context is None or definition_context.state != "confirmed":
            continue
        for field in (definition_context.definition or {}).get("columns", []):
            if field["name"] == lineage.metric and not field.get("unit_column"):
                label = field.get("currency") or field.get("unit")
                if label:
                    units[str(lineage.query_id)] = label
    return build_fact_packet(answer, units=units)
