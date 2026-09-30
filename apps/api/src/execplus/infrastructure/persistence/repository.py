"""Use case: Persists workspace operations atomically.

What it does: Implements scoped lookups and transaction-scoped PostgreSQL row locks.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID

from sqlalchemy import Connection, Engine, Table, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from execplus.application.ports import WorkspaceRepository
from execplus.domain.activation import Feedback, ReportDelivery, ReportSchedule
from execplus.domain.ingestion import (
    AuditEvent,
    Dataset,
    IngestionError,
    Invitation,
    Membership,
    Upload,
    User,
    Workspace,
)
from execplus.domain.join_paths import JoinPath
from execplus.domain.knowledge import Document, DocumentChunk
from execplus.domain.models import QueryExecution
from execplus.domain.profiling import Revision, UsageEvent
from execplus.domain.refresh import (
    AlertEvent,
    AlertRule,
    Monitor,
    Observation,
    RefreshCandidate,
    RefreshFeed,
)
from execplus.domain.saved_items import SavedItem
from execplus.domain.studies import (
    Department,
    Organization,
    Study,
    StudyBoard,
    StudyVersion,
    ViewDismissals,
)
from execplus.domain.threads import Thread, ThreadTurn
from execplus.domain.understanding import DataPreference, Understanding
from execplus.infrastructure.persistence import schema as s

Record = TypeVar(
    "Record",
    User,
    Workspace,
    Membership,
    Invitation,
    Dataset,
    Upload,
    AuditEvent,
    Revision,
    UsageEvent,
    QueryExecution,
    SavedItem,
    Thread,
    ThreadTurn,
    JoinPath,
    Feedback,
    ReportSchedule,
    ReportDelivery,
    Document,
    DocumentChunk,
    Understanding,
    Organization,
    Department,
    Study,
    StudyVersion,
    StudyBoard,
    RefreshFeed,
    RefreshCandidate,
    Monitor,
    Observation,
    AlertRule,
    AlertEvent,
)


class SQLWorkspaceRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def refresh_feed(self, workspace_id: UUID, record_id: UUID) -> RefreshFeed:
        return self._one(RefreshFeed, s.refresh_feeds, workspace_id=workspace_id, id=record_id)

    def refresh_feeds(self, workspace_id: UUID, dataset_id: UUID) -> tuple[RefreshFeed, ...]:
        return self._many(
            RefreshFeed, s.refresh_feeds, workspace_id=workspace_id, dataset_id=dataset_id
        )

    def set_refresh_feed(self, record: RefreshFeed) -> None:
        self.connection.execute(
            update(s.refresh_feeds)
            .where(
                s.refresh_feeds.c.workspace_id == record.workspace_id,
                s.refresh_feeds.c.id == record.id,
            )
            .values(**asdict(record))
        )

    def refresh_candidate(self, workspace_id: UUID, record_id: UUID) -> RefreshCandidate:
        return self._one(
            RefreshCandidate, s.refresh_candidates, workspace_id=workspace_id, id=record_id
        )

    def refresh_candidates(self, workspace_id: UUID, feed_id: UUID) -> tuple[RefreshCandidate, ...]:
        return self._many(
            RefreshCandidate, s.refresh_candidates, workspace_id=workspace_id, feed_id=feed_id
        )

    def set_refresh_candidate(self, record: RefreshCandidate) -> None:
        self.connection.execute(
            update(s.refresh_candidates)
            .where(
                s.refresh_candidates.c.workspace_id == record.workspace_id,
                s.refresh_candidates.c.id == record.id,
            )
            .values(**asdict(record))
        )

    def monitor(self, workspace_id: UUID, record_id: UUID) -> Monitor:
        return self._one(Monitor, s.monitors, workspace_id=workspace_id, id=record_id)

    def monitors(self, workspace_id: UUID, feed_id: UUID) -> tuple[Monitor, ...]:
        return self._many(Monitor, s.monitors, workspace_id=workspace_id, feed_id=feed_id)

    def set_monitor(self, record: Monitor) -> None:
        self.connection.execute(
            update(s.monitors)
            .where(s.monitors.c.workspace_id == record.workspace_id, s.monitors.c.id == record.id)
            .values(**asdict(record))
        )

    def observation(self, workspace_id: UUID, record_id: UUID) -> Observation:
        return self._one(Observation, s.observations, workspace_id=workspace_id, id=record_id)

    def observations(self, workspace_id: UUID, monitor_id: UUID) -> tuple[Observation, ...]:
        return self._many(
            Observation, s.observations, workspace_id=workspace_id, monitor_id=monitor_id
        )

    def set_observation(self, record: Observation) -> None:
        self.connection.execute(
            update(s.observations)
            .where(
                s.observations.c.workspace_id == record.workspace_id,
                s.observations.c.id == record.id,
            )
            .values(**asdict(record))
        )

    def alert_rule(self, workspace_id: UUID, record_id: UUID) -> AlertRule:
        return self._one(AlertRule, s.alert_rules, workspace_id=workspace_id, id=record_id)

    def alert_rules(self, workspace_id: UUID, monitor_id: UUID) -> tuple[AlertRule, ...]:
        return self._many(
            AlertRule, s.alert_rules, workspace_id=workspace_id, monitor_id=monitor_id
        )

    def set_alert_rule(self, record: AlertRule) -> None:
        self.connection.execute(
            update(s.alert_rules)
            .where(
                s.alert_rules.c.workspace_id == record.workspace_id, s.alert_rules.c.id == record.id
            )
            .values(**asdict(record))
        )

    def alert_event(self, workspace_id: UUID, record_id: UUID) -> AlertEvent:
        return self._one(AlertEvent, s.alert_events, workspace_id=workspace_id, id=record_id)

    def alert_events(self, workspace_id: UUID, rule_id: UUID) -> tuple[AlertEvent, ...]:
        return self._many(AlertEvent, s.alert_events, workspace_id=workspace_id, rule_id=rule_id)

    def set_alert_event(self, record: AlertEvent) -> None:
        self.connection.execute(
            update(s.alert_events)
            .where(
                s.alert_events.c.workspace_id == record.workspace_id,
                s.alert_events.c.id == record.id,
            )
            .values(**asdict(record))
        )

    def due_refreshes(self, now: datetime) -> tuple[tuple[UUID, UUID], ...]:
        rows = self.connection.execute(
            select(s.refresh_feeds.c.workspace_id, s.refresh_feeds.c.id)
            .where(s.refresh_feeds.c.enabled, s.refresh_feeds.c.next_due <= now)
            .order_by(s.refresh_feeds.c.next_due)
            .limit(100)
        )
        return tuple((row.workspace_id, row.id) for row in rows)

    def pending_observations(
        self, now: datetime, workspace_id: UUID | None = None, dataset_id: UUID | None = None
    ) -> tuple[tuple[UUID, UUID], ...]:
        from datetime import timedelta

        statement = (
            select(s.observations.c.workspace_id, s.observations.c.id)
            .join(
                s.monitors,
                (s.monitors.c.workspace_id == s.observations.c.workspace_id)
                & (s.monitors.c.id == s.observations.c.monitor_id),
            )
            .join(
                s.refresh_feeds,
                (s.refresh_feeds.c.workspace_id == s.monitors.c.workspace_id)
                & (s.refresh_feeds.c.id == s.monitors.c.feed_id),
            )
            .where(
                (s.observations.c.status == "pending")
                | (
                    (s.observations.c.status == "running")
                    & (s.observations.c.claimed_at < now - timedelta(minutes=10))
                )
            )
        )
        if workspace_id is not None:
            statement = statement.where(s.observations.c.workspace_id == workspace_id)
        if dataset_id is not None:
            statement = statement.where(s.refresh_feeds.c.dataset_id == dataset_id)
        rows = self.connection.execute(
            statement.order_by(s.observations.c.created_at, s.observations.c.source_version).limit(
                100
            )
        )
        return tuple((row.workspace_id, row.id) for row in rows)

    def organizations(self, actor_id: UUID) -> tuple[Organization, ...]:
        accessible = (
            select(s.departments.c.organization_id)
            .join(s.memberships, s.departments.c.workspace_id == s.memberships.c.workspace_id)
            .where(s.memberships.c.user_id == actor_id)
        )
        rows = self.connection.execute(
            select(s.organizations)
            .where((s.organizations.c.owner_id == actor_id) | s.organizations.c.id.in_(accessible))
            .order_by(s.organizations.c.created_at)
        ).mappings()
        return tuple(Organization(**row) for row in rows)

    def organization(self, organization_id: UUID) -> Organization:
        return self._one(Organization, s.organizations, id=organization_id)

    def departments(self, organization_id: UUID, actor_id: UUID) -> tuple[Department, ...]:
        rows = self.connection.execute(
            select(s.departments)
            .join(s.memberships, s.departments.c.workspace_id == s.memberships.c.workspace_id)
            .where(
                s.departments.c.organization_id == organization_id,
                s.memberships.c.user_id == actor_id,
            )
        ).mappings()
        return tuple(Department(**row) for row in rows)

    def department(self, workspace_id: UUID) -> Department | None:
        row = (
            self.connection.execute(
                select(s.departments).where(s.departments.c.workspace_id == workspace_id)
            )
            .mappings()
            .first()
        )
        return Department(**row) if row else None

    def set_department(self, department: Department) -> None:
        self.connection.execute(
            insert(s.departments)
            .values(**asdict(department))
            .on_conflict_do_update(index_elements=["workspace_id"], set_=dict(name=department.name))
        )

    def studies(self, workspace_id: UUID, dataset_id: UUID) -> tuple[Study, ...]:
        return self._many(Study, s.studies, workspace_id=workspace_id, dataset_id=dataset_id)

    def study(self, workspace_id: UUID, study_id: UUID) -> Study:
        return self._one(Study, s.studies, workspace_id=workspace_id, id=study_id)

    def study_versions(self, workspace_id: UUID, study_id: UUID) -> tuple[StudyVersion, ...]:
        records = self._many(
            StudyVersion, s.study_versions, workspace_id=workspace_id, study_id=study_id
        )
        return tuple(sorted(records, key=lambda item: item.number))

    def study_version(self, workspace_id: UUID, version_id: UUID) -> StudyVersion:
        return self._one(StudyVersion, s.study_versions, workspace_id=workspace_id, id=version_id)

    def set_study_shared(self, workspace_id: UUID, study_id: UUID, shared: bool) -> None:
        self.study(workspace_id, study_id)
        self.connection.execute(
            update(s.studies)
            .where(s.studies.c.workspace_id == workspace_id, s.studies.c.id == study_id)
            .values(shared=shared)
        )

    def study_boards(self, workspace_id: UUID) -> tuple[StudyBoard, ...]:
        return self._many(StudyBoard, s.study_boards, workspace_id=workspace_id)

    def study_board(self, workspace_id: UUID, board_id: UUID) -> StudyBoard:
        return self._one(StudyBoard, s.study_boards, workspace_id=workspace_id, id=board_id)

    def set_study_board(self, board: StudyBoard) -> None:
        self.study_board(board.workspace_id, board.id)
        self.connection.execute(
            update(s.study_boards)
            .where(
                s.study_boards.c.workspace_id == board.workspace_id, s.study_boards.c.id == board.id
            )
            .values(**asdict(board))
        )

    def view_dismissals(
        self, workspace_id: UUID, dataset_id: UUID, user_id: UUID, understanding_id: UUID
    ) -> list[str]:
        row = self.connection.execute(
            select(s.view_dismissals.c.dismissed).where(
                s.view_dismissals.c.workspace_id == workspace_id,
                s.view_dismissals.c.dataset_id == dataset_id,
                s.view_dismissals.c.user_id == user_id,
                s.view_dismissals.c.understanding_id == understanding_id,
            )
        ).scalar_one_or_none()
        return list(row or [])

    def set_view_dismissals(self, dismissals: ViewDismissals) -> None:
        self.connection.execute(
            insert(s.view_dismissals)
            .values(**asdict(dismissals))
            .on_conflict_do_update(
                index_elements=["workspace_id", "dataset_id", "user_id", "understanding_id"],
                set_=dict(dismissed=dismissals.dismissed),
            )
        )

    def latest_understanding(self, workspace_id: UUID, dataset_id: UUID) -> Understanding | None:
        row = (
            self.connection.execute(
                select(s.understandings)
                .filter_by(workspace_id=workspace_id, dataset_id=dataset_id)
                .order_by(s.understandings.c.version.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return Understanding(**row) if row else None

    def understanding(self, workspace_id: UUID, dataset_id: UUID, record_id: UUID) -> Understanding:
        return self._one(
            Understanding,
            s.understandings,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            id=record_id,
        )

    def understanding_history(
        self, workspace_id: UUID, dataset_id: UUID
    ) -> tuple[Understanding, ...]:
        return self._many(
            Understanding, s.understandings, workspace_id=workspace_id, dataset_id=dataset_id
        )

    def data_preference(
        self, workspace_id: UUID, dataset_id: UUID, user_id: UUID
    ) -> DataPreference | None:
        row = (
            self.connection.execute(
                select(s.data_preferences).filter_by(
                    workspace_id=workspace_id, dataset_id=dataset_id, user_id=user_id
                )
            )
            .mappings()
            .first()
        )
        return DataPreference(**row) if row else None

    def save_data_preference(self, preference: DataPreference) -> None:
        self.connection.execute(
            insert(s.data_preferences)
            .values(**asdict(preference))
            .on_conflict_do_update(
                index_elements=["workspace_id", "dataset_id", "user_id"],
                set_={"domain_hint": preference.domain_hint, "goal": preference.goal},
            )
        )

    def _one(self, record: type[Record], table: Table, **keys: UUID) -> Record:
        row = self.connection.execute(select(table).filter_by(**keys)).mappings().first()
        if row is None:
            raise IngestionError("not_found", "The requested resource is unavailable.", 404)
        return record(**row)

    def _many(self, record: type[Record], table: Table, **keys: UUID) -> tuple[Record, ...]:
        rows = self.connection.execute(select(table).filter_by(**keys).order_by(table.c.created_at))
        return tuple(record(**row) for row in rows.mappings())

    def user(self, user_id: UUID) -> User:
        return self._one(User, s.users, id=user_id)

    def workspaces(self, user_id: UUID) -> tuple[Workspace, ...]:
        statement = (
            select(s.workspaces).join(s.memberships).where(s.memberships.c.user_id == user_id)
        )
        return tuple(Workspace(**row) for row in self.connection.execute(statement).mappings())

    def workspace(self, workspace_id: UUID, *, lock: bool = False) -> Workspace:
        statement = select(s.workspaces).where(s.workspaces.c.id == workspace_id)
        if lock:
            statement = statement.with_for_update()
        row = self.connection.execute(statement).mappings().first()
        if row is None:
            raise IngestionError("not_found", "The requested workspace is unavailable.", 404)
        return Workspace(**row)

    def membership(self, workspace_id: UUID, user_id: UUID) -> Membership:
        return self._one(Membership, s.memberships, workspace_id=workspace_id, user_id=user_id)

    def members(self, workspace_id: UUID) -> tuple[Membership, ...]:
        return self._many(Membership, s.memberships, workspace_id=workspace_id)

    def invitations(self, workspace_id: UUID) -> tuple[Invitation, ...]:
        return self._many(Invitation, s.invitations, workspace_id=workspace_id)

    def invitation(self, workspace_id: UUID, invitation_id: UUID) -> Invitation:
        return self._one(Invitation, s.invitations, workspace_id=workspace_id, id=invitation_id)

    def set_invitation_status(self, workspace_id: UUID, invitation_id: UUID, status: str) -> None:
        self.connection.execute(
            update(s.invitations)
            .where(
                s.invitations.c.workspace_id == workspace_id,
                s.invitations.c.id == invitation_id,
            )
            .values(status=status)
        )

    def remove_member(self, workspace_id: UUID, user_id: UUID) -> None:
        self.connection.execute(
            delete(s.memberships).where(
                s.memberships.c.workspace_id == workspace_id,
                s.memberships.c.user_id == user_id,
            )
        )

    def set_seat_limit(self, workspace_id: UUID, limit: int) -> None:
        self.connection.execute(
            update(s.workspaces)
            .where(s.workspaces.c.id == workspace_id)
            .values(
                seat_limit=limit,
                updated_at=datetime.now(timezone.utc),
            )
        )

    def datasets(self, workspace_id: UUID) -> tuple[Dataset, ...]:
        return self._many(Dataset, s.datasets, workspace_id=workspace_id)

    def dataset(self, workspace_id: UUID, dataset_id: UUID) -> Dataset:
        return self._one(Dataset, s.datasets, workspace_id=workspace_id, id=dataset_id)

    def rename_dataset(self, workspace_id: UUID, dataset_id: UUID, name: str) -> Dataset:
        self.dataset(workspace_id, dataset_id)
        self.connection.execute(
            update(s.datasets)
            .where(
                s.datasets.c.workspace_id == workspace_id,
                s.datasets.c.id == dataset_id,
            )
            .values(name=name, updated_at=datetime.now(timezone.utc))
        )
        return self.dataset(workspace_id, dataset_id)

    def uploads(self, workspace_id: UUID, dataset_id: UUID) -> tuple[Upload, ...]:
        return self._many(Upload, s.uploads, workspace_id=workspace_id, dataset_id=dataset_id)

    def upload(self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID) -> Upload:
        return self._one(
            Upload, s.uploads, workspace_id=workspace_id, dataset_id=dataset_id, id=upload_id
        )

    def audit_events(self, workspace_id: UUID) -> tuple[AuditEvent, ...]:
        return self._many(AuditEvent, s.audit_events, workspace_id=workspace_id)

    def revisions(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[Revision, ...]:
        return self._many(
            Revision,
            s.revisions,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=upload_id,
        )

    def revision(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID, revision_id: UUID
    ) -> Revision:
        return self._one(
            Revision,
            s.revisions,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=upload_id,
            id=revision_id,
        )

    def active_revision(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> Revision | None:
        row = (
            self.connection.execute(
                select(s.revision_heads).filter_by(
                    workspace_id=workspace_id, dataset_id=dataset_id, upload_id=upload_id
                )
            )
            .mappings()
            .first()
        )
        return (
            self.revision(workspace_id, dataset_id, upload_id, row["revision_id"]) if row else None
        )

    def set_active_revision(self, revision: Revision) -> None:
        statement = insert(s.revision_heads).values(
            workspace_id=revision.workspace_id,
            dataset_id=revision.dataset_id,
            upload_id=revision.upload_id,
            revision_id=revision.id,
        )
        self.connection.execute(
            statement.on_conflict_do_update(
                index_elements=["workspace_id", "dataset_id", "upload_id"],
                set_={"revision_id": revision.id},
            )
        )

    def usage_events(self, workspace_id: UUID) -> tuple[UsageEvent, ...]:
        return self._many(UsageEvent, s.usage_events, workspace_id=workspace_id)

    def query_execution(self, workspace_id: UUID, query_id: UUID) -> QueryExecution:
        return self._one(QueryExecution, s.query_executions, workspace_id=workspace_id, id=query_id)

    def set_query_receipt(
        self, workspace_id: UUID, query_id: UUID, receipt: dict[str, object]
    ) -> None:
        self.query_execution(workspace_id, query_id)
        self.connection.execute(
            update(s.query_executions)
            .where(
                s.query_executions.c.workspace_id == workspace_id,
                s.query_executions.c.id == query_id,
            )
            .values(receipt=receipt)
        )

    def saved_items(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> tuple[SavedItem, ...]:
        return self._many(
            SavedItem,
            s.saved_items,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            upload_id=upload_id,
        )

    def saved_item(self, workspace_id: UUID, item_id: UUID) -> SavedItem:
        return self._one(SavedItem, s.saved_items, workspace_id=workspace_id, id=item_id)

    def delete_saved_item(self, workspace_id: UUID, item_id: UUID) -> None:
        self.connection.execute(
            delete(s.saved_items).where(
                s.saved_items.c.workspace_id == workspace_id, s.saved_items.c.id == item_id
            )
        )

    def thread(self, workspace_id: UUID, thread_id: UUID) -> Thread:
        return self._one(Thread, s.threads, workspace_id=workspace_id, id=thread_id)

    def threads(
        self, workspace_id: UUID, dataset_id: UUID, upload_id: UUID, owner_id: UUID
    ) -> tuple[Thread, ...]:
        rows = self.connection.execute(
            select(s.threads)
            .filter_by(
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                upload_id=upload_id,
                owner_id=owner_id,
            )
            .order_by(s.threads.c.created_at.desc(), s.threads.c.id)
            .limit(50)
        ).mappings()
        return tuple(Thread(**row) for row in rows)

    def thread_turns(self, workspace_id: UUID, thread_id: UUID) -> tuple[ThreadTurn, ...]:
        self.thread(workspace_id, thread_id)
        statement = (
            select(s.thread_turns)
            .join(s.threads)
            .where(
                s.threads.c.workspace_id == workspace_id, s.thread_turns.c.thread_id == thread_id
            )
            .order_by(s.thread_turns.c.created_at, s.thread_turns.c.id)
        )
        return tuple(ThreadTurn(**row) for row in self.connection.execute(statement).mappings())

    def add_thread_turn(self, workspace_id: UUID, turn: ThreadTurn) -> None:
        self.thread(workspace_id, turn.thread_id)
        self.add(turn)

    def update_thread_turn(self, workspace_id: UUID, turn: ThreadTurn) -> None:
        self.thread(workspace_id, turn.thread_id)
        self.connection.execute(
            update(s.thread_turns)
            .where(s.thread_turns.c.thread_id == turn.thread_id, s.thread_turns.c.id == turn.id)
            .values(**asdict(turn))
        )

    def join_paths(self, workspace_id: UUID) -> tuple[JoinPath, ...]:
        return self._many(JoinPath, s.join_paths, workspace_id=workspace_id)

    def join_path(self, workspace_id: UUID, join_path_id: UUID) -> JoinPath:
        return self._one(JoinPath, s.join_paths, workspace_id=workspace_id, id=join_path_id)

    def feedback(self, workspace_id: UUID) -> tuple[Feedback, ...]:
        return self._many(Feedback, s.feedback, workspace_id=workspace_id)

    def documents(
        self, workspace_id: UUID, dataset_id: UUID, actor_id: UUID
    ) -> tuple[Document, ...]:
        statement = (
            select(s.documents)
            .where(
                s.documents.c.workspace_id == workspace_id,
                s.documents.c.dataset_id == dataset_id,
                (s.documents.c.owner_id == actor_id) | s.documents.c.shared,
            )
            .order_by(s.documents.c.created_at, s.documents.c.id)
        )
        return tuple(Document(**row) for row in self.connection.execute(statement).mappings())

    def document(self, workspace_id: UUID, document_id: UUID) -> Document:
        return self._one(Document, s.documents, workspace_id=workspace_id, id=document_id)

    def document_chunks(self, workspace_id: UUID, document_id: UUID) -> tuple[DocumentChunk, ...]:
        statement = (
            select(s.document_chunks)
            .filter_by(workspace_id=workspace_id, document_id=document_id)
            .order_by(s.document_chunks.c.ordinal)
        )
        return tuple(DocumentChunk(**row) for row in self.connection.execute(statement).mappings())

    def delete_document(self, workspace_id: UUID, document_id: UUID) -> None:
        self.connection.execute(
            delete(s.documents).filter_by(workspace_id=workspace_id, id=document_id)
        )

    def report_schedules(self, workspace_id: UUID, owner_id: UUID) -> tuple[ReportSchedule, ...]:
        return self._many(
            ReportSchedule, s.report_schedules, workspace_id=workspace_id, owner_id=owner_id
        )

    def report_schedule(self, workspace_id: UUID, schedule_id: UUID) -> ReportSchedule:
        return self._one(
            ReportSchedule, s.report_schedules, workspace_id=workspace_id, id=schedule_id
        )

    def due_schedules(self, now: datetime) -> tuple[tuple[UUID, UUID], ...]:
        rows = self.connection.execute(
            select(s.report_schedules.c.workspace_id, s.report_schedules.c.id)
            .where(
                s.report_schedules.c.enabled,
                s.report_schedules.c.next_due <= now,
            )
            .order_by(s.report_schedules.c.next_due)
            .limit(100)
        )
        return tuple((row.workspace_id, row.id) for row in rows)

    def set_report_schedule(self, schedule: ReportSchedule) -> None:
        self.connection.execute(
            update(s.report_schedules)
            .where(
                s.report_schedules.c.workspace_id == schedule.workspace_id,
                s.report_schedules.c.id == schedule.id,
            )
            .values(**asdict(schedule))
        )

    def set_report_delivery(self, delivery: ReportDelivery) -> None:
        self.connection.execute(
            update(s.report_deliveries)
            .where(
                s.report_deliveries.c.workspace_id == delivery.workspace_id,
                s.report_deliveries.c.id == delivery.id,
            )
            .values(status=delivery.status)
        )

    def report_delivery(
        self, workspace_id: UUID, schedule_id: UUID, due_at: datetime
    ) -> ReportDelivery | None:
        row = (
            self.connection.execute(
                select(s.report_deliveries).filter_by(
                    workspace_id=workspace_id,
                    schedule_id=schedule_id,
                    due_at=due_at,
                )
            )
            .mappings()
            .first()
        )
        return ReportDelivery(**row) if row else None

    def add(
        self,
        record: Workspace
        | Membership
        | Invitation
        | Dataset
        | Upload
        | AuditEvent
        | Revision
        | UsageEvent
        | QueryExecution
        | SavedItem
        | Thread
        | ThreadTurn
        | JoinPath
        | Feedback
        | ReportSchedule
        | ReportDelivery
        | Document
        | DocumentChunk
        | Understanding
        | Organization
        | Department
        | Study
        | StudyVersion
        | StudyBoard
        | RefreshFeed
        | RefreshCandidate
        | Monitor
        | Observation
        | AlertRule
        | AlertEvent,
    ) -> None:
        tables = {
            Workspace: s.workspaces,
            Membership: s.memberships,
            Invitation: s.invitations,
            Dataset: s.datasets,
            Upload: s.uploads,
            AuditEvent: s.audit_events,
            Revision: s.revisions,
            UsageEvent: s.usage_events,
            QueryExecution: s.query_executions,
            SavedItem: s.saved_items,
            Thread: s.threads,
            ThreadTurn: s.thread_turns,
            JoinPath: s.join_paths,
            Feedback: s.feedback,
            ReportSchedule: s.report_schedules,
            ReportDelivery: s.report_deliveries,
            Document: s.documents,
            DocumentChunk: s.document_chunks,
            Understanding: s.understandings,
            Organization: s.organizations,
            Department: s.departments,
            Study: s.studies,
            StudyVersion: s.study_versions,
            StudyBoard: s.study_boards,
            RefreshFeed: s.refresh_feeds,
            RefreshCandidate: s.refresh_candidates,
            Monitor: s.monitors,
            Observation: s.observations,
            AlertRule: s.alert_rules,
            AlertEvent: s.alert_events,
        }
        self.connection.execute(tables[type(record)].insert().values(**asdict(record)))


class SQLUnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def __call__(self) -> Iterator[WorkspaceRepository]:
        with self.engine.begin() as connection:
            yield SQLWorkspaceRepository(connection)
