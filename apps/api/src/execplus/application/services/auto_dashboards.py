"""Use case: Gives every dataset an exact dataset brief and a dashboard built for that data.

What it does: Computes the cached dataset-brief-v1 through governed queries, enumerates candidate
tiles, lets a configured model only rank them and title them, executes the picked tiles with
receipts and keeps private, shareable dashboard versions per owner and upload.
"""

import asyncio
import json
from collections import OrderedDict
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.application.ports import LanguageModel, PatternStatistics, WorkspaceRepository
from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.dataset_access import authorize_sources, dataset_access
from execplus.application.services.insights import _run as run_governed
from execplus.application.services.insights import build_insights
from execplus.domain import dataset_brief as briefs
from execplus.domain.auto_dashboard import (
    MAX_TILES,
    ROUTE,
    VERSION,
    AutoDashboard,
    Candidate,
    deterministic_pick,
    enumerate_candidates,
    parse_selection,
    selection_input,
    selection_prompt,
    tile,
)
from execplus.domain.errors import (
    AuthorizationError,
    ClarificationRequiredError,
    ProviderUnavailableError,
    UnsafeQueryError,
    UnsupportedQuestionError,
)
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.insights import queryable
from execplus.domain.models import ModelTier, QueryResult, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import RECORD_COUNT, AggregationKind, MetricRequest

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]
SELECTION_SECONDS = 25.0
CACHE_SIZE = 32
_EXPECTED = (ClarificationRequiredError, UnsafeQueryError, UnsupportedQuestionError)
# shortcut: process-local LRU; API and jobs processes each compute their own copy. Move to
# object storage keyed by the source checksums if briefs become expensive to repeat.
_CACHE: "OrderedDict[str, tuple[dict[str, Any], list[dict[str, Any]]]]" = OrderedDict()


def _key(sources: Any) -> str:
    return json.dumps(sources, sort_keys=True, default=str)


def cached_brief(sources: Any) -> dict[str, Any] | None:
    hit = _CACHE.get(_key(sources))
    return hit[0] if hit else None


def _remember(sources: Any, value: tuple[dict[str, Any], list[dict[str, Any]]]) -> None:
    _CACHE[_key(sources)] = value
    _CACHE.move_to_end(_key(sources))
    while len(_CACHE) > CACHE_SIZE:
        _CACHE.popitem(last=False)


def _blocked(context: DescriptionContext) -> bool:
    return (
        any(source.get("understanding_id") for source in context.view.sources)
        and context.state != "confirmed"
    )


class AutoDashboardService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        analytics: AnalyticsService,
        statistics: PatternStatistics,
        model: LanguageModel | None = None,
        include_values: bool = False,
    ) -> None:
        self.uow = unit_of_work
        self.analytics = analytics
        self.statistics = statistics
        self.model = model
        self.include_values = include_values

    async def _query(
        self,
        actor: User,
        dataset_id: UUID,
        context: DescriptionContext,
        scope: WorkspaceScope,
        table: TableData,
        plan: Any,
        metric: str,
        aggregation: str,
        grouping: tuple[str, ...] = (),
    ) -> QueryResult:
        return await run_governed(
            self.analytics,
            actor,
            dataset_id,
            context.name,
            scope,
            table,
            context.view,
            plan,
            metric,
            aggregation,
            grouping,
        )

    async def _column(
        self,
        actor: User,
        dataset_id: UUID,
        context: DescriptionContext,
        scope: WorkspaceScope,
        table: TableData,
        column: dict[str, Any],
        rows: int,
    ) -> dict[str, Any]:
        name, kind = column["name"], column["type"]
        values = await self._query(
            actor,
            dataset_id,
            context,
            scope,
            table,
            briefs.values_plan(scope, dataset_id, name),
            name,
            "count",
            (name,),
        )
        groups = [(row[0], int(row[-1])) for row in values.rows]  # type: ignore[arg-type]
        if len(groups) <= briefs.GROUP_LIMIT:
            return briefs.stats_from_groups(kind, rows, groups)
        found: dict[str, Any] = {}
        functions = ["COUNT"]
        if kind in briefs.ORDERED:
            functions += ["MIN", "MAX"]
        if kind in briefs.NUMERIC:
            functions.append("SUM")
        for function in functions:
            result = await self._query(
                actor,
                dataset_id,
                context,
                scope,
                table,
                briefs.aggregate_plan(scope, dataset_id, name, function),
                name,
                function.lower(),
            )
            found[function] = result.rows[0][0] if result.rows else None
        top = await self._query(
            actor,
            dataset_id,
            context,
            scope,
            table,
            briefs.top_plan(scope, dataset_id, name),
            name,
            "count",
            (name,),
        )
        return briefs.stats_from_aggregates(
            kind,
            rows,
            int(found["COUNT"] or 0),
            found.get("MIN"),
            found.get("MAX"),
            found.get("SUM"),
            [(row[0], int(row[-1])) for row in top.rows],  # type: ignore[arg-type]
        )

    async def brief(
        self, actor: User, wid: UUID, did: UUID, uid: UUID
    ) -> tuple[dict[str, Any], list[dict[str, Any]], DescriptionContext, TableData, WorkspaceScope]:
        context, table, scope = await asyncio.to_thread(
            self.analytics.descriptive_snapshot, actor, wid, did, uid
        )
        hit = _CACHE.get(_key(context.view.sources))
        if hit:
            return hit[0], hit[1], context, table, scope
        profile = context.profile
        limitations: list[str] = []
        columns: list[dict[str, Any]] = []
        rows = str(profile["row_count"])
        cards: list[dict[str, Any]] = []
        coverage = None
        listed = [column["name"] for column in profile["columns"][briefs.COLUMN_LIMIT :]]
        if _blocked(context):
            limitations.append(
                "Confirm Data understanding for this revision before statistics are calculated."
            )
            columns = [
                briefs.column_entry(context, column, None)
                for column in profile["columns"][: briefs.COLUMN_LIMIT]
            ]
        else:
            count = await self._query(
                actor,
                did,
                context,
                scope,
                table,
                briefs.row_count_plan(scope, did),
                "rows",
                "count",
            )
            total = int(count.rows[0][0])  # type: ignore[arg-type]
            rows = str(total)
            for column in profile["columns"][: briefs.COLUMN_LIMIT]:
                stats = None
                if queryable(column["name"]) and column["type"] != "empty":
                    try:
                        stats = await self._column(actor, did, context, scope, table, column, total)
                    except _EXPECTED:
                        limitations.append(
                            f"{column['name']}: statistics were unavailable for this field."
                        )
                columns.append(briefs.column_entry(context, column, stats))
            coverage = await self._coverage(actor, did, context, scope, table, columns)
            try:
                payload = await build_insights(
                    self.analytics, actor, wid, did, uid, statistics=self.statistics, model=None
                )
                cards = list(payload["insights"])
            except _EXPECTED:
                limitations.append("The analyst team could not check this file.")
        if listed:
            limitations.append(
                f"Statistics cover the first {briefs.COLUMN_LIMIT} fields; others are listed only."
            )
        brief = briefs.assemble(
            context,
            rows,
            columns,
            listed,
            coverage,
            [card["id"] for card in cards],
            briefs.samples(context, table.headers, table.rows),
            limitations,
        )
        await asyncio.to_thread(
            self.analytics.recheck_description, actor, wid, did, uid, context.view.sources
        )
        _remember(context.view.sources, (brief, cards))
        return brief, cards, context, table, scope

    async def _coverage(
        self,
        actor: User,
        did: UUID,
        context: DescriptionContext,
        scope: WorkspaceScope,
        table: TableData,
        columns: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for entry in columns:
            if entry["type"] not in {"date", "datetime"} or not entry.get("min"):
                continue
            if entry["name"] not in context.view.dimensions:
                continue
            try:
                result, _ = await self.analytics._execute(
                    actor,
                    did,
                    context.name,
                    scope,
                    table,
                    context.view,
                    MetricRequest(
                        RECORD_COUNT, AggregationKind.COUNT, (entry["name"],), period="month"
                    ),
                    briefs.ROUTE,
                )
            except _EXPECTED:
                continue
            return briefs.date_coverage(
                entry["name"], entry["min"], entry["max"], [row[0] for row in result.rows]
            )
        return None

    async def _select(
        self, brief: dict[str, Any], candidates: list[Candidate], goal: str
    ) -> tuple[list[tuple[str, str, str]], dict[str, Any]]:
        known = {item.id: item for item in candidates}
        fallback = [
            (key, known[key].title, known[key].reason) for key in deterministic_pick(candidates)
        ]
        if self.model is None or not candidates:
            reason = "not_configured" if self.model is None else None
            return fallback, dict(route=ROUTE, fallback_reason=reason)
        request = ModelRequest(
            messages=(
                ModelMessage("system", selection_prompt()),
                ModelMessage(
                    "user",
                    selection_input(
                        briefs.model_view(brief, self.include_values), candidates, goal
                    ),
                ),
            ),
            tier=ModelTier.SMALL,
        )
        try:
            response = await asyncio.wait_for(self.model.complete(request), SELECTION_SECONDS)
            picked = parse_selection(response.content, candidates)
        except ProviderUnavailableError:
            return fallback, dict(route=ROUTE, fallback_reason="model_unavailable")
        except asyncio.TimeoutError:
            return fallback, dict(route=ROUTE, fallback_reason="timeout")
        except (ValueError, KeyError, TypeError):
            return fallback, dict(route=ROUTE, fallback_reason="invalid_response")
        except Exception:
            return fallback, dict(route=ROUTE, fallback_reason="provider_error")
        return picked, dict(route=f"{response.provider}:{response.model}", fallback_reason=None)

    async def _tiles(
        self,
        actor: User,
        did: UUID,
        context: DescriptionContext,
        scope: WorkspaceScope,
        table: TableData,
        candidates: list[Candidate],
        picked: list[tuple[str, str, str]],
        backfill: bool,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        known = {item.id: item for item in candidates}
        queue = list(picked)
        if backfill:
            queue += [
                (item.id, item.title, item.reason)
                for item in candidates
                if item.id not in {key for key, _, _ in picked}
            ]
        target = len(picked)
        tiles: list[dict[str, Any]] = []
        notes: list[str] = []
        for key, title, reason in queue:
            if len(tiles) >= min(target, MAX_TILES):
                break
            candidate = known[key]
            if candidate.card is not None:
                tiles.append(tile(candidate, title, reason, None, None))
                continue
            try:
                result, lineage = await self.analytics._execute(
                    actor,
                    did,
                    context.name,
                    scope,
                    table,
                    context.view,
                    candidate.request,  # type: ignore[arg-type]
                    ROUTE,
                )
            except _EXPECTED as error:
                notes.append(f"{candidate.title}: {error}")
                continue
            tiles.append(tile(candidate, title, reason, result, str(lineage.query_id)))
        return tiles, notes

    async def build(
        self,
        actor: User,
        wid: UUID,
        did: UUID,
        uid: UUID,
        chosen: list[str] | None = None,
    ) -> AutoDashboard:
        brief, cards, context, table, scope = await self.brief(actor, wid, did, uid)
        candidates = [] if _blocked(context) else enumerate_candidates(context, brief, cards)
        if chosen is None:
            picked, selection = await self._select(brief, candidates, context.private_goal)
        else:
            known = {item.id: item for item in candidates}
            if (
                not chosen
                or len(chosen) > MAX_TILES
                or len(set(chosen)) != len(chosen)
                or set(chosen) - set(known)
            ):
                raise IngestionError(
                    "invalid_dashboard", "Choose up to nine current candidate tiles.", 422
                )
            picked = [(key, known[key].title, known[key].reason) for key in chosen]
            selection = dict(route="user:edit", fallback_reason=None)
        tiles, notes = await self._tiles(
            actor, did, context, scope, table, candidates, picked, chosen is None
        )
        limitations = list(notes)
        if context.state != "confirmed":
            limitations.append(
                "Confirm meanings for more: totals, averages, trends and rankings of measures "
                "appear once their meaning and units are confirmed."
            )
        limitations.append(
            "Tiles describe this file; they are not causes, forecasts or errors. Every value "
            "comes from an executed query or a cross-checked analyst card."
        )
        await asyncio.to_thread(
            self.analytics.recheck_description, actor, wid, did, uid, context.view.sources
        )
        now = datetime.now(timezone.utc)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            dataset_access(repo, actor, wid, did)
            authorize_sources(repo, actor, wid, context.view.sources, did)
            mine = [
                item for item in repo.auto_dashboards(wid, did, uid) if item.owner_id == actor.id
            ]
            latest = max(mine, key=lambda item: item.number) if mine else None
            record = AutoDashboard(
                uuid4(),
                wid,
                did,
                uid,
                actor.id,
                (latest.number + 1) if latest else 1,
                latest.shared if latest else False,
                UUID(context.view.sources[0]["revision_id"]),
                dict(
                    version=VERSION,
                    dataset_name=context.name,
                    definition_state=context.state,
                    needs_confirmation=context.state != "confirmed",
                    sources=list(context.view.sources),
                    brief_version=brief["version"],
                    brief_summary=dict(
                        rows=brief["dataset"]["rows"],
                        columns=brief["dataset"]["columns"],
                        date_coverage=brief["date_coverage"],
                        analyst_findings=brief["analyst_findings"],
                    ),
                    selection=selection,
                    tiles=tiles,
                    candidates=[item.body() for item in candidates],
                    limitations=limitations,
                ),
                now,
            )
            repo.add(record)
            repo.add(
                AuditEvent(
                    uuid4(),
                    wid,
                    actor.id,
                    "auto_dashboard.created",
                    "auto_dashboard",
                    record.id,
                    now,
                )
            )
        return record

    async def current(
        self, actor: User, wid: UUID, did: UUID, uid: UUID
    ) -> tuple[AutoDashboard, list[AutoDashboard]]:
        _, _, context, _, _ = await self.brief(actor, wid, did, uid)
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            dataset_access(repo, actor, wid, did)
            items = repo.auto_dashboards(wid, did, uid)
            mine = [item for item in items if item.owner_id == actor.id]
            latest = max(mine, key=lambda item: item.number) if mine else None
            others = self._shared(repo, actor, wid, items)
        if latest is None or latest.payload["sources"] != list(context.view.sources):
            latest = await self.build(actor, wid, did, uid)
        return latest, others

    def _shared(
        self, repo: WorkspaceRepository, actor: User, wid: UUID, items: tuple[AutoDashboard, ...]
    ) -> list[AutoDashboard]:
        newest: dict[UUID, AutoDashboard] = {}
        for item in items:
            if item.owner_id != actor.id and item.number > getattr(
                newest.get(item.owner_id), "number", 0
            ):
                newest[item.owner_id] = item
        visible = []
        for item in newest.values():
            if not item.shared:
                continue
            try:
                authorize_sources(repo, actor, wid, item.payload["sources"], item.dataset_id)
            except IngestionError:
                continue
            visible.append(item)
        return visible

    def open(self, actor: User, wid: UUID, dashboard_id: UUID) -> AutoDashboard:
        with self.uow() as repo:
            repo.workspace(wid, lock=True)
            repo.membership(wid, actor.id)
            item = repo.auto_dashboard(wid, dashboard_id)
            if item.owner_id != actor.id and not item.shared:
                raise AuthorizationError("This dashboard is private")
            dataset_access(repo, actor, wid, item.dataset_id)
            authorize_sources(repo, actor, wid, item.payload["sources"], item.dataset_id)
            return item

    async def update(
        self,
        actor: User,
        wid: UUID,
        dashboard_id: UUID,
        expected_number: int,
        shared: bool | None,
        tiles: list[str] | None,
    ) -> AutoDashboard:
        item = self.open(actor, wid, dashboard_id)
        if item.owner_id != actor.id:
            raise IngestionError("forbidden", "Only its owner can change this dashboard.", 403)
        with self.uow() as repo:
            mine = [
                entry
                for entry in repo.auto_dashboards(wid, item.dataset_id, item.upload_id)
                if entry.owner_id == actor.id
            ]
        if item.number != expected_number or max(entry.number for entry in mine) != item.number:
            raise IngestionError("dashboard_conflict", "Reload the latest dashboard first.", 409)
        if tiles is not None:
            item = await self.build(actor, wid, item.dataset_id, item.upload_id, tiles)
        if shared is not None and shared != item.shared:
            with self.uow() as repo:
                repo.workspace(wid, lock=True)
                repo.set_auto_dashboard_shared(wid, item.id, shared)
                repo.add(
                    AuditEvent(
                        uuid4(),
                        wid,
                        actor.id,
                        "auto_dashboard.shared" if shared else "auto_dashboard.unshared",
                        "auto_dashboard",
                        item.id,
                        datetime.now(timezone.utc),
                    )
                )
                item = repo.auto_dashboard(wid, item.id)
        return item
