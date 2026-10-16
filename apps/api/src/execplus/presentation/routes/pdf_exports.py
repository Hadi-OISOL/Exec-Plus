"""Use case: Downloads a PDF of an existing actor-private saved answer.

What it does: Passes validated identifiers through the export service and returns
an authenticated no-store attachment without exposing a public object URL.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from execplus.application.services.pdf_exports import PdfExportService
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["pdf-exports"])


def get_pdf_export_service(request: Request) -> PdfExportService:
    service: PdfExportService = request.app.state.runtime.pdf_exports
    return service


Service = Annotated[PdfExportService, Depends(get_pdf_export_service)]


@router.get("/workspaces/{workspace_id}/threads/{thread_id}/turns/{turn_id}/export.pdf")
async def download_pdf(
    workspace_id: UUID, thread_id: UUID, turn_id: UUID, actor: Actor, service: Service
) -> Response:
    value = await service.download(actor, workspace_id, thread_id, turn_id)
    return Response(
        value.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{value.filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
