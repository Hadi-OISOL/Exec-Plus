"""Use case: Supplies isolated PostgreSQL and MinIO integration fixtures.

What it does: Applies real migrations in disposable schemas and creates private test buckets.
"""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from execplus.application.services.health import HealthService
from execplus.application.services.workspaces import WorkspaceService
from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.readiness import DatabaseProbe, StorageProbe
from execplus.main import create_app


@pytest.fixture
def integration():
    url = os.environ.get("EXECPLUS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set EXECPLUS_TEST_DATABASE_URL to run real PostgreSQL/MinIO integration tests")
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=url,
        object_store_endpoint=os.getenv(
            "EXECPLUS_TEST_OBJECT_STORE_ENDPOINT", "http://localhost:9000"
        ),
        object_store_bucket="test-" + uuid4().hex,
        object_store_access_key="execplus",
        object_store_secret_key="change-me",
    )
    runtime = build_runtime(settings)
    runtime.engine.dispose()
    runtime.engine = engine
    runtime.identity.engine = engine
    runtime.service = WorkspaceService(
        SQLUnitOfWork(engine), runtime.service.storage, runtime.service.parser
    )
    runtime.health = HealthService((DatabaseProbe(engine), StorageProbe(runtime.service.storage)))
    runtime.service.storage.client.create_bucket(Bucket=settings.object_store_bucket)
    with TestClient(create_app(settings, runtime)) as client:
        yield SimpleNamespace(
            client=client,
            runtime=runtime,
            engine=engine,
            config=config,
            bucket=settings.object_store_bucket,
        )
    storage = runtime.service.storage
    objects = storage.client.list_objects_v2(Bucket=settings.object_store_bucket).get(
        "Contents", []
    )
    for item in objects:
        storage.client.delete_object(Bucket=settings.object_store_bucket, Key=item["Key"])
    storage.client.delete_bucket(Bucket=settings.object_store_bucket)
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()
