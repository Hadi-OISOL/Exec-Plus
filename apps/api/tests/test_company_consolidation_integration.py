"""Use case: Verifies private company worksheets against real ledger files.

What it does: Checks exact multi-workspace receipts, explicit mappings, replay,
exports and policy/revocation changes around source reads and rendering.
"""

import asyncio
import copy
import io
import json
import zipfile
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import select, text

from execplus.infrastructure.persistence import schema as s
from test_studies import add_member
from test_understanding import confirm, context
from test_workspace_integration import accept, dataset, identity, invite, upload, workspace


def fixture(env, existing=None):
    if existing is None:
        owner, actor = identity(env, f"consolidation-{uuid4().hex}@example.test")
        created = env.client.post("/organizations", headers=owner, json={"name": "Fictional group"})
        assert created.status_code == 201, created.text
        oid = created.json()["id"]
    else:
        owner, actor, oid = existing
    companies, source_roots = [], []
    contents = [
        b"account,amount,counterparty\nCash,100.00,External\nDue,20.00,B\nEquity,-120.00,External\n",
        b"account,amount,counterparty\nCash,200.00,External\nDue,-40.00,A\nEquity,-160.00,External\n",
    ]
    for index, content in enumerate(contents):
        wid = workspace(env, owner)
        attached = env.client.post(
            f"/workspaces/{wid}/department",
            headers=owner,
            json={"organization_id": oid, "name": f"Company {index + 1}"},
        )
        assert attached.status_code == 200, attached.text
        did = dataset(env, owner, wid)
        uid = upload(env, owner, wid, did, content).json()["id"]
        source_root = f"/workspaces/{wid}/datasets/{did}/uploads/{uid}"
        meaning = context(env, owner, source_root)
        meaning["definition"]["domain"] = "finance"
        for column in meaning["definition"]["columns"]:
            column["role"] = "metric" if column["name"] == "amount" else "dimension"
            if column["name"] == "amount":
                column["currency"] = "USD" if index == 0 else "EUR"
                column["unit"] = column["currency"]
        saved = confirm(env, owner, source_root, meaning)
        assert saved.status_code == 201, saved.text
        current = context(env, owner, source_root)
        companies.append(
            dict(
                workspace_id=wid,
                dataset_id=did,
                upload_id=uid,
                revision_id=current["revision_id"],
                understanding_id=current["history"][-1]["id"],
                account_column="account",
                amount_column="amount",
                counterparty_column="counterparty",
                currency="USD" if index == 0 else "EUR",
                period_start="2026-01-01",
                period_end="2026-12-31",
                sign_convention="debit_positive",
                coverage_confirmed=True,
                counterparties=[],
            )
        )
        source_roots.append(source_root)
    for index, company in enumerate(companies):
        company["counterparties"] = [
            {
                "raw_value": "B" if index == 0 else "A",
                "company_id": companies[1 - index]["workspace_id"],
            }
        ]
    request = {
        "name": "Prepared group worksheet",
        "companies": companies,
        "worksheet": {
            "reporting_currency": "USD",
            "assumptions_confirmed": True,
            "mappings": {
                company["workspace_id"]: [
                    {
                        "account": account,
                        "group_account": "Internal" if account == "Due" else account,
                        "rate_key": "declared",
                    }
                    for account in ("Cash", "Due", "Equity")
                ]
                for company in companies
            },
            "rates": {
                company["workspace_id"]: [
                    {
                        "key": "declared",
                        "basis": "closing",
                        "value": "1" if index == 0 else "0.5",
                        "as_of": "2026-12-31",
                        "reference": "Fictional test rate",
                    }
                ]
                for index, company in enumerate(companies)
            },
            "eliminations": [
                {
                    "name": "Internal settlement",
                    "entries": [
                        {
                            "company_id": companies[0]["workspace_id"],
                            "account": "Due",
                            "counterparty": companies[1]["workspace_id"],
                            "amount": "-20",
                        },
                        {
                            "company_id": companies[1]["workspace_id"],
                            "account": "Due",
                            "counterparty": companies[0]["workspace_id"],
                            "amount": "20",
                        },
                    ],
                }
            ],
        },
    }
    return (
        owner,
        actor,
        oid,
        f"/organizations/{oid}/consolidations",
        request,
        source_roots,
        contents,
    )


def create(env, owner, path, request):
    response = env.client.post(path, headers=owner, json=request)
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_ledger_mappings_exact_translation_elimination_and_immutable_reopen(integration):
    env = integration
    owner, actor, _oid, path, request, roots, contents = fixture(env)
    options = env.client.get(path + "/options", headers=owner)
    assert options.status_code == 200 and len(options.json()["companies"]) == 2
    first = request["companies"][0]
    source = env.client.post(
        path + "/source-options",
        headers=owner,
        json={key: first[key] for key in ("workspace_id", "dataset_id", "upload_id")},
    )
    assert source.status_code == 200, source.text
    assert source.json()["amounts"] == [{"name": "amount", "currency": "USD"}]
    preview = env.client.post(
        path + "/preview-company",
        headers=owner,
        json={
            key: first[key]
            for key in (
                "workspace_id",
                "dataset_id",
                "upload_id",
                "revision_id",
                "understanding_id",
                "account_column",
                "amount_column",
                "counterparty_column",
                "currency",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["accounts"] == ["Cash", "Due", "Equity"]
    before = copy.deepcopy(request)
    value = create(env, owner, path, request)
    assert request == before
    result = value["run"]["result"]
    assert result["consolidated"] == [
        {"group_account": "Cash", "amount": "200"},
        {"group_account": "Equity", "amount": "-200"},
        {"group_account": "Internal", "amount": "0"},
    ]
    assert result["totals"] == {"combined": "0", "eliminations": "0", "consolidated": "0"}
    assert result["remaining_internal_balances"] == []
    assert value["source_rows"][0]["rows"][1] == ["Due", "20", "B"]
    opened = env.client.get(path + "/" + value["run"]["id"], headers=owner)
    assert opened.status_code == 200, opened.text
    assert opened.json() == value
    with env.engine.connect() as connection:
        receipts = (
            connection.execute(
                select(s.query_executions).where(s.query_executions.c.actor_id == actor.id)
            )
            .mappings()
            .all()
        )
    assert all(row["aggregation"] == "analysis" for row in receipts)
    for root, content in zip(roots, contents, strict=True):
        assert env.client.get(root + "/content", headers=owner).content == content


def test_saved_worksheet_private_even_for_members_of_every_company(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    value = create(env, owner, path, request)
    member, user = add_member(env, owner, request["companies"][0]["workspace_id"])
    wid = request["companies"][1]["workspace_id"]
    invitation = invite(env, owner, wid, user.email, "admin").json()["id"]
    assert accept(env, member, wid, invitation).status_code == 200
    assert env.client.get(path, headers=member).status_code == 404
    assert env.client.get(path + "/options", headers=member).status_code == 404
    company = request["companies"][0]
    source = {key: company[key] for key in ("workspace_id", "dataset_id", "upload_id")}
    assert env.client.post(path + "/source-options", headers=member, json=source).status_code == 404
    fields = {
        key: company[key]
        for key in (
            "workspace_id",
            "dataset_id",
            "upload_id",
            "revision_id",
            "understanding_id",
            "account_column",
            "amount_column",
            "counterparty_column",
            "currency",
        )
    }
    assert (
        env.client.post(path + "/preview-company", headers=member, json=fields).status_code == 404
    )
    assert env.client.post(path, headers=member, json=request).status_code == 404
    assert env.client.get(path + "/" + value["run"]["id"], headers=member).status_code == 404
    for format in ("pdf", "xlsx", "csv", "png"):
        assert (
            env.client.get(
                path + "/" + value["run"]["id"] + f"/export.{format}", headers=member
            ).status_code
            == 404
        )


@pytest.mark.parametrize(
    "change",
    ["currency", "missing_account", "missing_amount", "filtered", "partial_access", "counterparty"],
)
def test_incomplete_or_ambiguous_ledger_never_saves_a_worksheet(integration, change):
    env = integration
    owner, actor, _, path, request, roots, _ = fixture(env)
    first = request["companies"][0]
    if change == "currency":
        first["currency"] = "GBP"
    elif change == "counterparty":
        first["counterparties"][0]["raw_value"] = "Not present"
    elif change == "partial_access":
        response = env.client.put(
            f"/workspaces/{first['workspace_id']}/datasets/{first['dataset_id']}/access-policy",
            headers=owner,
            json={
                "expected_version": 0,
                "enabled": True,
                "grants": [
                    {
                        "user_id": str(actor.id),
                        "columns": None,
                        "conditions": [{"column": "account", "operator": "eq", "value": "Cash"}],
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text
    elif change == "filtered":
        current = context(env, owner, roots[0])
        current["definition"]["metrics"] = [
            {
                "name": "Only cash",
                "column": "amount",
                "aggregation": "sum",
                "filters": [{"column": "account", "operator": "eq", "value": "Cash"}],
            }
        ]
        saved = confirm(env, owner, roots[0], current)
        assert saved.status_code == 201, saved.text
        first["understanding_id"] = context(env, owner, roots[0])["history"][-1]["id"]
    else:
        raw = (
            b"account,amount,counterparty\n,20,B\n"
            if change == "missing_account"
            else b"account,amount,counterparty\nDue,,B\nCash,1,External\n"
        )
        uid = upload(env, owner, first["workspace_id"], first["dataset_id"], raw).json()["id"]
        root = f"/workspaces/{first['workspace_id']}/datasets/{first['dataset_id']}/uploads/{uid}"
        current = context(env, owner, root)
        for column in current["definition"]["columns"]:
            column["role"] = "metric" if column["name"] == "amount" else "dimension"
            if column["name"] == "amount":
                column["unit"] = column["currency"] = "USD"
        saved = confirm(env, owner, root, current)
        assert saved.status_code == 201, saved.text
        first.update(
            upload_id=uid,
            revision_id=current["revision_id"],
            understanding_id=context(env, owner, root)["history"][-1]["id"],
        )
    response = env.client.post(path, headers=owner, json=request)
    assert response.status_code in {403, 404, 409, 422}, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.consolidation_runs)).first() is None


def test_four_formats_include_all_layers_raw_counterparties_and_exact_sources(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    value = create(env, owner, path, request)
    target = path + "/" + value["run"]["id"]
    for format in ("pdf", "xlsx", "csv", "png"):
        result = env.client.get(target + f"/export.{format}", headers=owner)
        assert result.status_code == 200, result.text[:200]
        assert "no-store" in result.headers["cache-control"]
        if format == "pdf":
            extracted = " ".join(
                page.extract_text() for page in PdfReader(io.BytesIO(result.content)).pages
            )
            assert (
                "Consolidated balances" in extracted
                and "Fictional test rate" in extracted
                and "Original ledger rows" in extracted
            )
        elif format == "xlsx":
            book = load_workbook(io.BytesIO(result.content), data_only=False)
            strings = [str(cell.value) for sheet in book for row in sheet for cell in row]
            assert "20" in strings and "B" in strings and "-200" in strings
        elif format == "csv":
            archive = zipfile.ZipFile(io.BytesIO(result.content))
            text_value = "\n".join(archive.read(name).decode() for name in archive.namelist())
            assert "Fictional test rate" in text_value and "Fictional test rate" in text_value
        else:
            from PIL import Image

            image = Image.open(io.BytesIO(result.content))
            assert image.format == "PNG" and image.width >= 800
            assert "Fictional test rate" in json.dumps(image.info)


def test_policy_change_during_projection_holds_no_company_lock_and_saves_nothing(
    integration, monkeypatch
):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    original = env.runtime.analytics.executor.execute
    changed = False

    def revoke():
        for company in request["companies"]:
            with env.engine.begin() as connection:
                connection.execute(
                    text("SELECT id FROM workspaces WHERE id=:wid FOR UPDATE NOWAIT"),
                    {"wid": UUID(company["workspace_id"])},
                )
        company = request["companies"][0]
        response = env.client.put(
            f"/workspaces/{company['workspace_id']}/datasets/{company['dataset_id']}/access-policy",
            headers=owner,
            json={"expected_version": 0, "enabled": True, "grants": []},
        )
        assert response.status_code == 200, response.text

    async def execute(*args, **kwargs):
        nonlocal changed
        result = await original(*args, **kwargs)
        if not changed:
            changed = True
            await asyncio.to_thread(revoke)
        return result

    monkeypatch.setattr(env.runtime.analytics.executor, "execute", execute)
    response = env.client.post(path, headers=owner, json=request)
    assert response.status_code == 404, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.consolidation_runs)).first() is None


def test_reading_historical_source_preserves_result_but_marks_new_meaning(integration):
    env = integration
    owner, _, _, path, request, roots, _ = fixture(env)
    value = create(env, owner, path, request)
    current = context(env, owner, roots[0])
    current["definition"]["description"] = "New reviewed description, same original data"
    assert confirm(env, owner, roots[0], current).status_code == 201
    reopened = env.client.get(path + "/" + value["run"]["id"], headers=owner)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["run"] == value["run"] and reopened.json()["current"] is False
    stale = env.client.post(path, headers=owner, json=request)
    assert stale.status_code == 409, stale.text


def test_export_policy_revocation_discards_rendered_bytes_without_workspace_locks(
    integration, monkeypatch
):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    value = create(env, owner, path, request)
    original = env.runtime.result_exports.renderer.render

    def render(*args, **kwargs):
        payload = original(*args, **kwargs)
        for company in request["companies"]:
            with env.engine.begin() as connection:
                connection.execute(
                    text("SELECT id FROM workspaces WHERE id=:wid FOR UPDATE NOWAIT"),
                    {"wid": UUID(company["workspace_id"])},
                )
        company = request["companies"][1]
        revoked = env.client.put(
            f"/workspaces/{company['workspace_id']}/datasets/{company['dataset_id']}/access-policy",
            headers=owner,
            json={"expected_version": 0, "enabled": True, "grants": []},
        )
        assert revoked.status_code == 200, revoked.text
        return payload

    monkeypatch.setattr(env.runtime.result_exports.renderer, "render", render)
    response = env.client.get(path + "/" + value["run"]["id"] + "/export.pdf", headers=owner)
    assert response.status_code == 404 and response.headers["content-type"] == "application/json"
    assert env.client.get(path, headers=owner).json() == []


@pytest.mark.parametrize("stage", ["projection", "export"])
def test_lost_organization_ownership_refuses_new_or_rendered_results(
    integration, monkeypatch, stage
):
    env = integration
    owner, _, oid, path, request, _, _ = fixture(env)
    replacement, user = identity(env, f"new-organization-owner-{uuid4().hex}@example.test")

    def transfer():
        with env.engine.begin() as connection:
            connection.execute(
                s.organizations.update()
                .where(s.organizations.c.id == UUID(oid))
                .values(owner_id=user.id)
            )

    if stage == "projection":
        original = env.runtime.analytics.executor.execute

        async def execute(*args, **kwargs):
            result = await original(*args, **kwargs)
            transfer()
            return result

        monkeypatch.setattr(env.runtime.analytics.executor, "execute", execute)
        response = env.client.post(path, headers=owner, json=request)
        with env.engine.connect() as connection:
            assert connection.execute(select(s.consolidation_runs)).first() is None
    else:
        saved = create(env, owner, path, request)
        original = env.runtime.result_exports.renderer.render

        def render(*args, **kwargs):
            result = original(*args, **kwargs)
            transfer()
            return result

        monkeypatch.setattr(env.runtime.result_exports.renderer, "render", render)
        response = env.client.get(path + "/" + saved["run"]["id"] + "/export.pdf", headers=owner)
        assert (
            env.client.get(path + "/" + saved["run"]["id"], headers=replacement).status_code == 404
        )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert env.client.get(path + "/options", headers=owner).status_code == 404
    assert env.client.get(path, headers=owner).status_code == 404


def test_unmapped_uuid_looking_counterparty_stays_external_and_requires_explicit_alias(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    request["companies"][0]["counterparties"] = []
    request["companies"][1]["counterparties"] = []
    rejected = env.client.post(path, headers=owner, json=request)
    assert rejected.status_code == 422, rejected.text
    request["worksheet"]["eliminations"] = []
    value = create(env, owner, path, request)
    assert all(item["internal"] is False for item in value["run"]["result"]["source_balances"])
    assert value["source_rows"][0]["rows"][1][-1] == "B"


def test_saved_run_and_receipt_tampering_is_refused(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    value = create(env, owner, path, request)
    damaged = copy.deepcopy(value["run"]["result"])
    damaged["consolidated"][0]["amount"] = "999999"
    with env.engine.begin() as connection:
        connection.execute(
            s.consolidation_runs.update()
            .where(s.consolidation_runs.c.id == UUID(value["run"]["id"]))
            .values(result=damaged)
        )
    response = env.client.get(path + "/" + value["run"]["id"], headers=owner)
    assert response.status_code == 409, response.text


def replace_ledger(env, owner, company, content):
    uid = upload(env, owner, company["workspace_id"], company["dataset_id"], content).json()["id"]
    root = f"/workspaces/{company['workspace_id']}/datasets/{company['dataset_id']}/uploads/{uid}"
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        column["role"] = "metric" if column["name"] == "amount" else "dimension"
        if column["name"] == "amount":
            column["unit"] = column["currency"] = company["currency"]
    response = confirm(env, owner, root, current)
    assert response.status_code == 201, response.text
    company.update(
        upload_id=uid,
        revision_id=current["revision_id"],
        understanding_id=context(env, owner, root)["history"][-1]["id"],
    )


def test_large_decimal_and_uuid_external_party_retain_exact_identity(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    first, second = request["companies"]
    external = second["workspace_id"]
    replace_ledger(
        env,
        owner,
        first,
        f"account,amount,counterparty\nCash,9007199254740993.000001,External\nDue,20.00,{external}\nEquity,-9007199254741013.000001,External\n".encode(),
    )
    first["counterparties"] = []
    request["worksheet"]["eliminations"] = []
    value = create(env, owner, path, request)
    balances = value["run"]["result"]["consolidated"]
    assert (
        next(row["amount"] for row in balances if row["group_account"] == "Cash")
        == "9007199254741093.000001"
    )
    source = value["source_rows"][0]["rows"]
    assert Decimal(source[0][1]) == Decimal("9007199254740993.000001") and source[1][2] == external
    internal = [
        row
        for row in value["run"]["result"]["source_balances"]
        if row["company_id"] == first["workspace_id"] and row["account"] == "Due"
    ]
    assert internal[0]["counterparty"] is None and internal[0]["internal"] is False
    reopened = env.client.get(path + "/" + value["run"]["id"], headers=owner)
    assert reopened.status_code == 200 and reopened.json() == value


def test_invalid_calendar_day_returns_actionable_input_error(integration):
    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    request["companies"][0]["period_end"] = "2026-02-31"
    response = env.client.post(path, headers=owner, json=request)
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "consolidation_period"
    )


def test_source_revision_changed_inside_object_read_refuses_new_run_without_lock(
    integration, monkeypatch
):
    env = integration
    owner, _, _, path, request, roots, _ = fixture(env)
    current = context(env, owner, roots[0])
    current["definition"]["description"] = "Changed during source read"
    original = env.runtime.analytics.storage.read
    changed = False

    def read(uploaded):
        nonlocal changed
        payload = original(uploaded)
        if not changed:
            changed = True
            for company in request["companies"]:
                with env.engine.begin() as connection:
                    connection.execute(
                        text("SELECT id FROM workspaces WHERE id=:wid FOR UPDATE NOWAIT"),
                        {"wid": UUID(company["workspace_id"])},
                    )
            saved = confirm(env, owner, roots[0], current)
            assert saved.status_code == 201, saved.text
        return payload

    monkeypatch.setattr(env.runtime.analytics.storage, "read", read)
    response = env.client.post(path, headers=owner, json=request)
    assert response.status_code == 409, response.text
    with env.engine.connect() as connection:
        assert connection.execute(select(s.consolidation_runs)).first() is None


def test_options_rechecks_access_after_reading_filenames_without_holding_workspace_locks(
    integration, monkeypatch
):
    from execplus.infrastructure.persistence.consolidations import SQLConsolidationRepository

    env = integration
    owner, _, _, path, request, _, _ = fixture(env)
    company = request["companies"][0]
    original = SQLConsolidationRepository.uploads
    changed = False

    def uploads(repo, wid, did):
        nonlocal changed
        records = original(repo, wid, did)
        if str(did) == company["dataset_id"] and not changed:
            changed = True
            for source in request["companies"]:
                with env.engine.begin() as connection:
                    connection.execute(
                        text("SELECT id FROM workspaces WHERE id=:wid FOR UPDATE NOWAIT"),
                        {"wid": UUID(source["workspace_id"])},
                    )
            response = env.client.put(
                f"/workspaces/{wid}/datasets/{did}/access-policy",
                headers=owner,
                json={"expected_version": 0, "enabled": True, "grants": []},
            )
            assert response.status_code == 200, response.text
        return records

    monkeypatch.setattr(SQLConsolidationRepository, "uploads", uploads)
    response = env.client.get(path + "/options", headers=owner)
    assert changed and response.status_code == 404, response.text
    assert "filename" not in response.text and "companies" not in response.text


def test_disjoint_company_requests_share_one_atomic_private_worksheet_limit(
    integration, monkeypatch
):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from execplus.domain.ingestion import IngestionError
    from execplus.infrastructure.persistence.consolidations import SQLConsolidationRepository

    env = integration
    owner, actor, oid, path, first, _, _ = fixture(env)
    _, _, _, _, second, _, _ = fixture(env, (owner, actor, oid))
    assert {item["workspace_id"] for item in first["companies"]}.isdisjoint(
        item["workspace_id"] for item in second["companies"]
    )
    saved = create(env, owner, path, first)
    with env.engine.begin() as connection:
        row = dict(connection.execute(select(s.consolidation_runs)).mappings().one())
        connection.execute(
            s.consolidation_runs.insert(), [{**row, "id": uuid4()} for _ in range(48)]
        )
    service = env.runtime.consolidations
    check = service._check
    add = SQLConsolidationRepository.add_consolidation_run
    ready = Barrier(2)

    def checked(*args, **kwargs):
        result = check(*args, **kwargs)
        if len(args[3]) == 2 and kwargs.get("require_current"):
            ready.wait(timeout=10)
        return result

    def delayed_add(repo, value):
        time.sleep(0.3)
        return add(repo, value)

    def run_one(request):
        try:
            return asyncio.run(service.create(actor, UUID(oid), request))
        except IngestionError as exc:
            return exc.code

    monkeypatch.setattr(service, "_check", checked)
    monkeypatch.setattr(SQLConsolidationRepository, "add_consolidation_run", delayed_add)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run_one, [first, second]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "consolidation_limit" in results
    with env.engine.connect() as connection:
        records = connection.execute(select(s.consolidation_runs)).mappings().all()
    assert len(records) == 50
    assert (
        next(record["result"] for record in records if str(record["id"]) == saved["run"]["id"])
        == saved["run"]["result"]
    )
