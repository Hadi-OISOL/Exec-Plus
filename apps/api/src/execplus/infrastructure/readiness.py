"""Use case: Checks the actual ingestion dependencies.

What it does: Tests the migrated database and private object bucket without exposing diagnostics.
"""

import asyncio

from sqlalchemy import Engine, text

from execplus.application.contracts import ComponentStatus
from execplus.application.ports import ObjectStorage


class DatabaseProbe:
    name = "postgresql"

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    async def check(self) -> ComponentStatus:
        def check_database() -> None:
            with self.engine.connect() as connection:
                connection.execute(text("SET LOCAL statement_timeout = 3000"))
                connection.execute(text("SELECT id FROM workspaces LIMIT 0"))
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                if revision != "0001":
                    raise ValueError("Unexpected schema revision")

        await asyncio.to_thread(check_database)
        return ComponentStatus(self.name, True, "available")


class StorageProbe:
    name = "object_storage"

    def __init__(self, storage: ObjectStorage) -> None:
        self.storage = storage

    async def check(self) -> ComponentStatus:
        await asyncio.to_thread(self.storage.ready)
        return ComponentStatus(self.name, True, "available")
