"""Use case: Runs and reopens source-grounded structural diagram tools.

What it does: Verifies authorized metadata before publication and reproduces saved diagrams
from their exact recorded revision and meanings without calling a language model.
"""

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from execplus.application.progress import activity
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.forecasts import read_complete
from execplus.domain.data_diagram import DIAGRAM_VERSION, DataDiagram, DiagramRequest, build_diagram
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.jobs import EventStatus, JobStage


@dataclass(frozen=True, slots=True)
class DiagramAnswer:
    diagram: DataDiagram
    columns: tuple[str, ...]
    sources: tuple[dict[str, str], ...]
    model_route: str = "deterministic:" + DIAGRAM_VERSION


class DataDiagramService:
    def __init__(self, analytics: AnalyticsService) -> None:
        self.analytics = analytics

    async def create(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        context: DescriptionContext,
        request: DiagramRequest,
    ) -> DiagramAnswer:
        await activity(JobStage.VERIFYING, EventStatus.STARTED)
        diagram = build_diagram(context, request)
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, context.view.sources)
        )
        await activity(JobStage.VERIFYING, EventStatus.COMPLETED)
        return DiagramAnswer(diagram, request.columns, context.view.sources)

    async def reopen(self, actor: User, wid: UUID, evidence: dict[str, Any]) -> DiagramAnswer:
        sources = evidence.get("sources", [])
        if len(sources) != 1 or not isinstance(evidence.get("columns"), list):
            raise IngestionError(
                "lineage_mismatch", "The saved diagram source is inconsistent.", 409
            )
        source = sources[0]
        context = await read_complete(
            lambda: self.analytics.describe(
                actor, wid, UUID(source["dataset_id"]), UUID(source["upload_id"]), source
            )
        )
        try:
            result = evidence.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("version"), str):
                raise ValueError("The saved diagram has no recorded version.")
            diagram = build_diagram(
                context, DiagramRequest(tuple(evidence["columns"])), version=result["version"]
            )
        except (ValueError, TypeError) as error:
            raise IngestionError(
                "lineage_mismatch", "The saved diagram is inconsistent.", 409
            ) from error
        if json.loads(json.dumps(diagram.body())) != evidence.get("result"):
            raise IngestionError("lineage_mismatch", "The saved diagram evidence changed.", 409)
        return DiagramAnswer(
            diagram,
            tuple(evidence["columns"]),
            tuple(sources),
            "deterministic:" + diagram.version,
        )
