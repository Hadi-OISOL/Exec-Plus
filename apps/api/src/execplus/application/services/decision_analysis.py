"""Use case: Saves and reopens private anomaly and allocation evidence with human review.

What it does: Governs source queries, exact replay, current-source approval and bounded history.
"""

import asyncio
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.application.services.forecasts import ForecastService, read_complete
from execplus.application.services.studies import audit
from execplus.application.services.workspaces import checked_name
from execplus.domain.allocation_constraints import (
    RULE_METHOD,
    allocate_selection_rules,
    selection_rules,
    verify_selection_result,
)
from execplus.domain.analysis_extensions import (
    RESOURCE_METHOD,
    SEGMENT_METHOD,
    allocate_resources,
    detect_segments,
)
from execplus.domain.analysis_queries import analysis_plan, scenario_coverage_plans
from execplus.domain.analysis_readiness import fixed_unit_columns
from execplus.domain.decision_analysis import (
    METHODS,
    AnalysisReview,
    AnalysisRun,
    allocate,
    checksum,
    detect_distribution,
)
from execplus.domain.errors import AuthorizationError, ClarificationRequiredError
from execplus.domain.evidence import receipt
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.scenarios import COMPOUND_METHOD, DAILY_METHOD, alternatives, compare_scenarios
from execplus.domain.scenarios import METHOD as SCENARIO_METHOD

REGISTERED_METHODS = {**METHODS, "scenario_comparison": SCENARIO_METHOD}


def method_version(raw: dict[str, Any]) -> str:
    if raw["kind"] == "scenario_comparison" and any(
        item["operation"] == "daily_change" for item in raw["alternatives"]
    ):
        return DAILY_METHOD
    if raw["kind"] == "robust_distribution" and raw.get("segment_column"):
        return SEGMENT_METHOD
    if raw["kind"] == "bounded_allocation" and (raw.get("prerequisites") or raw.get("exclusions")):
        return RULE_METHOD
    if raw["kind"] == "bounded_allocation" and raw.get("resource_column"):
        return RESOURCE_METHOD
    if raw["kind"] == "scenario_comparison" and any(
        item["operation"] == "compound_percent" for item in raw["alternatives"]
    ):
        return COMPOUND_METHOD
    return REGISTERED_METHODS[raw["kind"]]


def calculate(raw: dict[str, Any], value: QueryResult) -> dict[str, Any]:
    if raw["kind"] == "scenario_comparison":
        return compare_scenarios(raw, value.rows)
    if raw["kind"] == "robust_distribution":
        if raw.get("segment_column"):
            return detect_segments(
                [(None if row[0] is None else str(row[0]), row[1], row[2]) for row in value.rows],
                raw["threshold"],
                raw["materiality"],
                raw["minimum_segment_size"],
            )
        return detect_distribution(
            [(row[0], row[1]) for row in value.rows], raw["threshold"], raw["materiality"]
        )
    candidates: list[tuple[str, object, object]] = []
    for row in value.rows:
        if row[0] is None:
            raise IngestionError(
                "candidate_identity_required", "Every action needs a nonempty identifier.", 422
            )
        candidates.append((str(row[0]), row[1], row[2]))
    supplied = raw["bounds"]
    if len({item["candidate"] for item in supplied}) != len(supplied):
        raise IngestionError("invalid_constraints", "Declare each candidate bound once.", 422)
    if {item["candidate"] for item in supplied} - {row[0] for row in candidates}:
        raise IngestionError(
            "invalid_constraints", "Quantity bounds reference an unknown candidate.", 422
        )
    bounds = {row[0]: (0, raw["maximum_quantity"]) for row in candidates}
    bounds.update({item["candidate"]: (item["minimum"], item["maximum"]) for item in supplied})
    if raw.get("prerequisites") or raw.get("exclusions"):
        rule_rows: list[tuple[str, object, object, object | None]] = [
            (str(row[0]), row[1], row[2], row[3] if raw.get("resource_column") else None)
            for row in value.rows
        ]
        rules = selection_rules(
            {row[0] for row in candidates}, raw.get("prerequisites", []), raw.get("exclusions", [])
        )
        calculated = allocate_selection_rules(
            rule_rows,
            raw["budget"],
            raw["quantum"],
            bounds,
            raw["assumptions_confirmed"],
            raw.get("prerequisites", []),
            raw.get("exclusions", []),
            raw.get("resource_capacity"),
        )
        verify_selection_result(
            rule_rows, raw["budget"], bounds, rules, calculated, raw.get("resource_capacity")
        )
        return calculated
    if raw.get("resource_column"):
        return allocate_resources(
            [(str(row[0]), row[1], row[2], row[3]) for row in value.rows],
            raw["budget"],
            raw["quantum"],
            bounds,
            raw["assumptions_confirmed"],
            raw["resource_capacity"],
        )
    return allocate(candidates, raw["budget"], raw["quantum"], bounds, raw["assumptions_confirmed"])


class DecisionAnalysisService:
    def __init__(self, uow: UnitOfWork, analytics: AnalyticsService) -> None:
        self.uow, self.analytics = uow, analytics
        self.sources = ForecastService(uow, analytics)

    async def options(self, actor: User, wid: UUID, did: UUID, uid: UUID) -> dict[str, Any]:
        context = await read_complete(lambda: self.analytics.describe(actor, wid, did, uid))
        source = context.view.sources[0]
        definition = context.view.definition or {}
        columns = definition.get("columns", [])
        metrics = [
            dict(name=c["name"], unit=c["currency"] or c["unit"])
            for c in fixed_unit_columns(context)
        ]
        return dict(
            state="ready" if context.state == "confirmed" and metrics else "needs_review",
            revision_id=source["revision_id"],
            understanding_id=source.get("understanding_id"),
            metrics=metrics,
            entities=[c["name"] for c in columns if c["role"] in {"dimension", "identifier"}],
            methods=REGISTERED_METHODS,
            extensions=[
                SEGMENT_METHOD,
                RESOURCE_METHOD,
                RULE_METHOD,
                COMPOUND_METHOD,
                DAILY_METHOD,
            ],
            limitations=[
                "Confirm meaning and fixed units before analysis.",
                "Exploratory anomalies are not confirmed errors; "
                "decisions require declared assumptions.",
            ],
        )

    def _current(self, actor: User, wid: UUID, did: UUID, uid: UUID, raw: dict[str, Any]) -> None:
        self.sources._current(actor, wid, did, uid, raw)
        with self.uow() as repo:
            feeds = repo.refresh_feeds(wid, did)
            if any(str(feed.source["upload_id"]) != str(uid) for feed in feeds):
                raise ClarificationRequiredError(
                    "Use the current accepted refresh source before new analysis or approval."
                )

    def _owned(self, actor: User, wid: UUID, did: UUID, rid: UUID) -> AnalysisRun:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            run = repo.analysis_run(wid, rid, actor.id)
            if run.dataset_id != did:
                raise AuthorizationError("Analysis source mismatch")
            repo.upload(wid, did, run.upload_id)
            return run

    def list(self, actor: User, wid: UUID, did: UUID) -> list[dict[str, Any]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            return [
                dict(
                    id=str(r.id),
                    name=r.name,
                    kind=r.kind,
                    created_at=r.created_at,
                    upload_id=str(r.upload_id),
                )
                for r in repo.analysis_runs(wid, did, actor.id)
            ]

    async def create(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, raw: dict[str, Any]
    ) -> dict[str, Any]:
        name = checked_name(raw["name"])
        if raw["kind"] == "scenario_comparison":
            alternatives(raw.get("alternatives"))
            if raw.get("assumptions_confirmed") is not True:
                raise IngestionError(
                    "scenario_assumptions_required", "Confirm hypothetical assumptions.", 422
                )
        self._current(actor, wid, did, uid, raw)
        with self.uow() as repo:
            if len(repo.analysis_runs(wid, did, actor.id)) >= 50:
                raise IngestionError(
                    "analysis_limit", "Use at most 50 saved analyses per dataset/person.", 409
                )
        dataset_name, scope, table, view = await read_complete(
            lambda: self.analytics._context(actor, wid, did, uid)
        )
        if (
            view.sources[0]["revision_id"] != raw["revision_id"]
            or view.sources[0].get("understanding_id") != raw["understanding_id"]
        ):
            raise ClarificationRequiredError("The source changed. Reload analysis options.")
        plan, units = analysis_plan(scope, did, view, table, raw)
        if raw["kind"] == "scenario_comparison" and raw.get("parent_run_id"):
            parent = self._owned(actor, wid, did, UUID(raw["parent_run_id"]))
            await self.open(actor, wid, did, parent.id)
            if (
                parent.kind != "scenario_comparison"
                or any(
                    parent.request.get(key) != raw.get(key)
                    for key in ("metric", "aggregation", "filters")
                )
                or parent.evidence["units"] != units
                or (parent.evidence["definition"] or {}).get("grain")
                != (view.definition or {}).get("grain")
                or next(
                    (
                        c
                        for c in (parent.evidence["definition"] or {}).get("columns", [])
                        if c["name"] == raw["metric"]
                    ),
                    None,
                )
                != next(
                    (
                        c
                        for c in (view.definition or {}).get("columns", [])
                        if c["name"] == raw["metric"]
                    ),
                    None,
                )
                or [
                    m
                    for m in (parent.evidence["definition"] or {}).get("metrics", [])
                    if m.get("column") == raw["metric"]
                ]
                != [
                    m
                    for m in (view.definition or {}).get("metrics", [])
                    if m.get("column") == raw["metric"]
                ]
            ):
                raise IngestionError(
                    "scenario_parent_mismatch",
                    "Use compatible measure, units and filters for a successor.",
                    422,
                )
        lineage = CalculationLineage(
            plan.query_id,
            wid,
            did,
            dataset_name,
            len(table.rows),
            raw.get("metric", raw.get("benefit_column", "")),
            "analysis",
            (),
            (),
            plan.sql,
            "deterministic:"
            + (
                method_version(raw)
                if method_version(raw)
                in {SEGMENT_METHOD, RESOURCE_METHOD, RULE_METHOD, COMPOUND_METHOD, DAILY_METHOD}
                else SCENARIO_METHOD
                if raw["kind"] == "scenario_comparison"
                else "decision-analysis-v1"
            ),
        )
        self._current(actor, wid, did, uid, raw)
        try:
            result = await self.analytics.executor.execute(plan, scope, table, view)
        except (Exception, asyncio.CancelledError):
            self.analytics._persist(
                actor, replace(lineage, receipt=receipt(plan, view.sources, None))
            )
            raise
        self.analytics._persist(
            actor, replace(lineage, receipt=receipt(plan, view.sources, result))
        )
        coverage_ids = []
        if raw["kind"] == "scenario_comparison":
            coverage_values = []
            for coverage_plan in scenario_coverage_plans(scope, did, view, table, raw):
                self._current(actor, wid, did, uid, raw)
                coverage_lineage = replace(
                    lineage, query_id=coverage_plan.query_id, sql=coverage_plan.sql
                )
                try:
                    coverage_result = await self.analytics.executor.execute(
                        coverage_plan, scope, table, view
                    )
                except (Exception, asyncio.CancelledError):
                    self.analytics._persist(
                        actor,
                        replace(
                            coverage_lineage, receipt=receipt(coverage_plan, view.sources, None)
                        ),
                    )
                    raise
                self.analytics._persist(
                    actor,
                    replace(
                        coverage_lineage,
                        receipt=receipt(coverage_plan, view.sources, coverage_result),
                    ),
                )
                if len(coverage_result.rows) != 1 or len(coverage_result.rows[0]) != 1:
                    raise IngestionError(
                        "scenario_coverage", "Complete coverage evidence is required.", 422
                    )
                coverage_values.append(coverage_result.rows[0][0])
                coverage_ids.append(str(coverage_plan.query_id))
            if len(result.rows) != 1 or len(result.rows[0]) != 1:
                raise IngestionError("scenario_coverage", "One complete baseline is required.", 422)
            result = replace(result, rows=((result.rows[0][0], *coverage_values),))
        calculated = await read_complete(lambda: calculate(raw, result))
        await read_complete(
            lambda: self.analytics.recheck_description(actor, wid, did, uid, view.sources)
        )
        evidence: dict[str, Any] = dict(
            query_id=str(plan.query_id),
            sources=list(view.sources),
            definition=view.definition,
            units=units,
            request_checksum=checksum(raw),
            result_checksum=checksum(calculated),
        )
        if raw["kind"] == "scenario_comparison":
            evidence["coverage_query_ids"] = coverage_ids
        run = AnalysisRun(
            uuid4(),
            wid,
            did,
            actor.id,
            uid,
            UUID(raw["revision_id"]),
            UUID(raw["understanding_id"]),
            name,
            raw["kind"],
            method_version(raw),
            raw,
            evidence,
            calculated,
            datetime.now(timezone.utc),
        )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._current(actor, wid, did, uid, raw)
            if len(repo.analysis_runs(wid, did, actor.id)) >= 50:
                raise IngestionError(
                    "analysis_limit", "Use at most 50 saved analyses per dataset/person.", 409
                )
            repo.add(run)
            audit(repo, actor, wid, "analysis.created", run.id)
        return await self._body(actor, run)

    async def _body(self, actor: User, run: AnalysisRun) -> dict[str, Any]:
        try:
            self._current(actor, run.workspace_id, run.dataset_id, run.upload_id, run.request)
            current = True
        except ClarificationRequiredError:
            current = False
        with self.uow() as repo:
            repo.membership(run.workspace_id, actor.id)
            reviews = repo.analysis_reviews(run.workspace_id, run.id, actor.id)
        decisions = [r for r in reviews if r.target == "decision"]
        status = decisions[-1].status if decisions else "pending"
        return dict(
            run=asdict(run),
            current=current,
            review_version=len(reviews),
            decision_status=status,
            approval_effective=current and status == "approved",
            reviews=[asdict(r) for r in reviews],
        )

    async def open(self, actor: User, wid: UUID, did: UUID, rid: UUID) -> dict[str, Any]:
        run = self._owned(actor, wid, did, rid)
        invalid = IngestionError(
            "lineage_mismatch", "The saved analysis evidence is inconsistent.", 409
        )
        try:
            if (
                run.kind != run.request["kind"]
                or run.method_version != method_version(run.request)
                or checksum(run.request) != run.evidence["request_checksum"]
            ):
                raise invalid
            source = run.evidence["sources"][0]
            if (
                len(run.evidence["sources"]) != 1
                or source["dataset_id"] != str(did)
                or source["upload_id"] != str(run.upload_id)
                or source["revision_id"] != str(run.revision_id)
                or source["understanding_id"] != str(run.understanding_id)
            ):
                raise invalid
            if run.request["revision_id"] != str(run.revision_id) or run.request[
                "understanding_id"
            ] != str(run.understanding_id):
                raise invalid
            _, scope, table, view = await read_complete(
                lambda: self.analytics.context_at(actor, wid, source)
            )
            plan, units = analysis_plan(scope, did, view, table, run.request)
            qid = UUID(run.evidence["query_id"])
            with self.uow() as repo:
                record = repo.query_execution(wid, qid)
            saved = record.receipt
            plan = replace(plan, query_id=qid)
            expected = receipt(plan, view.sources, None)
            if (
                record.actor_id != run.owner_id
                or record.dataset_id != did
                or record.sql != plan.sql
                or saved.get("outcome") != "executed"
                or any(
                    saved.get(key) != expected[key] for key in ("version", "sources", "parameters")
                )
                or run.evidence["definition"] != view.definition
                or units != run.evidence["units"]
            ):
                raise invalid
            result = await self.analytics.executor.execute(plan, scope, table, view)
            if receipt(plan, view.sources, result) != saved:
                raise invalid
            if run.kind == "scenario_comparison":
                coverage_ids = run.evidence["coverage_query_ids"]
                if len(coverage_ids) != 2 or len(set([str(qid), *coverage_ids])) != 3:
                    raise invalid
                coverage_values = []
                for index, coverage_plan in enumerate(
                    scenario_coverage_plans(scope, did, view, table, run.request)
                ):
                    coverage_plan = replace(coverage_plan, query_id=UUID(coverage_ids[index]))
                    with self.uow() as repo:
                        coverage_record = repo.query_execution(wid, coverage_plan.query_id)
                    expected_coverage = receipt(coverage_plan, view.sources, None)
                    if (
                        coverage_record.actor_id != run.owner_id
                        or coverage_record.dataset_id != did
                        or coverage_record.sql != coverage_plan.sql
                        or coverage_record.receipt.get("outcome") != "executed"
                        or any(
                            coverage_record.receipt.get(key) != expected_coverage[key]
                            for key in ("version", "sources", "parameters")
                        )
                    ):
                        raise invalid
                    coverage_result = await self.analytics.executor.execute(
                        coverage_plan, scope, table, view
                    )
                    if (
                        receipt(coverage_plan, view.sources, coverage_result)
                        != coverage_record.receipt
                        or len(coverage_result.rows) != 1
                        or len(coverage_result.rows[0]) != 1
                    ):
                        raise invalid
                    coverage_values.append(coverage_result.rows[0][0])
                if len(result.rows) != 1 or len(result.rows[0]) != 1:
                    raise invalid
                result = replace(result, rows=((result.rows[0][0], *coverage_values),))
            rebuilt = await read_complete(lambda: calculate(run.request, result))
            if rebuilt != run.result or checksum(rebuilt) != run.evidence["result_checksum"]:
                raise invalid
        except (KeyError, TypeError, ValueError, IndexError):
            raise invalid from None
        self._owned(actor, wid, did, rid)
        return await self._body(actor, run)

    async def review(
        self, actor: User, wid: UUID, did: UUID, rid: UUID, raw: dict[str, Any]
    ) -> dict[str, Any]:
        body = await self.open(actor, wid, did, rid)
        run = self._owned(actor, wid, did, rid)
        if run.kind == "scenario_comparison":
            raise IngestionError(
                "scenario_not_decision",
                "A hypothetical comparison cannot be approved as a recommendation.",
                422,
            )
        target, status, note = raw["target"], raw["status"], raw["note"].strip()
        if run.kind == "bounded_allocation":
            if target != "decision" or status not in {"pending", "approved", "rejected"}:
                raise IngestionError(
                    "invalid_review", "Approve, reject or reopen this decision.", 422
                )
            if status == "approved" and (not body["current"] or run.result["status"] != "feasible"):
                raise IngestionError(
                    "decision_not_approvable",
                    "Only a current feasible recommendation can be approved.",
                    409,
                )
        elif target not in {f["id"] for f in run.result["findings"]} or status not in {
            "expected",
            "investigate",
            "data_issue",
            "dismissed",
        }:
            raise IngestionError(
                "invalid_review", "Choose a saved finding and a supported feedback label.", 422
            )
        if not note or len(note) > 1000 or "\x00" in note:
            raise IngestionError(
                "review_note_required", "Explain this decision in up to 1,000 characters.", 422
            )
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            self._owned(actor, wid, did, rid)
            history = repo.analysis_reviews(wid, rid, actor.id)
            if len(history) != raw["expected_version"] or len(history) >= 200:
                raise IngestionError(
                    "review_conflict", "Reload review history before saving another decision.", 409
                )
            if status == "approved":
                self._current(actor, wid, did, run.upload_id, run.request)
            if history and history[-1].target == target and history[-1].status == status:
                raise IngestionError(
                    "review_conflict", "This review state is already recorded.", 409
                )
            repo.add(
                AnalysisReview(
                    uuid4(),
                    wid,
                    rid,
                    actor.id,
                    len(history) + 1,
                    target,
                    status,
                    note,
                    datetime.now(timezone.utc),
                )
            )
            audit(repo, actor, wid, "analysis.reviewed", rid)
        return await self._body(actor, run)
