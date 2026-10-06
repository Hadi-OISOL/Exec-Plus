"""Use case: Verifies private demo provisioning and preservation of deployment credentials.

What it does: Exercises real eight-seat isolation and prevents destructive reinitialization.
"""

import importlib
import json
import stat
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.analytics import DashboardCard, DashboardSummary
from execplus.application.services.summaries import SummaryService
from execplus.domain.errors import UnverifiedAnswerError
from execplus.domain.models import CalculationLineage, QueryResult


@pytest.fixture
def demo_provisioner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("provision_demo")


@pytest.mark.asyncio
async def test_eight_demo_users_share_fictional_data_without_duplicate_seeding(
    integration, demo_provisioner, tmp_path
):
    runtime = integration.runtime
    first = await demo_provisioner.provision(runtime)
    second = await demo_provisioner.provision(runtime)
    assert first["workspace_id"] == second["workspace_id"]
    assert first["upload_id"] == second["upload_id"]
    assert len({item["token"] for item in second["accounts"]}) == 8
    wid = second["workspace_id"]
    did = second["dataset_id"]
    for account in second["accounts"]:
        headers = {"Authorization": f"Bearer {account['token']}"}
        assert (
            len(integration.client.get(f"/workspaces/{wid}/members", headers=headers).json()) == 8
        )
        assert (
            len(integration.client.get(f"/workspaces/{wid}/datasets", headers=headers).json()) == 5
        )
        documents = integration.client.get(
            f"/workspaces/{wid}/datasets/{did}/documents", headers=headers
        )
        assert documents.status_code == 200 and len(documents.json()) == 6
    outsider = runtime.identity.provision("unrelated@example.test")
    assert (
        integration.client.get(
            f"/workspaces/{wid}/datasets", headers={"Authorization": f"Bearer {outsider}"}
        ).status_code
        == 404
    )
    output = tmp_path / "sessions.json"
    demo_provisioner.save_private(output, first)
    demo_provisioner.save_private(output, second)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert json.loads(output.read_text()) == second


def test_vps_initialization_preserves_secrets_and_refuses_partial_or_existing_data(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "deploy/vps"))
    initialize = importlib.import_module("initialize").initialize
    root = tmp_path / "demo"
    initialize(root)
    paths = list((root / "secrets").iterdir())
    originals = {path.name: path.read_bytes() for path in paths}
    initialize(root)
    assert {path.name: path.read_bytes() for path in paths} == originals
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in paths)
    assert "PASSWORD=" not in capsys.readouterr().out
    (root / "secrets/app.env").unlink()
    with pytest.raises(RuntimeError, match="Incomplete"):
        initialize(root)
    existing = tmp_path / "existing"
    (existing / "postgres").mkdir(parents=True)
    (existing / "postgres/PG_VERSION").write_text("16")
    with pytest.raises(RuntimeError, match="original credentials"):
        initialize(existing)


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", [["E1"], ["E2", "E1"], ["E3"], ["E1", "E1"]])
async def test_summary_aliases_preserve_real_receipt_ids_and_reject_invalid_selections(selection):
    ids = [uuid4(), uuid4()]
    cards = tuple(
        DashboardCard(
            metric,
            QueryResult(qid, ("value",), ((Decimal(value),),), 4),
            CalculationLineage(qid, uuid4(), uuid4(), "Demo", 4, metric, "sum", (), (), "SELECT"),
        )
        for qid, metric, value in zip(ids, ("revenue", "cost"), ("10000", "2800"), strict=True)
    )

    class Model:
        async def complete(self, request):
            bank = json.loads(request.messages[-1].content)
            assert set(bank) == {"E1", "E2"}
            assert all(str(qid) not in request.messages[-1].content for qid in ids)
            return ModelResponse(json.dumps({"evidence_ids": selection}), "qwen-test", "local")

    service = SummaryService(Model())
    summary = DashboardSummary(cards, None, None)
    if selection in (["E3"], ["E1", "E1"]):
        with pytest.raises(UnverifiedAnswerError):
            await service.compose(summary)
    else:
        narrative = await service.compose(summary)
        assert narrative.evidence_ids == tuple(str(ids[int(alias[1:]) - 1]) for alias in selection)
        assert "10000" in narrative.text and narrative.model_route == "local:qwen-test"
