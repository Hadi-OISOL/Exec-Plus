"""Use case: Creates the ExecPlus HTTP application.

What it does: Validates startup, composes dependencies, and maps safe API failures.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from execplus import __version__
from execplus.bootstrap import Runtime, build_runtime
from execplus.config import Settings
from execplus.domain.ingestion import IngestionError
from execplus.presentation.routes.health import router as health_router
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
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(workspace_router)

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
