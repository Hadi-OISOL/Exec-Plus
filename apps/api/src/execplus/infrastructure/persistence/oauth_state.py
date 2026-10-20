"""Use case: Serializes browser-bound provider consent and one-use session exchange.

What it does: Stores only token hashes, rechecks revocation after network I/O and prevents
email-based association of external identities with existing native/operator accounts.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from execplus.application.connector_ports import ConnectorConnection
from execplus.application.google_ports import GoogleConnection
from execplus.application.oauth_ports import OAuthAttempt
from execplus.application.services.workspaces import normalized_email
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from execplus.infrastructure.persistence.accounts import SQLAccountRepository, SQLAccountStore


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def invalid() -> IngestionError:
    return IngestionError(
        "oauth_state_invalid", "This sign-in expired or was already used. Try again.", 400
    )


def active_user(connection: Connection, user_id: UUID) -> None:
    # Match account-change lock order before locking sessions or connection state.
    for table in (s.local_accounts, s.external_identities):
        row = (
            connection.execute(select(table).where(table.c.user_id == user_id).with_for_update())
            .mappings()
            .first()
        )
        if row and row["disabled_at"] is not None:
            raise IngestionError("unauthenticated", "The session is invalid or expired.", 401)
    if (
        connection.execute(
            select(s.users.c.id).where(s.users.c.id == user_id).with_for_update()
        ).first()
        is None
    ):
        raise IngestionError("unauthenticated", "The session is invalid or expired.", 401)


def active_session(connection: Connection, user_id: UUID, session_hash: str, now: datetime) -> None:
    active_user(connection, user_id)
    if (
        connection.execute(
            select(s.sessions.c.token_hash)
            .where(
                s.sessions.c.user_id == user_id,
                s.sessions.c.token_hash == session_hash,
                s.sessions.c.expires_at > now,
            )
            .with_for_update()
        ).first()
        is None
    ):
        raise IngestionError("unauthenticated", "The session is invalid or expired.", 401)


def connection_table(provider: str) -> Any:
    return s.google_connections if provider == "google" else s.connector_connections


def connection_match(table: Any, user_id: UUID, provider: str) -> Any:
    match = table.c.user_id == user_id
    return match if provider == "google" else match & (table.c.provider == provider)


def current_version(connection: Connection, user_id: UUID, provider: str) -> UUID | None:
    table = connection_table(provider)
    return connection.execute(
        select(table.c.version).where(connection_match(table, user_id, provider))
    ).scalar_one_or_none()


def record_values(record: GoogleConnection | ConnectorConnection) -> dict[str, Any]:
    if isinstance(record, GoogleConnection):
        return dict(
            google_email=record.google_email,
            scope=record.scope,
            refresh_token_encrypted=record.refresh_token_sealed,
            version=record.version,
        )
    return dict(
        display_name=record.display_name,
        sealed_credentials=record.sealed_credentials,
        version=record.version,
    )


def save_connection(connection: Connection, record: GoogleConnection | ConnectorConnection) -> None:
    provider = "google" if isinstance(record, GoogleConnection) else record.provider
    table = connection_table(provider)
    values = record_values(record)
    now = datetime.now(timezone.utc)
    key: dict[str, Any] = dict(user_id=record.user_id)
    if provider != "google":
        key["provider"] = provider
    connection.execute(
        insert(table)
        .values(**key, **values, created_at=now, updated_at=now)
        .on_conflict_do_update(index_elements=list(key), set_={**values, "updated_at": now})
    )


def revoke_attempts(connection: Connection, user_id: UUID, provider: str) -> None:
    connection.execute(
        update(s.oauth_attempts)
        .where(
            s.oauth_attempts.c.user_id == user_id,
            s.oauth_attempts.c.provider == provider,
            s.oauth_attempts.c.status.in_(("pending", "claimed", "complete")),
        )
        .values(status="revoked", sealed_payload="")
    )


class SqlOAuthState:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def assert_connection(self, user_id: UUID, token: str, provider: str, version: UUID) -> None:
        with self.engine.begin() as connection:
            active_session(connection, user_id, digest(token), datetime.now(timezone.utc))
            if current_version(connection, user_id, provider) != version:
                code = "google_reconnect" if provider == "google" else "connector_reconnect"
                raise IngestionError(code, "Your connection changed. Connect it again.", 409)

    def begin(
        self,
        provider: str,
        purpose: str,
        browser: str,
        sealed_payload: str,
        *,
        user_id: UUID | None = None,
        session_token: str = "",
        peer: str = "",
    ) -> str:
        if not 32 <= len(browser) <= 128 or purpose not in {"signin", "connect"}:
            raise invalid()
        now = datetime.now(timezone.utc)
        # Existing atomic direct-peer authentication throttles; independent transaction keeps
        # rejected attempts counted. No forwarded client address is trusted.
        if not SQLAccountStore(self.engine).consume_auth_attempt(
            "oauth_start", str(user_id or digest(browser)), peer, now
        ):
            raise IngestionError(
                "authentication_rate_limit", "Too many attempts. Try again later.", 429
            )
        state = secrets.token_urlsafe(32)
        with self.engine.begin() as connection:
            connection.execute(
                delete(s.oauth_attempts).where(
                    s.oauth_attempts.c.expires_at < now - timedelta(minutes=10)
                )
            )
            version = None
            if purpose == "connect":
                if user_id is None or not 32 <= len(session_token) <= 256:
                    raise invalid()
                active_session(connection, user_id, digest(session_token), now)
                version = current_version(connection, user_id, provider)
                revoke_attempts(connection, user_id, provider)
            connection.execute(
                s.oauth_attempts.insert().values(
                    state_hash=digest(state),
                    browser_hash=digest(browser),
                    provider=provider,
                    purpose=purpose,
                    user_id=user_id,
                    session_hash=digest(session_token) if user_id else None,
                    connection_version=version,
                    sealed_payload=sealed_payload,
                    status="pending",
                    expires_at=now + timedelta(minutes=10),
                    created_at=now,
                )
            )
        return state

    @staticmethod
    def _attempt(row: Any) -> OAuthAttempt:
        return OAuthAttempt(**{field: row[field] for field in OAuthAttempt.__dataclass_fields__})

    @staticmethod
    def _live(connection: Connection, attempt: OAuthAttempt, status: str) -> Any:
        now = datetime.now(timezone.utc)
        if attempt.purpose == "connect":
            if attempt.user_id is None or attempt.session_hash is None:
                raise invalid()
            active_session(connection, attempt.user_id, attempt.session_hash, now)
        row = (
            connection.execute(
                select(s.oauth_attempts)
                .where(
                    s.oauth_attempts.c.state_hash == attempt.state_hash,
                    s.oauth_attempts.c.status == status,
                    s.oauth_attempts.c.expires_at > now,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise invalid()
        return row

    def claim(self, state: str, browser: str, provider: str, purpose: str) -> OAuthAttempt:
        if not 32 <= len(state) <= 128 or not 32 <= len(browser) <= 128:
            raise invalid()
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(s.oauth_attempts).where(
                        s.oauth_attempts.c.state_hash == digest(state),
                        s.oauth_attempts.c.browser_hash == digest(browser),
                        s.oauth_attempts.c.provider == provider,
                        s.oauth_attempts.c.purpose == purpose,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise invalid()
            attempt = self._attempt(row)
            self._live(connection, attempt, "pending")
            connection.execute(
                update(s.oauth_attempts)
                .where(s.oauth_attempts.c.state_hash == attempt.state_hash)
                .values(status="claimed")
            )
            return attempt

    @staticmethod
    def _handoff(
        connection: Connection,
        attempt: OAuthAttempt,
        *,
        user_id: UUID | None = None,
        error_code: str = "",
    ) -> str:
        handle = secrets.token_urlsafe(32)
        values: dict[str, Any] = dict(
            status="complete",
            sealed_payload="",
            handoff_hash=digest(handle),
            handoff_expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            error_code=error_code,
        )
        if user_id is not None:
            values["user_id"] = user_id
        connection.execute(
            update(s.oauth_attempts)
            .where(s.oauth_attempts.c.state_hash == attempt.state_hash)
            .values(**values)
        )
        return handle

    def fail(self, attempt: OAuthAttempt, error_code: str) -> str:
        with self.engine.begin() as connection:
            self._live(connection, attempt, "claimed")
            return self._handoff(connection, attempt, error_code=error_code[:80])

    def complete_connection(
        self, attempt: OAuthAttempt, record: GoogleConnection | ConnectorConnection
    ) -> str:
        provider = "google" if isinstance(record, GoogleConnection) else record.provider
        with self.engine.begin() as connection:
            self._live(connection, attempt, "claimed")
            if (
                attempt.purpose != "connect"
                or record.user_id != attempt.user_id
                or provider != attempt.provider
                or current_version(connection, record.user_id, provider)
                != attempt.connection_version
            ):
                raise invalid()
            save_connection(connection, record)
            SQLAccountRepository(connection).account_event(
                record.user_id, "connector.connected", datetime.now(timezone.utc), provider
            )
            return self._handoff(connection, attempt)

    def complete_signin(
        self, attempt: OAuthAttempt, subject: str, email: str, display_name: str
    ) -> str:
        if (
            attempt.purpose != "signin"
            or attempt.provider != "google"
            or not 1 <= len(subject) <= 255
        ):
            raise invalid()
        email = normalized_email(email)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            self._live(connection, attempt, "claimed")
            # Insert-or-read under a stable subject lock prevents duplicate new principals.
            from sqlalchemy import text

            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": int(digest("google:" + subject)[:15], 16)},
            )
            row = (
                connection.execute(
                    select(s.external_identities)
                    .where(
                        s.external_identities.c.provider == "google",
                        s.external_identities.c.subject == subject,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row:
                user_id = row["user_id"]
                active_user(connection, user_id)
            else:
                # Never auto-link native accounts or operator sessions by an email claim.
                user_id = connection.execute(
                    insert(s.users)
                    .values(
                        id=uuid4(),
                        email=email,
                        display_name=display_name.strip()[:100],
                        created_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["email"])
                    .returning(s.users.c.id)
                ).scalar_one_or_none()
                if user_id is None:
                    raise IngestionError(
                        "google_identity_conflict",
                        "Use this account's existing sign-in method.",
                        409,
                    )
                connection.execute(
                    s.external_identities.insert().values(
                        provider="google",
                        subject=subject,
                        user_id=user_id,
                        created_at=now,
                    )
                )
                SQLAccountRepository(connection).account_event(user_id, "google.registered", now)
            return self._handoff(connection, attempt, user_id=user_id)

    def exchange(self, handoff: str, browser: str) -> dict[str, str]:
        if not 32 <= len(handoff) <= 128 or not 32 <= len(browser) <= 128:
            raise invalid()
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(s.oauth_attempts).where(
                        s.oauth_attempts.c.handoff_hash == digest(handoff),
                        s.oauth_attempts.c.browser_hash == digest(browser),
                        s.oauth_attempts.c.handoff_expires_at > now,
                        s.oauth_attempts.c.status == "complete",
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise invalid()
            attempt = self._attempt(row)
            if attempt.user_id is not None:
                if attempt.purpose == "connect":
                    active_session(connection, attempt.user_id, attempt.session_hash or "", now)
                else:
                    active_user(connection, attempt.user_id)
            current = connection.execute(
                select(s.oauth_attempts.c.status)
                .where(
                    s.oauth_attempts.c.state_hash == attempt.state_hash,
                    s.oauth_attempts.c.handoff_expires_at > now,
                )
                .with_for_update()
            ).scalar_one_or_none()
            if current != "complete":
                raise invalid()
            result: dict[str, str] = {}
            if row["error_code"]:
                result["error"] = row["error_code"]
            if attempt.purpose == "connect":
                result["provider"] = attempt.provider
            if attempt.user_id is not None:
                token = secrets.token_urlsafe(32)
                SQLAccountRepository(connection).add_account_session(
                    attempt.user_id, digest(token), now + timedelta(hours=8)
                )
                if attempt.session_hash:
                    connection.execute(
                        delete(s.sessions).where(s.sessions.c.token_hash == attempt.session_hash)
                    )
                SQLAccountRepository(connection).account_event(
                    attempt.user_id, "oauth.session_exchanged", now
                )
                result["token"] = token
            connection.execute(
                update(s.oauth_attempts)
                .where(s.oauth_attempts.c.state_hash == attempt.state_hash)
                .values(status="consumed", handoff_hash=None)
            )
            return result
