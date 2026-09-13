"""Use case: Composes provider implementations from validated settings.

What it does: Selects disabled, local, or hosted model adapters at the application edge.
"""

from dataclasses import dataclass

import boto3
from botocore.config import Config
from sqlalchemy import Engine, create_engine

from execplus.application.ports import IdentityProvider, LanguageModel
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.answers import AnswerAssembler
from execplus.application.services.health import HealthService
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.joins import JoinService
from execplus.application.services.saved_items import SavedItemService
from execplus.application.services.summaries import SummaryService
from execplus.application.services.threads import ThreadService
from execplus.application.services.workspaces import WorkspaceService
from execplus.config import Settings
from execplus.infrastructure.file_parser import StructuredFileParser
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.infrastructure.models.disabled import DisabledLanguageModel
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel
from execplus.infrastructure.object_storage import S3ObjectStorage
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.readiness import DatabaseProbe, StorageProbe


def build_language_model(settings: Settings) -> LanguageModel:
    if settings.llm_mode == "disabled":
        return DisabledLanguageModel()
    return OpenAICompatibleLanguageModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        small_model=settings.llm_small_model,
        large_model=settings.llm_large_model,
        provider_name=settings.llm_mode,
    )


def build_runtime(settings: Settings) -> "Runtime":
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3}
    )
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
        region_name="us-east-1",
        config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}),
    )
    storage = S3ObjectStorage(client, settings.object_store_bucket)
    identity = LocalSessionIdentity(engine, settings.environment)
    parser = StructuredFileParser()
    executor = DuckDBQueryExecutor(settings.query_timeout_seconds, settings.query_memory_limit_mb)
    analytics = AnalyticsService(
        SQLUnitOfWork(engine),
        storage,
        parser,
        executor,
        AnswerAssembler(),
        settings.query_row_limit,
    )
    model = build_language_model(settings)
    intent_router = IntentRouterService(model, analytics)
    return Runtime(
        WorkspaceService(SQLUnitOfWork(engine), storage, parser, settings.max_upload_bytes),
        identity,
        HealthService((DatabaseProbe(engine), StorageProbe(storage))),
        engine,
        analytics,
        intent_router,
        SummaryService(model),
        JoinService(SQLUnitOfWork(engine), storage, parser, executor, settings.query_row_limit),
        SavedItemService(SQLUnitOfWork(engine)),
        ThreadService(SQLUnitOfWork(engine), intent_router),
    )


@dataclass
class Runtime:
    service: WorkspaceService
    identity: IdentityProvider
    health: HealthService
    engine: Engine
    analytics: AnalyticsService
    intent_router: IntentRouterService
    summaries: SummaryService
    joins: JoinService
    saved_items: SavedItemService
    threads: ThreadService
