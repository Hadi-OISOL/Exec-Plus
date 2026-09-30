"""Use case: Composes provider implementations from validated settings.

What it does: Selects disabled, local, or hosted model adapters at the application edge.
"""

from dataclasses import dataclass

import boto3
from botocore.config import Config
from sqlalchemy import Engine, create_engine

from execplus import __version__
from execplus.application.ports import IdentityProvider, LanguageModel
from execplus.application.services.activation import ActivationService
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.answers import AnswerAssembler
from execplus.application.services.catalog import CatalogService
from execplus.application.services.document_answers import DocumentAnswerService
from execplus.application.services.health import HealthService
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.joins import JoinService
from execplus.application.services.knowledge import KnowledgeService
from execplus.application.services.monitoring import MonitoringService
from execplus.application.services.refresh import RefreshService
from execplus.application.services.reports import ReportService
from execplus.application.services.saved_items import SavedItemService
from execplus.application.services.studies import OrganizationService, StudyService
from execplus.application.services.summaries import SummaryService
from execplus.application.services.threads import ThreadService
from execplus.application.services.understanding import UnderstandingService
from execplus.application.services.workspaces import WorkspaceService
from execplus.config import Settings
from execplus.infrastructure.email import DisabledEmailDelivery, SMTPEmailDelivery
from execplus.infrastructure.file_parser import StructuredFileParser
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.infrastructure.knowledge import ReferenceHybridRanker
from execplus.infrastructure.models.disabled import DisabledLanguageModel
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel
from execplus.infrastructure.object_storage import S3ObjectStorage
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.readiness import DatabaseProbe, StorageProbe
from execplus.infrastructure.release_gate import require_production_evidence


def build_language_model(settings: Settings) -> LanguageModel:
    if settings.llm_mode == "disabled":
        return DisabledLanguageModel()
    return OpenAICompatibleLanguageModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        small_model=settings.llm_small_model,
        large_model=settings.llm_large_model,
        provider_name=settings.llm_mode,
        max_output_tokens=settings.llm_max_output_tokens,
        reasoning_effort=settings.llm_reasoning_effort,
        json_mode=settings.llm_json_mode,
    )


def build_selection_model(settings: Settings) -> LanguageModel | None:
    if not settings.llm_selection_model:
        return None
    return OpenAICompatibleLanguageModel(
        base_url=settings.llm_selection_base_url,
        api_key=settings.llm_selection_api_key,
        small_model=settings.llm_selection_model,
        large_model=settings.llm_selection_model,
        provider_name="selection",
        max_output_tokens=512,
        reasoning_effort="none",
        json_mode=True,
        timeout_seconds=20,
        max_attempts=1,
    )


def build_runtime(settings: Settings) -> "Runtime":
    if settings.environment == "production":
        require_production_evidence(settings.production_evidence_path)
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
    selector = build_selection_model(settings)
    knowledge = KnowledgeService(SQLUnitOfWork(engine), storage, ReferenceHybridRanker())
    intent_router = IntentRouterService(
        model, analytics, selector, DocumentAnswerService(knowledge, model)
    )
    uploads = WorkspaceService(SQLUnitOfWork(engine), storage, parser, settings.max_upload_bytes)
    refresh = RefreshService(SQLUnitOfWork(engine), uploads, analytics)
    return Runtime(
        uploads,
        identity,
        HealthService((DatabaseProbe(engine), StorageProbe(storage))),
        engine,
        analytics,
        intent_router,
        SummaryService(selector or model),
        JoinService(SQLUnitOfWork(engine), storage, parser, executor, settings.query_row_limit),
        SavedItemService(SQLUnitOfWork(engine)),
        ThreadService(SQLUnitOfWork(engine), intent_router),
        ActivationService(SQLUnitOfWork(engine), analytics, __version__),
        knowledge,
        ReportService(
            SQLUnitOfWork(engine),
            analytics,
            SMTPEmailDelivery(
                settings.smtp_host,
                settings.smtp_port,
                settings.smtp_username,
                settings.smtp_password,
                settings.smtp_sender,
            )
            if settings.email_mode == "smtp"
            else DisabledEmailDelivery(),
            settings.web_origin,
        ),
        UnderstandingService(SQLUnitOfWork(engine), storage, parser),
        CatalogService(SQLUnitOfWork(engine)),
        StudyService(SQLUnitOfWork(engine), analytics),
        OrganizationService(SQLUnitOfWork(engine)),
        refresh,
        MonitoringService(SQLUnitOfWork(engine), analytics, refresh),
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
    activation: ActivationService
    knowledge: KnowledgeService
    reports: ReportService
    understanding: UnderstandingService
    catalog: CatalogService
    studies: StudyService
    organizations: OrganizationService
    refresh: RefreshService
    monitoring: MonitoringService
