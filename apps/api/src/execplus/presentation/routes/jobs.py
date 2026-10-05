"""Use case: Exposes private durable conversation submission and genuine activity.

What it does: Authorizes polling, cancellation and evidence independently of HTTP lifetime.
"""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request

from execplus.application.services.jobs import JobService
from execplus.domain.jobs import Job
from execplus.presentation.routes.analytics import numerical_answer_body
from execplus.presentation.routes.threads import AskInThreadInput, _turn_body
from execplus.presentation.routes.workspaces import Actor

router = APIRouter(tags=["jobs"])


def service(request: Request) -> JobService:
    jobs: JobService = request.app.state.runtime.jobs
    return jobs


Service = Annotated[JobService, Depends(service)]


def body(job: Job) -> dict[str, object]:
    return {
        "id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "thread_id": str(job.thread_id),
        "turn_id": str(job.turn_id),
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "attempts": job.attempts,
        "current_stage": job.current_stage,
        "cancel_requested": job.cancel_requested,
        "failure_code": job.failure_code,
    }


@router.post("/workspaces/{workspace_id}/threads/{thread_id}/jobs", status_code=202)
def submit(
    workspace_id: UUID, thread_id: UUID, request: AskInThreadInput, actor: Actor, jobs: Service
) -> object:
    request_id = request.request_id or uuid4()
    return body(jobs.submit(actor, workspace_id, thread_id, request.question, request_id))


@router.get("/workspaces/{workspace_id}/jobs/{job_id}")
def get(workspace_id: UUID, job_id: UUID, actor: Actor, jobs: Service) -> object:
    return body(jobs.get(actor, workspace_id, job_id))


@router.get("/workspaces/{workspace_id}/jobs/{job_id}/events")
def events(
    workspace_id: UUID,
    job_id: UUID,
    actor: Actor,
    jobs: Service,
    after: Annotated[int, Query(ge=0, le=200)] = 0,
) -> object:
    recorded = jobs.events(actor, workspace_id, job_id, after)
    return {
        "events": [
            {
                "sequence": event.sequence,
                "stage": event.stage,
                "status": event.status,
                "created_at": event.created_at.isoformat(),
            }
            for event in recorded
        ],
        "next_sequence": recorded[-1].sequence if recorded else after,
    }


@router.post("/workspaces/{workspace_id}/jobs/{job_id}/cancel")
def cancel(workspace_id: UUID, job_id: UUID, actor: Actor, jobs: Service) -> object:
    return body(jobs.cancel(actor, workspace_id, job_id))


@router.get("/workspaces/{workspace_id}/jobs/{job_id}/result")
async def result(workspace_id: UUID, job_id: UUID, actor: Actor, jobs: Service) -> object:
    answer, turn = await jobs.result(actor, workspace_id, job_id)
    return {
        "turn": _turn_body(turn),
        "answer": numerical_answer_body(answer) if answer is not None else None,
    }
