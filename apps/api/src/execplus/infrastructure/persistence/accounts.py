"""Use case: Persists native account security and actor-private setup progress.

What it does: Serializes credential changes, applies atomic throttles
and preserves existing workspace records.
"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from execplus.application.account_ports import AccountRepository
from execplus.domain.accounts import GuideProgress, LocalAccount
from execplus.domain.ingestion import User
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.repository import SQLWorkspaceRepository


class SQLAccountRepository(SQLWorkspaceRepository):
    def new_user(self, user: User) -> bool:
        return (
            self.connection.execute(
                insert(s.users)
                .values(**asdict(user))
                .on_conflict_do_nothing(index_elements=["email"])
                .returning(s.users.c.id)
            ).scalar_one_or_none()
            is not None
        )

    def add_local_account(self, account: LocalAccount) -> None:
        self.connection.execute(
            insert(s.local_accounts).values(
                user_id=account.user.id,
                password_hash=account.password_hash,
                password_changed_at=account.password_changed_at,
                disabled_at=account.disabled_at,
            )
        )

    def account_by_email(self, email: str) -> LocalAccount | None:
        user_id = self.connection.execute(
            select(s.users.c.id).where(s.users.c.email == email)
        ).scalar_one_or_none()
        return self.local_account(user_id) if user_id is not None else None

    def local_account(self, user_id: UUID, *, lock: bool = False) -> LocalAccount | None:
        statement = select(s.local_accounts).where(s.local_accounts.c.user_id == user_id)
        if lock:
            statement = statement.with_for_update()
        row = self.connection.execute(statement).mappings().one_or_none()
        if row is None:
            return None
        return LocalAccount(
            self.user(user_id), row["password_hash"], row["password_changed_at"], row["disabled_at"]
        )

    def lock_account_workspaces(self, user_id: UUID) -> None:
        identifiers = self.connection.execute(
            select(s.memberships.c.workspace_id)
            .where(s.memberships.c.user_id == user_id)
            .order_by(s.memberships.c.workspace_id)
        ).scalars()
        for wid in identifiers:
            self.workspace(wid, lock=True)

    def update_local_account(self, account: LocalAccount) -> None:
        self.connection.execute(
            update(s.local_accounts)
            .where(s.local_accounts.c.user_id == account.user.id)
            .values(
                password_hash=account.password_hash,
                password_changed_at=account.password_changed_at,
                disabled_at=account.disabled_at,
            )
        )

    def add_account_session(self, user_id: UUID, digest: str, expires_at: datetime) -> None:
        self.connection.execute(
            delete(s.sessions).where(
                s.sessions.c.user_id == user_id,
                s.sessions.c.expires_at <= expires_at - timedelta(hours=8),
            )
        )
        surplus = (
            self.connection.execute(
                select(s.sessions.c.token_hash)
                .where(s.sessions.c.user_id == user_id)
                .order_by(s.sessions.c.expires_at.desc(), s.sessions.c.token_hash.desc())
                .offset(7)
            )
            .scalars()
            .all()
        )
        if surplus:
            self.connection.execute(
                delete(s.sessions).where(
                    s.sessions.c.user_id == user_id, s.sessions.c.token_hash.in_(surplus)
                )
            )
        self.connection.execute(
            insert(s.sessions).values(token_hash=digest, user_id=user_id, expires_at=expires_at)
        )

    def revoke_account_credentials(self, user_id: UUID, now: datetime) -> None:
        self.connection.execute(delete(s.sessions).where(s.sessions.c.user_id == user_id))
        for table in (s.integration_keys, s.embed_grants):
            self.connection.execute(
                update(table)
                .where(table.c.user_id == user_id, table.c.revoked_at.is_(None))
                .values(revoked_at=now)
            )

    def account_event(
        self, user_id: UUID | None, action: str, now: datetime, reason: str = ""
    ) -> None:
        self.connection.execute(
            insert(s.account_events).values(
                id=uuid4(), user_id=user_id, action=action, reason=reason, created_at=now
            )
        )

    def account_events(self, user_id: UUID) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            select(
                s.account_events.c.id,
                s.account_events.c.action,
                s.account_events.c.reason,
                s.account_events.c.created_at,
            )
            .where(s.account_events.c.user_id == user_id)
            .order_by(s.account_events.c.created_at.desc(), s.account_events.c.id.desc())
            .limit(50)
        ).mappings()
        return tuple(dict(row) for row in rows)

    def approve_invitation_identity(
        self, invitation_id: UUID, user_id: UUID, actor_id: UUID, now: datetime
    ) -> None:
        self.connection.execute(
            insert(s.invitation_identity_approvals)
            .values(
                invitation_id=invitation_id,
                user_id=user_id,
                approved_by=actor_id,
                approved_at=now,
            )
            .on_conflict_do_update(
                index_elements=["invitation_id"],
                set_={"user_id": user_id, "approved_by": actor_id, "approved_at": now},
            )
        )

    def onboarding_progress(self, wid: UUID, actor_id: UUID) -> GuideProgress | None:
        row = (
            self.connection.execute(
                select(s.onboarding_progress).where(
                    s.onboarding_progress.c.workspace_id == wid,
                    s.onboarding_progress.c.user_id == actor_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return GuideProgress(**dict(row, skipped_steps=tuple(row["skipped_steps"])))

    def save_onboarding_progress(self, progress: GuideProgress) -> None:
        value = asdict(progress)
        value["skipped_steps"] = list(progress.skipped_steps)
        self.connection.execute(
            insert(s.onboarding_progress)
            .values(**value)
            .on_conflict_do_update(
                index_elements=["workspace_id", "user_id"],
                set_={
                    key: item
                    for key, item in value.items()
                    if key not in {"workspace_id", "user_id"}
                },
            )
        )

    def onboarding_actions(self, wid: UUID, actor_id: UUID) -> set[str]:
        return set(
            self.connection.execute(
                select(s.audit_events.c.action)
                .where(s.audit_events.c.workspace_id == wid, s.audit_events.c.actor_id == actor_id)
                .distinct()
            ).scalars()
        )


class SQLAccountStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def transaction(self) -> Iterator[AccountRepository]:
        with self.engine.begin() as connection:
            yield SQLAccountRepository(connection)

    def consume_auth_attempt(
        self, operation: str, identifier: str, peer: str, now: datetime
    ) -> bool:
        duration = 3600 if operation == "register" else 900
        epoch = int(now.timestamp())
        window = datetime.fromtimestamp(epoch - epoch % duration, timezone.utc)
        account_limit = 10 if operation == "login" else 5
        peer_limit = 20 if operation == "register" else 60
        limits = [
            (
                hashlib.sha256(f"{operation}:account:{identifier}".encode()).hexdigest(),
                account_limit,
            ),
            (hashlib.sha256(f"{operation}:peer:{peer[:200]}".encode()).hexdigest(), peer_limit),
        ]
        allowed = True
        with self.engine.begin() as connection:
            connection.execute(
                delete(s.account_rate_windows).where(
                    s.account_rate_windows.c.window_start < now - timedelta(days=1)
                )
            )
            for key, limit in sorted(limits):
                used = connection.execute(
                    insert(s.account_rate_windows)
                    .values(key_hash=key, window_start=window, used=1)
                    .on_conflict_do_update(
                        index_elements=["key_hash", "window_start"],
                        set_={"used": s.account_rate_windows.c.used + 1},
                        where=s.account_rate_windows.c.used < limit,
                    )
                    .returning(s.account_rate_windows.c.used)
                ).scalar_one_or_none()
                allowed = allowed and used is not None
        return allowed
