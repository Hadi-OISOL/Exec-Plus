"""Use case: Proves a connected platform can refresh a dataset through the staged refresh pipeline.

What it does: Stages platform snapshots as candidates, activates them, checks drift, access, audit.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from execplus.application.google_ports import SheetTab, SpreadsheetInfo
from test_connectors_service import enable
from test_google_access import SHEET
from test_google_access import connect as connect_google
from test_google_access import enable as enable_google
from test_refresh import activate, setup
from test_workspace_integration import identity

FRESH = [{"city": "Karachi", "amount": "0.30"}, {"city": "Lahore", "amount": "0.20"}]


def refresh_from(env, headers, path, sender=None, **body):
    current = env.client.get(path + "/refresh", headers=headers).json()["feed"]
    options = dict(
        request_id=str(uuid4()),
        expected_version=current["version"],
        mode="replace",
        keys=[],
        duplicates="keep_all",
        as_of=datetime.now(timezone.utc).isoformat(),
    )
    return env.client.post(
        path + "/connectors/odoo/refresh-candidates",
        headers=sender or headers,
        json=dict(source_id="invoices", options=options) | body,
    )


def connect(env, headers):
    saved = env.client.post(
        "/connectors/odoo/credentials",
        headers=headers,
        json={"values": {"url": "https://odoo.example", "api_key": "k"}},
    )
    assert saved.status_code == 200, saved.text


def test_a_platform_snapshot_refreshes_the_dataset_through_review_and_activation(integration):
    env = integration
    headers, _, wid, _, uid, path, _ = setup(env)
    _, credentials, _ = enable(env)
    connect(env, headers)
    credentials.fetch = lambda session, source_id, max_rows: FRESH
    staged = refresh_from(env, headers, path)
    assert staged.status_code == 201, staged.text
    candidate = staged.json()
    assert candidate["status"] == "queued" and candidate["details"]["schema_changed"] is False
    assert env.client.get(path + "/refresh", headers=headers).json()["feed"]["source"][
        "upload_id"
    ] == str(uid)
    assert activate(env, headers, wid, candidate).json()["status"] == "activated"
    active = env.client.get(path + "/refresh", headers=headers).json()["feed"]["source"]
    content = env.client.get(
        f"{path}/uploads/{active['upload_id']}/content", headers=headers
    ).content.decode()
    assert content.splitlines() == ["city,amount", "Karachi,0.30", "Lahore,0.20"]
    with env.engine.connect() as connection:
        audited = connection.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE workspace_id = :w "
                "AND action = 'connector.refresh_staged' AND resource_id = :t"
            ),
            dict(w=wid, t=candidate["id"]),
        ).scalar_one()
    assert audited == 1


def test_a_changed_platform_schema_waits_for_review(integration):
    env = integration
    headers, *_, path, _ = setup(env)
    _, credentials, _ = enable(env)
    connect(env, headers)
    credentials.fetch = lambda session, source_id, max_rows: [
        {**row, "region": "South"} for row in FRESH
    ]
    candidate = refresh_from(env, headers, path).json()
    assert candidate["status"] == "needs_review" and candidate["details"]["schema_changed"]


def test_refresh_needs_editor_rights_and_a_connection_before_any_platform_call(integration):
    env = integration
    headers, *_, path, _ = setup(env)
    _, credentials, _ = enable(env)
    calls = []
    credentials.fetch = lambda session, source_id, max_rows: calls.append(source_id) or FRESH
    missing = refresh_from(env, headers, path)
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "connector_not_connected"
    outsider, _ = identity(env, "refresh-outsider@example.test")
    connect(env, outsider)
    intrusion = refresh_from(env, headers, path, sender=outsider)
    assert intrusion.status_code in {403, 404} and calls == []
    connect(env, headers)
    credentials.fetch = lambda session, source_id, max_rows: []
    empty = refresh_from(env, headers, path)
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_source"


def test_a_google_sheet_refreshes_the_dataset_through_the_same_pipeline(integration):
    env = integration
    headers, actor, wid, *_, path, _ = setup(env)
    google, _ = enable_google(env)
    connect_google(env, google, headers, email=actor.email)
    google.sheets[SHEET] = (
        SpreadsheetInfo("Orders", (SheetTab(0, "Jan", 3, 2),)),
        {"Jan": [["city", "amount"], ["Karachi", "0.30"], ["Lahore", "0.20"]]},
    )
    current = env.client.get(path + "/refresh", headers=headers).json()["feed"]
    options = dict(
        request_id=str(uuid4()),
        expected_version=current["version"],
        mode="replace",
        keys=[],
        duplicates="keep_all",
        as_of=datetime.now(timezone.utc).isoformat(),
    )
    staged = env.client.post(
        path + "/google-sheets/refresh-candidates",
        headers=headers,
        json=dict(spreadsheet_id=SHEET, options=options),
    )
    assert staged.status_code == 201, staged.text
    candidate = staged.json()
    assert candidate["status"] == "queued"
    assert activate(env, headers, wid, candidate).json()["status"] == "activated"
    with env.engine.connect() as connection:
        actions = connection.execute(
            text("SELECT action FROM audit_events WHERE resource_id = :t"),
            dict(t=candidate["id"]),
        ).scalars()
        assert "google_sheets.refresh_staged" in list(actions)
