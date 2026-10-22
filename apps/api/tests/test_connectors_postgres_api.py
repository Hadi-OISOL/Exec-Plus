"""Use case: Proves the PostgreSQL connector end to end through the real API and a real database.

What it does: Connects, browses, imports, re-imports as a refresh and checks secrets and tenants.
"""

from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from execplus.application.services.connectors import ConnectorService
from execplus.infrastructure.connectors.base import HostPolicy
from execplus.infrastructure.connectors.database import PostgresConnector
from execplus.infrastructure.persistence.connector_connections import SqlConnectorConnections
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.token_vault import FernetTokenVault
from test_connectors_database import database  # noqa: F401
from test_connectors_service import stored
from test_workspace_integration import dataset, identity, workspace


def enable(env):
    env.runtime.connectors = ConnectorService(
        {"postgresql": PostgresConnector(HostPolicy(True))},
        FernetTokenVault(Fernet.generate_key().decode()),
        SqlConnectorConnections(env.engine),
        env.runtime.service,
        SQLUnitOfWork(env.engine),
        oauth=env.runtime.oauth_state,
        public_api_url="http://api.test",
        web_origin="http://web.test",
        max_rows=1000,
    )
    env.client.headers["Origin"] = env.client.app.state.web_origin


@pytest.fixture
def reader(database):  # noqa: F811
    schema, credentials, source = database
    role, secret = "reader_" + uuid4().hex[:10], "pw-" + uuid4().hex
    with source.connect() as connection:
        connection.execute(text(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{secret}'"))
        connection.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
        connection.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'))
    yield schema, {**credentials, "user": role, "password": secret}, source
    with source.connect() as connection:
        connection.execute(text(f'DROP OWNED BY "{role}"'))
        connection.execute(text(f'DROP ROLE "{role}"'))


def content(env, headers, base, upload_id):
    return env.client.get(f"{base}/uploads/{upload_id}/content", headers=headers).content.decode()


def test_postgres_connects_imports_refreshes_and_keeps_secrets_and_tenants_apart(
    integration, reader
):
    schema, credentials, source = reader
    enable(integration)
    owner, user = identity(integration, "pg-owner@example.test")
    outsider, other = identity(integration, "pg-outsider@example.test")
    secret = credentials["password"]

    wrong = integration.client.post(
        "/connectors/postgresql/credentials",
        headers=owner,
        json={"values": {**credentials, "password": secret + "-wrong"}},
    )
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "connector_credentials_rejected"
    assert secret not in wrong.text and stored(integration, user.id, "postgresql") is None

    saved = integration.client.post(
        "/connectors/postgresql/credentials", headers=owner, json={"values": credentials}
    )
    assert saved.status_code == 200, saved.text
    sealed = stored(integration, user.id, "postgresql")
    assert sealed and secret not in sealed and credentials["user"] not in sealed
    assert secret not in integration.client.get("/connectors", headers=owner).text

    schemas = integration.client.get("/connectors/postgresql/sources", headers=owner).json()
    ours = next(item for item in schemas if item["label"] == schema)
    tables = integration.client.get(
        "/connectors/postgresql/sources", headers=owner, params={"parent": ours["id"]}
    ).json()
    orders = next(item["id"] for item in tables if item["label"] == "orders")

    wid = workspace(integration, owner)
    base = f"/workspaces/{wid}/datasets/{dataset(integration, owner, wid)}"
    first = integration.client.post(
        f"{base}/connectors/postgresql/import", headers=owner, json={"source_id": orders}
    )
    assert first.status_code == 201, first.text
    lines = content(integration, owner, base, first.json()["id"]).splitlines()
    assert len(lines) == 6 and lines[1].startswith("1,Customer 1,12.50,false,")

    with source.connect() as connection:
        connection.execute(
            text(f"INSERT INTO \"{schema}\".orders (customer, amount) VALUES ('Late', 99.99)")
        )
    refreshed = integration.client.post(
        f"{base}/connectors/postgresql/import", headers=owner, json={"source_id": orders}
    )
    assert refreshed.status_code == 201 and refreshed.json()["id"] != first.json()["id"]
    assert "Late,99.99" in content(integration, owner, base, refreshed.json()["id"])
    assert content(integration, owner, base, first.json()["id"]).splitlines() == lines

    assert (
        integration.client.get("/connectors/postgresql/sources", headers=outsider).json()["error"][
            "code"
        ]
        == "connector_not_connected"
    )
    integration.client.post(
        "/connectors/postgresql/credentials", headers=outsider, json={"values": credentials}
    )
    intrusion = integration.client.post(
        f"{base}/connectors/postgresql/import", headers=outsider, json={"source_id": orders}
    )
    assert intrusion.status_code in {403, 404}
    with integration.engine.connect() as connection:
        uploads = connection.execute(
            text("SELECT count(*) FROM uploads WHERE workspace_id = :w"), dict(w=wid)
        ).scalar_one()
    assert uploads == 2 and stored(integration, other.id, "postgresql") != sealed
