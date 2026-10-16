"""Use case: Delivers private multi-company worksheets as exact portable files.

What it does: Replays all participating sources around rendering and rechecks
current rights under ordered workspace locks before returning any bytes.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.services.company_consolidation import CompanyConsolidationService
from execplus.application.services.consolidation_report_documents import build_consolidation_report
from execplus.application.services.forecasts import read_complete
from execplus.application.services.result_exports import ResultExportService
from execplus.domain.exports import ExportDownload, validate_export
from execplus.domain.ingestion import AuditEvent, IngestionError, User


class ConsolidationExportService:
    def __init__(
        self, worksheets: CompanyConsolidationService, exports: ResultExportService
    ) -> None:
        self.worksheets, self.exports = worksheets, exports

    async def download(self, actor: User, oid: UUID, rid: UUID, format: str) -> ExportDownload:
        formats = {
            "pdf": ("pdf", "application/pdf"),
            "xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "csv": ("zip", "application/zip"),
            "png": ("png", "image/png"),
        }
        if format not in formats:
            raise IngestionError("export_format", "Choose PDF, Excel, CSV or PNG.", 422)
        if self.exports.slots.locked():
            raise IngestionError(
                "export_busy", "Export generation is busy. Try again shortly.", 429
            )
        async with self.exports.slots:
            now = datetime.now(timezone.utc)
            before = await self.worksheets.open(actor, oid, rid)
            content = build_consolidation_report(before, now)
            validate_export(content)
            payload = await read_complete(lambda: self.exports.renderer.render(content, format))
            after = await self.worksheets.open(actor, oid, rid)
            if after != before:
                raise IngestionError(
                    "source_changed",
                    "The worksheet changed during export. Reopen it and retry.",
                    409,
                )
            run = before["run"]
            with self.worksheets.store.transaction() as repo:
                current = self.worksheets._check(
                    repo,
                    actor,
                    oid,
                    run["request"]["companies"],
                    run["evidence"]["companies"],
                    require_current=False,
                )
                saved = repo.consolidation_run(oid, rid, actor.id)
                if current != before["current"] or asdict(saved) != run:
                    raise IngestionError(
                        "source_changed",
                        "The worksheet changed during export. Reopen it and retry.",
                        409,
                    )
                for company in run["request"]["companies"]:
                    repo.add(
                        AuditEvent(
                            uuid4(),
                            UUID(company["workspace_id"]),
                            actor.id,
                            "consolidation.exported",
                            "consolidation",
                            rid,
                            now,
                        )
                    )
            extension, media_type = formats[format]
            return ExportDownload(f"execplus-consolidation-{rid}.{extension}", payload, media_type)
