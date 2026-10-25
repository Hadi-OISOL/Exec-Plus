"""Use case: Proves the MySQL, MariaDB and SQL Server connectors end to end through the real API.

What it does: Connects, browses with row counts, previews, imports a table and a custom SELECT,
stages a refresh and checks sealed secrets and workspace isolation.
"""

from datetime import datetime, timezone
from uuid import uuid4

from cryptography.fernet import Fernet
from sqlalchemy import text

from execplus.application.services.connectors import ConnectorService
from execplus.infrastructure.connectors.base import HostPolicy
from execplus.infrastructure.persistence.connector_connections import SqlConnectorConnections
from execplus.infrastructure.persistence.repository import SQLUnitOfWork
from execplus.infrastructure.token_vault import FernetTokenVault
from test_connectors_service import stored
from test_connectors_sql_databases import server  # noqa: F401
from test_refresh import activate, setup
from test_workspace_integration import dataset, identity, workspace


def enable(env, provider, kind):
    env.runtime.connectors = ConnectorService(
        {provider: kind(HostPolicy(True))},
        FernetTokenVault(Fernet.generate_key().decode()),
        SqlConnectorConnections(env.engine),
        env.runtime.service,
        SQLUnitOfWork(env.engine),
        oauth=env.runtime.oauth_state,
        public_api_url="http://api.test",
        web_origin="http://web.test",
        max_rows=100,
        database_max_rows=1000,
    )
    env.client.headers["Origin"] = env.client.app.state.web_origin


def test_database_connects_previews_imports_refreshes_and_keeps_tenants_apart(
    integration,
    server,  # noqa: F811
):
    name, kind, schema, credentials, _, _ = server
    provider = "sqlserver" if name == "sqlserver" else "mysql"
    enable(integration, provider, kind)
    owner, user = identity(integration, f"{name}-owner@example.test")
    outsider, other = identity(integration, f"{name}-outsider@example.test")
    secret = credentials["password"]
    route = f"/connectors/{provider}"

    catalog = {
        item["id"]: item for item in integration.client.get("/connectors", headers=owner).json()
    }
    assert catalog[provider]["queries"] is True
    assert [item["name"] for item in catalog[provider]["fields"]][-1] == "tls"
    assert catalog["postgresql"]["configured"] is False

    wrong = integration.client.post(
        f"{route}/credentials",
        headers=owner,
        json={"values": {**credentials, "password": secret + "-wrong"}},
    )
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "connector_credentials_rejected"
    assert secret not in wrong.text and stored(integration, user.id, provider) is None

    saved = integration.client.post(
        f"{route}/credentials", headers=owner, json={"values": {**credentials, "tls": "require"}}
    )
    assert saved.status_code == 200, saved.text
    sealed = stored(integration, user.id, provider)
    assert sealed and secret not in sealed and credentials["user"] not in sealed
    assert secret not in integration.client.get("/connectors", headers=owner).text

    schemas = integration.client.get(f"{route}/sources", headers=owner).json()
    ours = next(item for item in schemas if item["label"] == schema)
    tables = integration.client.get(
        f"{route}/sources", headers=owner, params={"parent": ours["id"]}
    ).json()
    orders = next(item for item in tables if item["label"] == "orders")
    assert isinstance(orders["rows"], int)

    preview = integration.client.post(
        f"{route}/preview", headers=owner, json={"source_id": orders["id"]}
    )
    assert preview.status_code == 200 and preview.json()["rows"][0][2] == "12345678901234.5678"
    refused = integration.client.post(
        f"{route}/preview",
        headers=owner,
        json={"source_id": f"query/DELETE FROM {schema}.orders"},
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "connector_query_refused"

    wid = workspace(integration, owner)
    base = f"/workspaces/{wid}/datasets/{dataset(integration, owner, wid)}"
    imported = integration.client.post(
        f"{base}{route}/import", headers=owner, json={"source_id": orders["id"]}
    )
    assert imported.status_code == 201, imported.text
    body = integration.client.get(
        f"{base}/uploads/{imported.json()['id']}/content", headers=owner
    ).content.decode()
    assert body.splitlines()[1].startswith("1,Customer 1,12345678901234.5678,")
    assert imported.json()["filename"].endswith(" - orders.csv")

    query = f"query/SELECT customer AS city, amount FROM {schema}.orders WHERE id > 1"
    custom = integration.client.post(
        f"{base}{route}/import", headers=owner, json={"source_id": query}
    )
    assert custom.status_code == 201, custom.text
    assert "Custom query" in custom.json()["filename"]

    headers, _, refresh_wid, _, _, path, _ = setup(integration)
    integration.client.post(f"{route}/credentials", headers=headers, json={"values": credentials})
    current = integration.client.get(path + "/refresh", headers=headers).json()["feed"]
    staged = integration.client.post(
        f"{path}{route}/refresh-candidates",
        headers=headers,
        json=dict(
            source_id=query,
            options=dict(
                request_id=str(uuid4()),
                expected_version=current["version"],
                mode="replace",
                keys=[],
                duplicates="keep_all",
                as_of=datetime.now(timezone.utc).isoformat(),
            ),
        ),
    )
    assert staged.status_code == 201, staged.text
    assert staged.json()["details"]["schema_changed"] is False
    assert (
        activate(integration, headers, refresh_wid, staged.json()).json()["status"] == "activated"
    )
    active = integration.client.get(path + "/refresh", headers=headers).json()["feed"]["source"]
    refreshed = integration.client.get(
        f"{path}/uploads/{active['upload_id']}/content", headers=headers
    ).content.decode()
    assert refreshed.splitlines() == ["city,amount", "Customer 2,0.0001", "Customer 3,-7.5000"]

    assert (
        integration.client.get(f"{route}/sources", headers=outsider).json()["error"]["code"]
        == "connector_not_connected"
    )
    integration.client.post(f"{route}/credentials", headers=outsider, json={"values": credentials})
    intrusion = integration.client.post(
        f"{base}{route}/import", headers=outsider, json={"source_id": orders["id"]}
    )
    assert intrusion.status_code in {403, 404}
    with integration.engine.connect() as connection:
        uploads = connection.execute(
            text("SELECT count(*) FROM uploads WHERE workspace_id = :w"), dict(w=wid)
        ).scalar_one()
        audited = connection.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE workspace_id = :w "
                "AND action = 'connector.imported'"
            ),
            dict(w=wid),
        ).scalar_one()
    assert uploads == 2 and audited == 2
    assert stored(integration, other.id, provider) != sealed
