"""Use case: Saves and reopens private, source-backed company consolidations.

What it does: Projects complete confirmed ledgers with private receipts, applies
explicit worksheet inputs and rechecks every company under ordered short locks.
"""

import asyncio
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.consolidation_ports import ConsolidationRepository, ConsolidationStore
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.dataset_access import authorize_sources, require_full_access
from execplus.application.services.forecasts import read_complete
from execplus.application.services.workspaces import checked_name
from execplus.domain.company_consolidation import CompanyLedger, LedgerRow, consolidate
from execplus.domain.consolidation_projection import exact_ledger_rows, ledger_plan
from execplus.domain.consolidation_records import ConsolidationRun
from execplus.domain.decision_analysis import checksum
from execplus.domain.evidence import receipt
from execplus.domain.exports import exact_text
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult


def unavailable() -> IngestionError:
    return IngestionError(
        "consolidation_unavailable", "This private worksheet is unavailable.", 404
    )


def changed() -> IngestionError:
    return IngestionError(
        "consolidation_source_changed", "A company source or access changed. Review it again.", 409
    )


class CompanyConsolidationService:
    def __init__(self, store: ConsolidationStore, analytics: AnalyticsService) -> None:
        self.store, self.analytics = store, analytics

    @staticmethod
    def _display(raw: dict[str, Any], result: QueryResult) -> dict[str, Any]:
        return {
            "company_id": raw["workspace_id"],
            "query_id": str(result.query_id),
            "columns": list(result.columns),
            "rows": [
                [None if item is None else exact_text(item) for item in row] for row in result.rows
            ],
        }

    def _company(
        self, repo: ConsolidationRepository, actor: User, oid: UUID, raw: dict[str, Any]
    ) -> dict[str, Any]:
        wid, did, uid = (UUID(raw[key]) for key in ("workspace_id", "dataset_id", "upload_id"))
        member = repo.membership(wid, actor.id)
        department = repo.department(wid)
        if not department or department.organization_id != oid:
            raise unavailable()
        repo.organization(oid)
        require_full_access(repo, actor, wid, did)
        repo.upload(wid, did, uid)
        return {
            "department": asdict(department),
            "membership_epoch": member.created_at.isoformat(),
            "membership_role": member.role,
        }

    @staticmethod
    def _json_context(value: dict[str, Any]) -> dict[str, Any]:
        return {
            **value,
            "department": {key: str(item) for key, item in value["department"].items()},
        }

    def _current(
        self,
        repo: ConsolidationRepository,
        actor: User,
        raw: dict[str, Any],
        source: dict[str, str],
    ) -> bool:
        wid, did, uid = (UUID(raw[key]) for key in ("workspace_id", "dataset_id", "upload_id"))
        _, current = self.analytics._current_description_source(repo, actor, wid, did, uid)
        feeds = repo.refresh_feeds(wid, did)
        return current == (source,) and all(
            str(feed.source["upload_id"]) == str(uid) for feed in feeds
        )

    def _check(
        self,
        repo: ConsolidationRepository,
        actor: User,
        oid: UUID,
        companies: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        *,
        require_current: bool,
        lock: bool = True,
    ) -> bool:
        if len(companies) != len(evidence):
            raise changed()
        if lock:
            for wid in sorted({UUID(item["workspace_id"]) for item in companies}, key=str):
                repo.workspace(wid, lock=True)
        current = True
        for raw, saved in zip(companies, evidence, strict=True):
            context = self._json_context(self._company(repo, actor, oid, raw))
            if context != saved["context"]:
                raise unavailable()
            wid = UUID(raw["workspace_id"])
            source = saved["source"]
            if any(
                source[key] != raw[key]
                for key in ("dataset_id", "upload_id", "revision_id", "understanding_id")
            ):
                raise changed()
            authorize_sources(repo, actor, wid, [source])
            did, uid = UUID(raw["dataset_id"]), UUID(raw["upload_id"])
            upload = repo.upload(wid, did, uid)
            revision = repo.revision(wid, did, uid, UUID(source["revision_id"]))
            meaning = repo.understanding(wid, did, UUID(source["understanding_id"]))
            if (
                upload.checksum != source["source_checksum"]
                or revision.source_checksum != source["source_checksum"]
                or revision.output_checksum != source["output_checksum"]
                or meaning.state != "confirmed"
                or meaning.revision_id != revision.id
                or ("definition" in saved and meaning.definition != saved["definition"])
            ):
                raise changed()
            is_current = self._current(repo, actor, raw, source)
            if require_current and not is_current:
                raise changed()
            current = current and is_current
        return current

    def options(self, actor: User, oid: UUID) -> dict[str, Any]:
        with self.store.transaction() as repo:
            if oid not in {item.id for item in repo.organizations(actor.id)}:
                raise unavailable()
            organization = repo.organization(oid)
            companies = []
            snapshots = []
            for department in repo.departments(oid, actor.id):
                member = repo.membership(department.workspace_id, actor.id)
                references = []
                datasets = []
                for dataset in repo.datasets(department.workspace_id):
                    try:
                        access = require_full_access(
                            repo, actor, department.workspace_id, dataset.id
                        )
                    except IngestionError:
                        continue
                    references.append((dataset.id, access.reference()))
                    datasets.append(
                        {
                            "id": str(dataset.id),
                            "name": dataset.name,
                            "uploads": [
                                {"id": str(item.id), "filename": item.filename}
                                for item in repo.uploads(department.workspace_id, dataset.id)
                            ],
                        }
                    )
                companies.append(
                    {
                        "workspace_id": str(department.workspace_id),
                        "name": department.name,
                        "datasets": datasets,
                    }
                )
                snapshots.append((department, member, references))
        with self.store.transaction() as repo:
            for department, _, _ in sorted(snapshots, key=lambda item: str(item[0].workspace_id)):
                repo.workspace(department.workspace_id, lock=True)
            if repo.organization(oid) != organization:
                raise unavailable()
            for department, member, references in snapshots:
                wid = department.workspace_id
                if repo.department(wid) != department or repo.membership(wid, actor.id) != member:
                    raise unavailable()
                for did, reference in references:
                    if require_full_access(repo, actor, wid, did).reference() != reference:
                        raise unavailable()
        return {"organization": asdict(organization), "companies": companies}

    async def source_options(self, actor: User, oid: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        with self.store.transaction() as repo:
            snapshot = self._json_context(self._company(repo, actor, oid, raw))
        wid, did, uid = (UUID(raw[key]) for key in ("workspace_id", "dataset_id", "upload_id"))
        context = await read_complete(lambda: self.analytics.describe(actor, wid, did, uid))
        if context.state != "confirmed":
            raise IngestionError(
                "consolidation_meaning", "Confirm the ledger's field meanings first.", 422
            )
        source = context.view.sources[0]
        selected = {
            **raw,
            "revision_id": source["revision_id"],
            "understanding_id": source["understanding_id"],
        }
        with self.store.transaction() as repo:
            self._check(
                repo,
                actor,
                oid,
                [selected],
                [{"context": snapshot, "source": source}],
                require_current=True,
            )
        columns = (context.definition or {}).get("columns", [])
        return {
            **selected,
            "name": snapshot["department"]["name"],
            "row_count": context.profile["row_count"],
            "accounts": [
                item["name"]
                for item in columns
                if item["role"] in {"dimension", "identifier", "ordinal"}
            ],
            "counterparties": [
                item["name"] for item in columns if item["role"] in {"dimension", "identifier"}
            ],
            "amounts": [
                {"name": item["name"], "currency": item["currency"] or item["unit"]}
                for item in columns
                if item["role"] == "metric"
                and item["name"] in context.view.metrics
                and not item["unit_column"]
                and (item["currency"] or item["unit"])
            ],
        }

    async def _project(
        self, actor: User, oid: UUID, raw: dict[str, Any], saved: dict[str, Any] | None = None
    ) -> tuple[QueryResult, dict[str, Any]]:
        with self.store.transaction() as repo:
            snapshot = self._json_context(self._company(repo, actor, oid, raw))
        wid, did, uid = (UUID(raw[key]) for key in ("workspace_id", "dataset_id", "upload_id"))
        if saved:
            name, scope, table, view = await read_complete(
                lambda: self.analytics.context_at(actor, wid, saved["source"])
            )
        else:
            context, table, scope = await read_complete(
                lambda: self.analytics.descriptive_snapshot(actor, wid, did, uid)
            )
            if context.state != "confirmed":
                raise changed()
            name, view = context.name, context.view
        source = view.sources[0]
        evidence = {"context": snapshot, "source": source, "definition": view.definition}
        with self.store.transaction() as repo:
            self._check(repo, actor, oid, [raw], [saved or evidence], require_current=not saved)
        plan = ledger_plan(scope, did, view, table, raw)
        if saved:
            plan = replace(plan, query_id=UUID(saved["query_id"]))
            with self.store.transaction() as repo:
                record = repo.query_execution(wid, plan.query_id)
            if (
                record.actor_id != actor.id
                or record.aggregation != "analysis"
                or record.dataset_id != did
                or record.sql != plan.sql
                or saved["definition"] != view.definition
                or saved["context"] != snapshot
            ):
                raise changed()
        lineage = CalculationLineage(
            plan.query_id,
            wid,
            did,
            name,
            len(table.rows),
            raw["amount_column"],
            "analysis",
            (),
            (),
            plan.sql,
            "deterministic:company-consolidation-v1",
        )
        try:
            result = await self.analytics.executor.execute(plan, scope, table, view)
        except (Exception, asyncio.CancelledError):
            if not saved:
                self.analytics._persist(
                    actor, replace(lineage, receipt=receipt(plan, view.sources, None))
                )
            raise
        actual = receipt(plan, view.sources, result)
        if saved:
            if actual != record.receipt:
                raise changed()
        else:
            self.analytics._persist(actor, replace(lineage, receipt=actual))
        exact_ledger_rows(result)
        if len(result.rows) != len(table.rows):
            raise IngestionError(
                "consolidation_population", "The complete ledger is required.", 422
            )
        with self.store.transaction() as repo:
            self._check(repo, actor, oid, [raw], [saved or evidence], require_current=not saved)
        return result, {**evidence, "query_id": str(plan.query_id)}

    async def preview_company(self, actor: User, oid: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        result, evidence = await self._project(actor, oid, raw)
        rows = exact_ledger_rows(result)
        return {
            "accounts": sorted({row[0] for row in rows}),
            "counterparties": sorted({row[2] for row in rows if row[2] is not None}),
            "row_count": len(rows),
            "query_id": evidence["query_id"],
            "source": evidence["source"],
        }

    @staticmethod
    def _ledger(
        raw: dict[str, Any], name: str, value: QueryResult, company_ids: set[str]
    ) -> CompanyLedger:
        mappings = raw.get("counterparties", [])
        aliases = {item["raw_value"]: item["company_id"] for item in mappings}
        rows = exact_ledger_rows(value)
        if (
            len(aliases) != len(mappings)
            or set(aliases) - {row[2] for row in rows if row[2] is not None}
            or any(
                target not in company_ids or target == raw["workspace_id"]
                for target in aliases.values()
            )
        ):
            raise IngestionError(
                "consolidation_counterparty",
                "Map existing counterparties to another selected company.",
                422,
            )
        if raw.get("coverage_confirmed") is not True:
            raise IngestionError(
                "consolidation_coverage",
                "Confirm that each file is a complete prepared ledger for its declared period.",
                422,
            )
        try:
            period_start, period_end = (
                date.fromisoformat(raw["period_start"]),
                date.fromisoformat(raw["period_end"]),
            )
        except (ValueError, TypeError):
            raise IngestionError(
                "consolidation_period", "Choose valid calendar dates for the ledger period.", 422
            ) from None
        return CompanyLedger(
            raw["workspace_id"],
            name,
            raw["currency"],
            period_start,
            period_end,
            raw["sign_convention"],
            tuple(
                LedgerRow(account, amount, aliases.get(party) if party else None)
                for account, amount, party in rows
            ),
        )

    async def create(self, actor: User, oid: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        name = checked_name(raw["name"])
        companies = raw["companies"]
        company_ids = {item["workspace_id"] for item in companies}
        if not 2 <= len(companies) <= 8 or len(company_ids) != len(companies):
            raise IngestionError(
                "consolidation_companies", "Choose two to eight different companies.", 422
            )
        ledgers, evidence, source_rows = [], [], []
        for item in companies:
            result, item_evidence = await self._project(actor, oid, item)
            ledgers.append(
                self._ledger(
                    item, item_evidence["context"]["department"]["name"], result, company_ids
                )
            )
            evidence.append(item_evidence)
            source_rows.append(self._display(item, result))
        calculated = await read_complete(lambda: consolidate(tuple(ledgers), raw["worksheet"]))
        now = datetime.now(timezone.utc)
        run = ConsolidationRun(
            uuid4(),
            oid,
            actor.id,
            name,
            raw,
            {
                "version": "consolidation-evidence-v1",
                "companies": evidence,
                "request_checksum": checksum(raw),
                "result_checksum": checksum(calculated),
            },
            calculated,
            now,
        )
        with self.store.transaction() as repo:
            self._check(repo, actor, oid, companies, evidence, require_current=True)
            repo.lock_consolidation_owner(oid, actor.id)
            if len(repo.consolidation_runs(oid, actor.id)) >= 50:
                raise IngestionError(
                    "consolidation_limit",
                    "Use at most 50 saved worksheets per organization and person.",
                    422,
                )
            repo.add_consolidation_run(run)
            for wid in sorted(company_ids):
                repo.add(
                    AuditEvent(
                        uuid4(),
                        UUID(wid),
                        actor.id,
                        "consolidation.created",
                        "consolidation",
                        run.id,
                        now,
                    )
                )
        return {"run": asdict(run), "current": True, "source_rows": source_rows}

    def list(self, actor: User, oid: UUID) -> list[dict[str, Any]]:
        with self.store.transaction() as repo:
            if oid not in {item.id for item in repo.organizations(actor.id)}:
                raise unavailable()
            runs = repo.consolidation_runs(oid, actor.id)
        values = []
        for run in runs:
            with self.store.transaction() as repo:
                try:
                    current = self._check(
                        repo,
                        actor,
                        oid,
                        run.request["companies"],
                        run.evidence["companies"],
                        require_current=False,
                    )
                except IngestionError:
                    continue
                values.append(
                    {
                        "id": str(run.id),
                        "name": run.name,
                        "created_at": run.created_at,
                        "current": current,
                    }
                )
        return values

    async def open(self, actor: User, oid: UUID, rid: UUID) -> dict[str, Any]:
        with self.store.transaction() as repo:
            run = repo.consolidation_run(oid, rid, actor.id)
            self._check(
                repo,
                actor,
                oid,
                run.request["companies"],
                run.evidence["companies"],
                require_current=False,
            )
        if (
            run.evidence.get("version") != "consolidation-evidence-v1"
            or checksum(run.request) != run.evidence["request_checksum"]
            or checksum(run.result) != run.evidence["result_checksum"]
        ):
            raise changed()
        companies = run.request["companies"]
        ids = {item["workspace_id"] for item in companies}
        ledgers, source_rows = [], []
        for raw, saved in zip(companies, run.evidence["companies"], strict=True):
            value, _ = await self._project(actor, oid, raw, saved)
            source_rows.append(self._display(raw, value))
            ledgers.append(self._ledger(raw, saved["context"]["department"]["name"], value, ids))
        calculated = await read_complete(
            lambda: consolidate(tuple(ledgers), run.request["worksheet"])
        )
        if calculated != run.result:
            raise changed()
        with self.store.transaction() as repo:
            current = self._check(
                repo, actor, oid, companies, run.evidence["companies"], require_current=False
            )
        return {"run": asdict(run), "current": current, "source_rows": source_rows}
