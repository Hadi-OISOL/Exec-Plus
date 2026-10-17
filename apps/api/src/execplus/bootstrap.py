"""Use case: Composes provider implementations from validated settings.

What it does: Selects disabled, local, or hosted model adapters at the application edge.
"""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import boto3
from botocore.config import Config
from sqlalchemy import Engine, create_engine

from execplus import __version__
from execplus.application.ports import IdentityProvider, LanguageModel
from execplus.application.services.access_policies import AccessPolicyService
from execplus.application.services.accounts import AccountService
from execplus.application.services.activation import ActivationService
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.answers import AnswerAssembler
from execplus.application.services.artifacts import ArtifactService
from execplus.application.services.catalog import CatalogService
from execplus.application.services.company_consolidation import CompanyConsolidationService
from execplus.application.services.compute import ComputeBroker, ComputeEngine
from execplus.application.services.consolidation_exports import ConsolidationExportService
from execplus.application.services.data_brief import DataBriefService
from execplus.application.services.decision_analysis import DecisionAnalysisService
from execplus.application.services.document_answers import DocumentAnswerService
from execplus.application.services.forecasts import ForecastService
from execplus.application.services.health import HealthService
from execplus.application.services.incidents import IncidentService
from execplus.application.services.integration_access import IntegrationAccessService
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.jobs import JobService
from execplus.application.services.joins import JoinService
from execplus.application.services.knowledge import KnowledgeService
from execplus.application.services.monitoring import MonitoringService
from execplus.application.services.operations import OperationsService
from execplus.application.services.patterns import PatternService
from execplus.application.services.pdf_exports import PdfExportService
from execplus.application.services.plans import PlanService
from execplus.application.services.product_usage import ProductUsageService
from execplus.application.services.refresh import RefreshService
from execplus.application.services.reports import ReportService
from execplus.application.services.result_exports import ResultExportService
from execplus.application.services.saved_items import SavedItemService
from execplus.application.services.source_imports import SourceImportService
from execplus.application.services.studies import OrganizationService, StudyService
from execplus.application.services.summaries import SummaryService
from execplus.application.services.threads import ThreadService
from execplus.application.services.understanding import UnderstandingService
from execplus.application.services.usage_metering import UsageMeteringService
from execplus.application.services.webhooks import WebhookService
from execplus.application.services.workspaces import WorkspaceService
from execplus.config import Settings
from execplus.domain.compute import ComputeCapabilities, ComputeOperation, QueryBudget
from execplus.infrastructure.allocation.cp_sat import CpSatAllocationSolver
from execplus.infrastructure.email import DisabledEmailDelivery, SMTPEmailDelivery
from execplus.infrastructure.exports.portable import PortableRenderer
from execplus.infrastructure.exports.reportlab_pdf import ReportLabPdfRenderer
from execplus.infrastructure.file_parser import StructuredFileParser
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.infrastructure.integrations.webhook_http import PinnedWebhookTransport
from execplus.infrastructure.knowledge import ReferenceHybridRanker
from execplus.infrastructure.models.disabled import DisabledLanguageModel
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel
from execplus.infrastructure.object_storage import S3ObjectStorage
from execplus.infrastructure.passwords import ScryptPasswords
from execplus.infrastructure.persistence.accounts import SQLAccountStore
from execplus.infrastructure.persistence.consolidations import SQLConsolidationStore
from execplus.infrastructure.persistence.incidents import SQLIncidentStore
from execplus.infrastructure.persistence.integrations import SQLIntegrationStore
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.persistence.usage_metering import SQLUsageUnitOfWork
from execplus.infrastructure.query.duckdb_executor import DuckDBQueryExecutor
from execplus.infrastructure.readiness import DatabaseProbe, StorageProbe
from execplus.infrastructure.release_gate import require_production_evidence
from execplus.infrastructure.sources.postgres import controlled_extractor
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics


def build_language_model(
    settings: Settings,
    max_output_tokens: int | None = None,
    timeout_seconds: float = 60.0,
    metering: UsageMeteringService | None = None,
) -> LanguageModel:
    if settings.llm_mode == "disabled":
        return DisabledLanguageModel()
    return OpenAICompatibleLanguageModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        small_model=settings.llm_small_model,
        large_model=settings.llm_large_model,
        provider_name=settings.llm_mode,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens or settings.llm_max_output_tokens,
        reasoning_effort=settings.llm_reasoning_effort,
        json_mode=settings.llm_json_mode,
        metering=metering,
    )


def build_selection_model(
    settings: Settings, metering: UsageMeteringService | None = None
) -> LanguageModel | None:
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
        metering=metering,
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
    budget = QueryBudget(
        timeout_seconds=settings.query_timeout_seconds,
        memory_limit_mb=settings.query_memory_limit_mb,
        threads=settings.query_threads,
        input_rows=settings.query_input_rows,
        input_cells=settings.query_input_cells,
        result_rows=settings.query_result_rows,
    )
    executor = ComputeBroker(
        {
            "duckdb": ComputeEngine(
                ComputeCapabilities("duckdb", frozenset(ComputeOperation), budget),
                DuckDBQueryExecutor(budget.timeout_seconds, budget.memory_limit_mb, budget=budget),
            )
        },
        "duckdb",
    )
    analytics = AnalyticsService(
        SQLUnitOfWork(engine),
        storage,
        parser,
        executor,
        AnswerAssembler(),
        settings.query_row_limit,
    )
    usage_metering = UsageMeteringService(SQLUsageUnitOfWork(engine))
    model = build_language_model(settings, metering=usage_metering)
    selector = build_selection_model(settings, metering=usage_metering)
    knowledge = KnowledgeService(SQLUnitOfWork(engine), storage, ReferenceHybridRanker())
    intent_router = IntentRouterService(
        model,
        analytics,
        selector,
        DocumentAnswerService(knowledge, model),
        interpretation_enabled=settings.llm_mode != "disabled",
        patterns=PatternService(SQLUnitOfWork(engine), analytics, ScipyPatternStatistics()),
    )
    uploads = WorkspaceService(SQLUnitOfWork(engine), storage, parser, settings.max_upload_bytes)
    refresh = RefreshService(SQLUnitOfWork(engine), uploads, analytics)
    threads = ThreadService(SQLUnitOfWork(engine), intent_router)
    pdf_exports = PdfExportService(SQLUnitOfWork(engine), threads, ReportLabPdfRenderer())
    threads.pdf_exports = pdf_exports
    intent_router.report_exports_enabled = True
    operations = OperationsService(SQLUnitOfWork(engine))
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
        threads,
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
        ArtifactService(SQLUnitOfWork(engine)),
        JobService(
            SQLUnitOfWork(engine),
            threads,
            workspace_limit=settings.jobs_workspace_limit,
            lease_seconds=settings.jobs_lease_seconds,
            timeout_seconds=settings.jobs_timeout_seconds,
            queue_limit=settings.jobs_queue_limit,
        ),
        ForecastService(SQLUnitOfWork(engine), analytics),
        operations,
        ProductUsageService(SQLUnitOfWork(engine), operations),
        DecisionAnalysisService(SQLUnitOfWork(engine), analytics, CpSatAllocationSolver()),
        DataBriefService(
            SQLUnitOfWork(engine),
            build_language_model(
                settings, settings.data_brief_max_output_tokens, 120.0, usage_metering
            ),
            storage,
            parser,
            settings.data_brief_sample_values,
            settings.llm_mode != "disabled",
        ),
        pdf_exports,
        usage_metering,
        settings.integration_allow_loopback,
        settings.webhook_master_secret,
        settings.webhook_destinations,
        source_secret_directory=settings.source_secret_directory,
        source_allow_test_loopback=settings.source_allow_test_loopback,
        local_registration_enabled=settings.local_registration_enabled,
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
    artifacts: ArtifactService
    jobs: JobService
    forecasts: ForecastService
    operations: OperationsService
    product_usage: ProductUsageService
    decision_analysis: DecisionAnalysisService
    data_brief: DataBriefService
    pdf_exports: PdfExportService
    usage_metering: UsageMeteringService
    integration_allow_loopback: bool = False
    webhook_master_secret: str = field(default="", repr=False)
    webhook_destinations: dict[str, str] | None = None

    source_secret_directory: str = field(default="/run/execplus/source-secrets", repr=False)
    source_allow_test_loopback: bool = False
    local_registration_enabled: bool = True

    @cached_property
    def plans(self) -> PlanService:
        return PlanService(SQLUnitOfWork(self.engine))

    @cached_property
    def accounts(self) -> AccountService:
        return AccountService(
            SQLAccountStore(self.engine),
            ScryptPasswords(),
            registration_enabled=self.local_registration_enabled,
        )

    @cached_property
    def source_imports(self) -> SourceImportService:
        url = self.engine.url
        extractor = controlled_extractor(
            Path(self.source_secret_directory),
            url.host or "localhost",
            url.port or 5432,
            url.database or "execplus",
            local_test=self.source_allow_test_loopback,
        )
        return SourceImportService(
            SQLUnitOfWork(self.engine), extractor, self.service, self.refresh
        )

    @cached_property
    def integration_access(self) -> IntegrationAccessService:
        return IntegrationAccessService(
            SQLIntegrationStore(self.engine),
            self.studies,
            allow_local_origins=self.integration_allow_loopback,
        )

    @cached_property
    def webhooks(self) -> WebhookService:
        destinations = self.webhook_destinations or {}
        transport = PinnedWebhookTransport(
            destinations, allow_local=self.integration_allow_loopback
        )
        return WebhookService(
            SQLIntegrationStore(self.engine),
            transport,
            self.webhook_master_secret.encode(),
            tuple(transport.destinations),
            allow_local=self.integration_allow_loopback,
        )

    @cached_property
    def incidents(self) -> IncidentService:
        return IncidentService(SQLIncidentStore(self.engine))

    @cached_property
    def access_policies(self) -> AccessPolicyService:
        return AccessPolicyService(SQLUnitOfWork(self.engine))

    @cached_property
    def result_exports(self) -> ResultExportService:
        return ResultExportService(
            SQLUnitOfWork(self.engine),
            self.pdf_exports,
            self.analytics,
            self.studies,
            self.forecasts,
            self.decision_analysis,
            PortableRenderer(),
        )

    @cached_property
    def consolidations(self) -> CompanyConsolidationService:
        return CompanyConsolidationService(SQLConsolidationStore(self.engine), self.analytics)

    @cached_property
    def consolidation_exports(self) -> ConsolidationExportService:
        return ConsolidationExportService(self.consolidations, self.result_exports)
