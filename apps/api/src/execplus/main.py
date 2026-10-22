"""Use case: Creates the ExecPlus HTTP application.

What it does: Validates startup, composes dependencies, and maps safe API failures.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from execplus import __version__
from execplus.application.plan_context import plan_request_context
from execplus.bootstrap import Runtime, build_runtime
from execplus.config import Settings
from execplus.domain.errors import (
    AuthorizationError,
    ClarificationRequiredError,
    ProviderUnavailableError,
    UnsafeQueryError,
    UnsupportedQuestionError,
    UnverifiedAnswerError,
)
from execplus.domain.ingestion import IngestionError
from execplus.presentation.account_request_guard import AccountRequestGuard
from execplus.presentation.private_json import EvidenceJSONResponse
from execplus.presentation.request_observation import category_for, configure_observation_logging
from execplus.presentation.routes.access_policies import router as access_policies_router
from execplus.presentation.routes.accounts import router as accounts_router
from execplus.presentation.routes.activation import router as activation_router
from execplus.presentation.routes.analytics import router as analytics_router
from execplus.presentation.routes.artifacts import router as artifacts_router
from execplus.presentation.routes.company_consolidation import router as consolidation_router
from execplus.presentation.routes.connectors import router as connectors_router
from execplus.presentation.routes.data_brief import router as data_brief_router
from execplus.presentation.routes.decision_analysis import router as decision_analysis_router
from execplus.presentation.routes.forecasts import router as forecasts_router
from execplus.presentation.routes.google import router as google_router
from execplus.presentation.routes.health import router as health_router
from execplus.presentation.routes.incidents import router as incidents_router
from execplus.presentation.routes.integrations import router as integrations_router
from execplus.presentation.routes.jobs import router as jobs_router
from execplus.presentation.routes.joins import router as joins_router
from execplus.presentation.routes.oauth import router as oauth_router
from execplus.presentation.routes.operations import router as operations_router
from execplus.presentation.routes.pdf_exports import router as pdf_exports_router
from execplus.presentation.routes.plans import router as plans_router
from execplus.presentation.routes.product_usage import router as product_usage_router
from execplus.presentation.routes.refresh import router as refresh_router
from execplus.presentation.routes.result_exports import router as result_exports_router
from execplus.presentation.routes.saved_items import router as saved_items_router
from execplus.presentation.routes.source_imports import router as source_imports_router
from execplus.presentation.routes.studies import router as studies_router
from execplus.presentation.routes.threads import router as threads_router
from execplus.presentation.routes.understanding import router as understanding_router
from execplus.presentation.routes.usage_metering import router as usage_metering_router
from execplus.presentation.routes.workspaces import router as workspace_router


def create_app(settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configured = settings or Settings()
        application.state.runtime = runtime or build_runtime(configured)
        collector = application.state.runtime.incidents
        notifications = application.state.runtime.webhooks
        collector.stop.clear()
        collection_task = asyncio.create_task(collector.run())
        notifications.stop.clear()
        notification_task = asyncio.create_task(notifications.run())
        try:
            yield
        finally:
            collector.stop.set()
            notifications.stop.set()
            await notification_task
            await collection_task
            if (
                collector.pending
                or collector.observations
                or collector.observation_batch is not None
                or collector.collector_extras
                or collector.dropped
                or collector.outages
            ):
                await collector.collect_once()
            if runtime is None:
                application.state.runtime.engine.dispose()

    application = FastAPI(
        title="ExecPlus API",
        summary="Verified conversational analytics",
        version=__version__,
        lifespan=lifespan,
        default_response_class=EvidenceJSONResponse,
    )
    configured = settings or Settings()
    configure_observation_logging()
    application.state.web_origin = configured.web_origin
    application.add_middleware(AccountRequestGuard, web_origin=configured.web_origin)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[configured.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-ExecPlus-Request"],
        expose_headers=["Content-Disposition", "X-Request-ID"],
    )

    @application.middleware("http")
    async def private_responses(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        current_runtime = getattr(request.app.state, "runtime", None)
        request_id = uuid4()
        request.state.request_id = request_id
        started = monotonic()
        try:
            with plan_request_context(request.headers.get("Idempotency-Key")):
                response = await call_next(request)
        except IngestionError as exc:
            response = JSONResponse(
                status_code=exc.status, content={"error": {"code": exc.code, "message": str(exc)}}
            )
            if request.headers.get("origin") == configured.web_origin:
                response.headers["Access-Control-Allow-Origin"] = configured.web_origin
                response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                response.headers["Vary"] = "Origin"
        except Exception:
            # Do not let framework tracebacks disclose SQL, credentials or uploaded content.
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "The request could not be completed. Try again.",
                    }
                },
            )
            if request.headers.get("origin") == configured.web_origin:
                response.headers["Access-Control-Allow-Origin"] = configured.web_origin
                response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                response.headers["Vary"] = "Origin"
        category = category_for(request)
        if response.status_code >= 500 and current_runtime is not None:
            current_runtime.incidents.record_http_failure(request_id, category or "other")
            logging.getLogger("execplus.requests").error(
                json.dumps(
                    {
                        "event": "request_failed",
                        "request_id": str(request_id),
                        "category": category or "other",
                        "status": response.status_code,
                    },
                    separators=(",", ":"),
                )
            )
        if current_runtime is not None and category is not None:
            current_runtime.incidents.record_request(
                category, response.status_code, int((monotonic() - started) * 1000)
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-ID"] = str(request_id)
        return response

    application.include_router(oauth_router)
    application.include_router(activation_router)
    application.include_router(accounts_router)
    application.include_router(plans_router)
    application.include_router(access_policies_router)
    application.include_router(health_router)
    application.include_router(incidents_router)
    application.include_router(integrations_router)
    application.include_router(consolidation_router)
    application.include_router(usage_metering_router)
    application.include_router(source_imports_router)
    application.include_router(workspace_router)
    application.include_router(analytics_router)
    application.include_router(joins_router)
    application.include_router(saved_items_router)
    application.include_router(threads_router)
    application.include_router(understanding_router)
    application.include_router(studies_router)
    application.include_router(refresh_router)
    application.include_router(artifacts_router)
    application.include_router(jobs_router)
    application.include_router(forecasts_router)
    application.include_router(operations_router)
    application.include_router(product_usage_router)
    application.include_router(decision_analysis_router)
    application.include_router(data_brief_router)
    application.include_router(pdf_exports_router)
    application.include_router(result_exports_router)
    application.include_router(google_router)
    application.include_router(connectors_router)

    @application.exception_handler(IngestionError)
    async def ingestion_error(request: Request, error: IngestionError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": str(error)}},
            headers={
                "Cache-Control": "no-store",
                **({"WWW-Authenticate": "Bearer"} if error.status == 401 else {}),
            },
        )

    @application.exception_handler(AuthorizationError)
    async def authorization_error(request: Request, error: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {"code": "not_found", "message": "The requested resource is unavailable."}
            },
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(ClarificationRequiredError)
    async def clarification_required_error(
        request: Request, error: ClarificationRequiredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "clarification_required", "message": str(error)}},
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(UnsupportedQuestionError)
    async def unsupported_question_error(
        request: Request, error: UnsupportedQuestionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "unsupported_question", "message": str(error)}},
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(UnsafeQueryError)
    async def unsafe_query_error(request: Request, error: UnsafeQueryError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "unsafe_query", "message": str(error)}},
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(ProviderUnavailableError)
    async def provider_unavailable_error(
        request: Request, error: ProviderUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "provider_unavailable", "message": str(error)}},
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(UnverifiedAnswerError)
    async def unverified_answer_error(
        request: Request, error: UnverifiedAnswerError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "internal_error", "message": "The answer could not be verified."}
            },
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Check the request fields and UUID identifiers.",
                }
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "The database is unavailable. Try again.",
                }
            },
        )

    return application


app = create_app()
