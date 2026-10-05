"""Use case: Creates the ExecPlus HTTP application.

What it does: Validates startup, composes dependencies, and maps safe API failures.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from execplus import __version__
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
from execplus.presentation.routes.activation import router as activation_router
from execplus.presentation.routes.analytics import router as analytics_router
from execplus.presentation.routes.artifacts import router as artifacts_router
from execplus.presentation.routes.health import router as health_router
from execplus.presentation.routes.jobs import router as jobs_router
from execplus.presentation.routes.joins import router as joins_router
from execplus.presentation.routes.refresh import router as refresh_router
from execplus.presentation.routes.saved_items import router as saved_items_router
from execplus.presentation.routes.studies import router as studies_router
from execplus.presentation.routes.threads import router as threads_router
from execplus.presentation.routes.understanding import router as understanding_router
from execplus.presentation.routes.workspaces import router as workspace_router


def create_app(settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configured = settings or Settings()
        application.state.runtime = runtime or build_runtime(configured)
        try:
            yield
        finally:
            if runtime is None:
                application.state.runtime.engine.dispose()

    application = FastAPI(
        title="ExecPlus API",
        summary="Verified conversational analytics",
        version=__version__,
        lifespan=lifespan,
    )
    configured = settings or Settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[configured.web_origin],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.middleware("http")
    async def private_responses(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    application.include_router(activation_router)
    application.include_router(health_router)
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
