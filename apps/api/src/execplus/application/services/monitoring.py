"""Use case: Computes replayable observations and privately delivers threshold alerts.

What it does: Runs bounded queries with durable claims, current permissions and exact evidence.
"""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.analytics import AnalyticsService, UnitOfWork
from execplus.application.services.refresh import RefreshService, current, editor
from execplus.application.services.workspaces import checked_name
from execplus.domain.errors import ExecPlusError
from execplus.domain.evidence import receipt
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.refresh import (
    AlertEvent,
    AlertRule,
    Monitor,
    Observation,
    RefreshFeed,
    breached,
    decimal_value,
    difference,
    drivers,
    fail,
    periods,
    stale,
)
from execplus.domain.semantics import MetricRequest
from execplus.domain.studies import count_plan, method_request, validated_method
from execplus.domain.understanding import governed_request

Result = tuple[QueryResult, CalculationLineage]


class MonitoringService:
    def __init__(
        self, uow: UnitOfWork, analytics: AnalyticsService, refresh: RefreshService
    ) -> None:
        self.uow, self.analytics, self.refresh = uow, analytics, refresh

    def create(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        name: str,
        method: dict[str, Any],
        relevance: int,
        date_column: str | None,
        segment: str | None,
    ) -> Monitor:
        with self.uow() as repo:
            editor(repo, actor, wid, did)
            feeds = repo.refresh_feeds(wid, did)
            if not feeds:
                fail("refresh_not_configured", "Configure refresh before adding a monitor.", 409)
            feed = feeds[0]
            if not current(repo, feed):
                fail(
                    "definition_conflict", "Review the source and refresh configuration first.", 409
                )
        _, _, table, view = self.analytics.context_at(actor, wid, feed.source)
        method = validated_method(method, view)
        if method["kind"] != "metric" or method["group_by"]:
            fail(
                "invalid_monitor",
                "A monitor requires one scalar metric. Choose a driver segment separately.",
            )
        if not 1 <= relevance <= 5:
            fail("invalid_relevance", "Choose relevance from one to five.")
        if date_column and (
            date_column not in view.dimensions
            or not any(c.name == date_column and c.type == "date" for c in view.columns)
        ):
            fail("invalid_period", "Monthly comparison requires a confirmed date column.")
        if date_column and any(item["column"] == date_column for item in method["filters"]):
            fail("invalid_period", "Monthly windows supply their own date filters.")
        if date_column and len(method["filters"]) > 18:
            fail("invalid_period", "Use at most 18 filters with a monthly comparison.")
        if segment:
            validated_method({**method, "group_by": [segment]}, view)
            if method["aggregation"] != "sum":
                fail("nonadditive_drivers", "Reconciled segment drivers require sum aggregation.")
        request = governed_request(view, table, method_request(method))
        if view.definition and view.definition["grain"] == "inventory_snapshot":
            date_names = {c.name for c in view.columns if c.type == "date"}
            if date_column or not date_names.intersection(item.column for item in request.filters):
                fail(
                    "inventory_period_required",
                    "Inventory monitors need one snapshot date. Monthly sums are unsupported.",
                )
            for column in date_names:
                values = [
                    item
                    for item in request.filters
                    if item.column == column and item.operator.value == "eq"
                ]
                if not values:
                    fail("inventory_period_required", "Filter each snapshot date by equality.")
        method = {
            **method,
            "date_column": date_column,
            "segment": segment,
            "definition_hash": feed.source["definition_hash"],
            "method_version": "monitor-v1",
        }
        now = datetime.now(timezone.utc)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            editor(repo, actor, wid, did)
            latest = repo.refresh_feed(wid, feed.id)
            if latest.version != feed.version or not current(repo, latest):
                fail("refresh_conflict", "The source changed while creating this monitor.", 409)
            if sum(m.enabled for m in repo.monitors(wid, feed.id)) >= 6:
                fail("monitor_limit", "Use at most six active monitors per dataset.", 409)
            monitor = Monitor(
                uuid4(), wid, feed.id, actor.id, checked_name(name), method, relevance, True, now
            )
            repo.add(monitor)
            repo.add(
                Observation(
                    uuid4(),
                    wid,
                    monitor.id,
                    feed.version,
                    feed.source,
                    "pending",
                    0,
                    None,
                    None,
                    {},
                    now,
                )
            )
            self.refresh.audit(repo, actor, wid, "monitor.created", monitor.id)
            return monitor

    def disable(self, actor: User, wid: UUID, mid: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            monitor = repo.monitor(wid, mid)
            feed = repo.refresh_feed(wid, monitor.feed_id)
            editor(repo, actor, wid, feed.dataset_id)
            repo.set_monitor(replace(monitor, enabled=False))
            self.refresh.audit(repo, actor, wid, "monitor.disabled", mid)

    def list_monitors(self, actor: User, wid: UUID, did: UUID) -> dict[str, Any]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            feeds = repo.refresh_feeds(wid, did)
            monitors = repo.monitors(wid, feeds[0].id) if feeds else ()
            output = []
            for monitor in monitors:
                observations = sorted(
                    repo.observations(wid, monitor.id), key=lambda o: o.source_version, reverse=True
                )
                rules = [r for r in repo.alert_rules(wid, monitor.id) if r.owner_id == actor.id]
                output.append(
                    dict(
                        monitor=asdict(monitor),
                        observations=[
                            dict(
                                id=str(o.id),
                                source_version=o.source_version,
                                status=o.status,
                                failure_code=o.evidence.get("failure_code"),
                                created_at=o.created_at,
                            )
                            for o in observations[:50]
                        ],
                        rules=[asdict(r) for r in rules],
                        deliveries=[asdict(e) for r in rules for e in repo.alert_events(wid, r.id)][
                            -100:
                        ],
                    )
                )
            return dict(monitors=output)

    async def _measure(
        self,
        actor: User,
        wid: UUID,
        source: dict[str, Any],
        method: dict[str, Any],
        window: dict[str, str] | None,
    ) -> dict[str, Result]:
        name, scope, table, view = self.analytics.context_at(actor, wid, source)
        base = {
            key: method[key]
            for key in ("kind", "column", "aggregation", "group_by", "filters", "order")
        }
        if window:
            base["filters"] = [
                *base["filters"],
                dict(column=method["date_column"], operator="gte", value=window["start"]),
                dict(column=method["date_column"], operator="lt", value=window["end"]),
            ]
        method_checked = validated_method(base, view)
        request = governed_request(view, table, method_request(method_checked))
        did = UUID(source["dataset_id"])
        values = {
            "value": await self.analytics._execute(
                actor, did, name, scope, table, view, request, "deterministic:monitor-v1"
            )
        }
        for label, present in (("sample", False), ("present", True)):
            plan = count_plan(scope, did, view, request, present_only=present)
            lineage = CalculationLineage(
                plan.query_id,
                wid,
                did,
                name,
                len(table.rows),
                request.metric,
                "count",
                (),
                tuple(f"{f.column} {f.operator.value} {f.value!r}" for f in request.filters),
                plan.sql,
                "deterministic:monitor-v1",
            )
            with self.uow() as repo:
                repo.membership(wid, actor.id)
            try:
                result = await self.analytics.executor.execute(plan, scope, table, view)
            except Exception:
                self.analytics._persist(
                    actor, replace(lineage, receipt=receipt(plan, view.sources, None))
                )
                raise
            lineage = replace(lineage, receipt=receipt(plan, view.sources, result))
            self.analytics._persist(actor, lineage)
            values[label] = result, lineage
        if method["segment"]:
            grouped = MetricRequest(
                request.metric, request.aggregation, (method["segment"],), request.filters
            )
            values["segments"] = await self.analytics._execute(
                actor, did, name, scope, table, view, grouped, "deterministic:monitor-v1"
            )
            group_count = len(values["segments"][0].rows)
            if group_count > 1000 or group_count >= self.analytics.row_limit:
                fail(
                    "monitor_too_many_groups",
                    "Filter to at most 1,000 segments and below the configured query limit.",
                )
        return values

    def _finding(self, evidence: dict[str, Any], results: dict[str, Result]) -> dict[str, Any]:
        value = results["current.value"][0].rows[0][-1]
        sample = int(str(results["current.sample"][0].rows[0][-1]))
        present = int(str(results["current.present"][0].rows[0][-1]))
        limitations = list(evidence["limitations"])
        if sample == 0 or present == 0 or value is None:
            limitations.append("empty_sample")
        if present < sample:
            limitations.append("missing_values")
        if sample < 5:
            limitations.append("small_sample")
        previous = results.get("previous.value")
        prior = previous[0].rows[0][-1] if previous else None
        finding: dict[str, Any] = dict(
            value=str(value) if value is not None else None,
            previous=str(prior) if prior is not None else None,
            sample_count=sample,
            present_count=present,
            missing_count=sample - present,
            limitations=limitations,
            delta=None,
            percent_change=None,
            drivers=[],
            interpretation=(
                "Descriptive arithmetic only. Causes are unverified; "
                "no anomaly or causal inference."
            ),
        )
        if prior is not None and value is not None:
            finding.update(difference(value, prior))
            prior_sample = int(str(results["previous.sample"][0].rows[0][-1]))
            prior_present = int(str(results["previous.present"][0].rows[0][-1]))
            finding.update(previous_sample_count=prior_sample, previous_present_count=prior_present)
            if not prior_present:
                limitations.append("empty_previous_sample")
            if prior_present < prior_sample:
                limitations.append("missing_previous_values")
            if "current.segments" in results and "previous.segments" in results:
                finding["drivers"] = drivers(
                    [list(row) for row in results["current.segments"][0].rows],
                    [list(row) for row in results["previous.segments"][0].rows],
                    finding["delta"],
                )
        elif previous:
            limitations.append("empty_previous_sample")
        else:
            limitations.append("no_baseline")
        return finding

    async def process(
        self,
        now: datetime | None = None,
        *,
        workspace_id: UUID | None = None,
        dataset_id: UUID | None = None,
    ) -> dict[str, int]:
        now = now or datetime.now(timezone.utc)
        counts = dict(complete=0, failed=0, skipped=0)
        with self.uow() as repo:
            jobs = repo.pending_observations(now, workspace_id, dataset_id)
        for wid, oid in jobs:
            if workspace_id is not None and wid != workspace_id:
                continue
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                job = repo.observation(wid, oid)
                if job.status not in {"pending", "running"} or (
                    job.status == "running"
                    and job.claimed_at
                    and job.claimed_at >= now - timedelta(minutes=10)
                ):
                    counts["skipped"] += 1
                    continue
                monitor = repo.monitor(wid, job.monitor_id)
                feed = repo.refresh_feed(wid, monitor.feed_id)
                if dataset_id is not None and feed.dataset_id != dataset_id:
                    continue
                actor = repo.user(monitor.owner_id)
                failure = None
                try:
                    editor(repo, actor, wid, feed.dataset_id)
                except IngestionError:
                    failure = "unauthorized"
                if not monitor.enabled:
                    failure = "monitor_disabled"
                if monitor.method["definition_hash"] != job.source["definition_hash"]:
                    failure = "definition_changed"
                if failure:
                    repo.set_observation(
                        replace(job, status="cancelled", evidence=dict(failure_code=failure))
                    )
                    self.refresh.audit(repo, actor, wid, "observation.cancelled", oid)
                    counts["failed"] += 1
                    continue
                if job.attempts >= 3:
                    repo.set_observation(
                        replace(job, status="failed", evidence=dict(failure_code="retry_limit"))
                    )
                    counts["failed"] += 1
                    continue
                job = replace(
                    job,
                    status="running",
                    attempts=job.attempts + 1,
                    claimed_at=now,
                    claim_id=uuid4(),
                )
                repo.set_observation(job)
                previous = max(
                    (
                        o
                        for o in repo.observations(wid, monitor.id)
                        if o.source_version < job.source_version
                        and o.source["definition_hash"] == job.source["definition_hash"]
                    ),
                    key=lambda o: o.source_version,
                    default=None,
                )
            try:
                windows, limitations = periods(job.source, monitor.method["date_column"])
                results = {
                    "current." + key: value
                    for key, value in (
                        await self._measure(
                            actor, wid, job.source, monitor.method, windows[0] if windows else None
                        )
                    ).items()
                }
                if windows or previous:
                    prior_source = (
                        job.source if windows else previous.source if previous else job.source
                    )
                    results.update(
                        {
                            "previous." + key: value
                            for key, value in (
                                await self._measure(
                                    actor,
                                    wid,
                                    prior_source,
                                    monitor.method,
                                    windows[1] if windows else None,
                                )
                            ).items()
                        }
                    )
                if stale(job.source, feed.freshness_hours, now):
                    limitations.append("stale_source")
                with self.uow() as repo:
                    revision = repo.revision(
                        wid,
                        feed.dataset_id,
                        UUID(job.source["upload_id"]),
                        UUID(job.source["revision_id"]),
                    )
                    meaning = repo.understanding(
                        wid, feed.dataset_id, UUID(job.source["understanding_id"])
                    )
                column = next(
                    c
                    for c in meaning.definition["columns"]
                    if c["name"] == monitor.method["column"]
                )
                evidence = dict(
                    method=monitor.method,
                    periods=windows,
                    period_bounds="start inclusive; end exclusive",
                    coverage=dict(
                        start=job.source.get("coverage_start"),
                        end=job.source.get("coverage_end"),
                        declaration="operator-declared complete dates",
                    ),
                    quality_score=revision.profile["quality_score"],
                    definition_id=str(meaning.id),
                    preparation=revision.recipe,
                    preparation_version=revision.algorithm,
                    unit="records"
                    if monitor.method["aggregation"] == "count"
                    else column["currency"] or column["unit"],
                    limitations=limitations,
                    queries={key: str(value[0].query_id) for key, value in results.items()},
                )
                finding = self._finding(evidence, results)
                with self.uow() as repo:
                    repo.workspace(wid, lock=True)
                    latest = repo.observation(wid, oid)
                    if latest.claim_id != job.claim_id or latest.status != "running":
                        counts["skipped"] += 1
                        continue
                    editor(repo, actor, wid, feed.dataset_id)
                    feed = repo.refresh_feed(wid, feed.id)
                    monitor = repo.monitor(wid, monitor.id)
                    self._deliver(repo, monitor, feed, job, finding, now)
                    repo.set_observation(replace(job, status="complete", evidence=evidence))
                    self.refresh.audit(repo, actor, wid, "observation.complete", oid)
                counts["complete"] += 1
            except Exception as exc:
                with self.uow() as repo:
                    repo.workspace(wid, lock=True)
                    latest = repo.observation(wid, oid)
                    if latest.claim_id == job.claim_id and latest.status == "running":
                        code = exc.code if isinstance(exc, IngestionError) else "calculation_failed"
                        final = (
                            isinstance(exc, (IngestionError, ExecPlusError)) or job.attempts >= 3
                        )
                        repo.set_observation(
                            replace(
                                job,
                                status="failed" if final else "pending",
                                evidence=dict(failure_code=code),
                            )
                        )
                        self.refresh.audit(repo, actor, wid, "observation.failed", oid)
                counts["failed"] += 1
        return counts

    def _deliver(
        self,
        repo: WorkspaceRepository,
        monitor: Monitor,
        feed: RefreshFeed,
        job: Observation,
        finding: dict[str, Any],
        now: datetime,
    ) -> None:
        wid = feed.workspace_id
        for rule in repo.alert_rules(wid, monitor.id):
            if not rule.enabled or rule.created_at > job.created_at:
                continue
            if any(event.observation_id == job.id for event in repo.alert_events(wid, rule.id)):
                continue
            status = "delivered"
            try:
                repo.membership(wid, rule.owner_id)
            except IngestionError:
                status = "unauthorized"
                repo.set_alert_rule(replace(rule, enabled=False))
            if status == "delivered":
                if not monitor.enabled:
                    status = "cancelled"
                elif not current(repo, feed):
                    status = "blocked_definition"
                elif feed.version != job.source_version:
                    status = "superseded"
                elif stale(job.source, feed.freshness_hours, now):
                    status = "blocked_stale"
                elif set(finding["limitations"]) & {
                    "incomplete_periods",
                    "empty_sample",
                    "missing_values",
                }:
                    status = "blocked_coverage"
                elif not breached(finding["value"], rule.operator, rule.threshold):
                    status = "not_triggered"
                elif rule.last_delivered_at and now < rule.last_delivered_at + timedelta(
                    minutes=rule.cooldown_minutes
                ):
                    status = "suppressed_cooldown"
            repo.add(AlertEvent(uuid4(), wid, rule.id, job.id, status, None, now))
            if status == "delivered":
                repo.set_alert_rule(replace(rule, last_delivered_at=now))
            self.refresh.audit(repo, repo.user(rule.owner_id), wid, "alert." + status, rule.id)

    def subscribe(
        self,
        actor: User,
        wid: UUID,
        mid: UUID,
        operator: str,
        threshold: str,
        cooldown_minutes: int,
    ) -> AlertRule:
        threshold = str(decimal_value(threshold))
        breached("0", operator, threshold)
        if not 1 <= cooldown_minutes <= 10080:
            fail("invalid_cooldown", "Use a cooldown between 1 and 10,080 minutes.")
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            monitor = repo.monitor(wid, mid)
            if not monitor.enabled:
                fail("monitor_disabled", "Choose an active monitor.", 409)
            rules = [r for r in repo.alert_rules(wid, mid) if r.owner_id == actor.id and r.enabled]
            for rule in rules:
                if (rule.operator, rule.threshold, rule.cooldown_minutes) == (
                    operator,
                    threshold,
                    cooldown_minutes,
                ):
                    return rule
            if len(rules) >= 5:
                fail("alert_limit", "Use at most five active alerts per monitor.", 409)
            rule = AlertRule(
                uuid4(),
                wid,
                mid,
                actor.id,
                operator,
                threshold,
                cooldown_minutes,
                True,
                None,
                datetime.now(timezone.utc),
            )
            repo.add(rule)
            self.refresh.audit(repo, actor, wid, "alert.subscribed", rule.id)
            return rule

    def unsubscribe(self, actor: User, wid: UUID, rid: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            rule = repo.alert_rule(wid, rid)
            if rule.owner_id != actor.id:
                fail("not_found", "Alert not found.", 404)
            repo.set_alert_rule(replace(rule, enabled=False))
            self.refresh.audit(repo, actor, wid, "alert.unsubscribed", rid)

    def read(self, actor: User, wid: UUID, eid: UUID) -> None:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            event = repo.alert_event(wid, eid)
            rule = repo.alert_rule(wid, event.rule_id)
            if rule.owner_id != actor.id:
                fail("not_found", "Alert not found.", 404)
            if event.status == "delivered" and not event.read_at:
                repo.set_alert_event(replace(event, read_at=datetime.now(timezone.utc)))
                self.refresh.audit(repo, actor, wid, "alert.read", eid)

    async def open(
        self, actor: User, wid: UUID, oid: UUID
    ) -> tuple[dict[str, Any], dict[str, Result]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            job = repo.observation(wid, oid)
            monitor = repo.monitor(wid, job.monitor_id)
            feed = repo.refresh_feed(wid, monitor.feed_id)
        if job.status != "complete":
            return dict(observation=asdict(job), monitor=asdict(monitor), finding=None), {}
        results = {}
        for key, qid in job.evidence["queries"].items():
            with self.uow() as repo:
                repo.membership(wid, actor.id)
            results[key] = await self.analytics.replay(actor, wid, UUID(qid))
        finding = self._finding(job.evidence, results)
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            feed = repo.refresh_feed(wid, monitor.feed_id)
            if (
                stale(job.source, feed.freshness_hours, datetime.now(timezone.utc))
                and "stale_source" not in finding["limitations"]
            ):
                finding["limitations"].append("stale_source")
            if feed.version != job.source_version:
                finding["limitations"].append("historical_snapshot")
            if not current(repo, feed):
                finding["limitations"].append("current_definition_needs_review")
            self.refresh.audit(repo, actor, wid, "observation.opened", oid)
        return dict(observation=asdict(job), monitor=asdict(monitor), finding=finding), results

    async def ranked(self, actor: User, wid: UUID, did: UUID) -> list[dict[str, Any]]:
        with self.uow() as repo:
            repo.membership(wid, actor.id)
            repo.dataset(wid, did)
            feeds = repo.refresh_feeds(wid, did)
            monitors = repo.monitors(wid, feeds[0].id) if feeds else ()
            ids = []
            for monitor in monitors:
                if monitor.enabled:
                    latest = max(
                        repo.observations(wid, monitor.id),
                        key=lambda o: o.source_version,
                        default=None,
                    )
                    if latest:
                        ids.append(latest.id)
        values = [(await self.open(actor, wid, oid))[0] for oid in ids]

        def rank(value: dict[str, Any]) -> tuple[int, Decimal, Decimal]:
            finding = value["finding"] or {}
            magnitude = abs(Decimal(finding.get("percent_change") or "0"))
            return (
                -value["monitor"]["relevance"],
                -magnitude,
                -Decimal(str(value["observation"]["evidence"].get("quality_score", 0))),
            )

        with self.uow() as repo:
            repo.membership(wid, actor.id)
        return sorted(values, key=rank)
