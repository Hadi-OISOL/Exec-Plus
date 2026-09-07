"""Use case: Supplies the explicitly local/test identity provider.

What it does: Authenticates expiring opaque sessions using hashes stored in PostgreSQL.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Engine, delete, select

from execplus.application.services.workspaces import normalized_email
from execplus.domain.ingestion import IngestionError, User
from execplus.infrastructure.persistence.schema import sessions, users


class LocalSessionIdentity:
    def __init__(self, engine: Engine, environment: str) -> None:
        if environment not in {"local", "test"}:
            raise ValueError("Local session identity is available only in local/test environments")
        self.engine = engine

    def authenticate(self, token: str) -> User:
        if len(token) < 32 or len(token) > 256:
            raise IngestionError("unauthenticated", "A valid session token is required.", 401)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(users)
                    .join(sessions)
                    .where(
                        sessions.c.token_hash == token_hash,
                        sessions.c.expires_at > datetime.now(timezone.utc),
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise IngestionError("unauthenticated", "The session is invalid or expired.", 401)
        return User(**row)

    def revoke(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.token_hash == token_hash))

    def provision(self, email: str, display_name: str = "") -> str:
        email = normalized_email(email)
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        with self.engine.begin() as connection:
            user_id = connection.execute(
                select(users.c.id).where(users.c.email == email)
            ).scalar_one_or_none()
            if user_id is None:
                user_id = uuid4()
                connection.execute(
                    users.insert().values(
                        id=user_id,
                        email=email,
                        display_name=display_name.strip()[:100],
                        created_at=now,
                    )
                )
            connection.execute(
                sessions.insert().values(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=user_id,
                    expires_at=now + timedelta(hours=8),
                )
            )
        return token
