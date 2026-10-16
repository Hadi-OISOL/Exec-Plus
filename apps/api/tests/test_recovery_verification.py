"""Use case: Keeps recovery rehearsals isolated and detects incomplete restored data.

What it does: Exercises restored-source/revision/receipt checks and rejects unsafe
targets and archive entries before any recovery container is created.
"""

import asyncio
import hashlib
import importlib.util
import io
import os
import subprocess
import tarfile
from pathlib import Path

import pytest
from sqlalchemy import select, update

from execplus.config import Settings
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask, setup

spec = importlib.util.spec_from_file_location("recovery", "scripts/verify_recovery_snapshot.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


@pytest.mark.parametrize(
    "name",
    [
        "execplus",
        "live",
        "execplus_restore_x",
        "../execplus",
        "execplus_restore_0123456789ab;echo bad",
    ],
)
def test_recovery_refuses_nonisolated_targets(name):
    with pytest.raises(ValueError, match="isolated"):
        recovery.isolated_settings(Settings(_env_file=None), name)


def test_recovery_settings_disable_model_and_live_database_connections():
    original = Settings(_env_file=None)
    value = recovery.isolated_settings(original, "execplus_restore_0123456789ab")
    assert value.object_store_endpoint == "http://execplus-restore-0123456789ab-objects:9000"
    assert (
        "execplus_restore_0123456789ab_db:5432/execplus_restore_0123456789ab" in value.database_url
    )
    assert "default_transaction_read_only" in value.database_url
    assert value.llm_mode == "disabled" and not value.llm_selection_model
    assert original.database_url != value.database_url


def test_recovered_objects_and_exact_receipts_verify_without_database_changes(integration):
    env = integration
    model = ScriptedModel(
        {"kind": "numerical", "plan": {"metric": "attock_erp", "aggregation": "sum"}}
    )
    owner, _, _, path, _ = setup(env, model)
    assert ask(env, owner, path, "What is total attock_erp?")["answer"]["value"] == 5
    before = recovery.fingerprints(env.engine)
    counts = recovery.verify_objects(env.runtime)
    receipts = asyncio.run(recovery.verify_receipts(env.runtime, 20))
    assert counts["uploads"] == counts["revisions"] == 1
    assert receipts == {
        "eligible_receipts": 1,
        "replayed": 1,
        "operations": {"sum": 1},
        "permission_denials_verified": 0,
        "candidates_checked": 1,
        "candidate_check_limit": 100,
    }
    assert recovery.fingerprints(env.engine) == before
    assert "agent_memories" in before


def test_recovery_checks_revoked_receipts_without_restoring_access(integration):
    from test_dataset_access import fixture, query

    env = integration
    owner, _, member, _, _, _, _, root, policy_path, policy = fixture(env)
    assert query(env, owner, root).status_code == 200
    restricted = query(env, member, root)
    assert restricted.status_code == 200
    updated = {**policy, "expected_version": 1, "grants": policy["grants"][:1]}
    assert env.client.put(policy_path, headers=owner, json=updated).status_code == 200
    assert query(env, owner, root).status_code == 200
    before = recovery.fingerprints(env.engine)
    recovered = asyncio.run(recovery.verify_receipts(env.runtime, 20))
    assert recovered["replayed"] == 1
    assert recovered["permission_denials_verified"] == 2
    assert recovered["candidates_checked"] == 3
    assert recovery.fingerprints(env.engine) == before


def test_recovery_still_fails_corrupted_authorized_receipt(integration):
    from test_dataset_access import fixture, query

    env = integration
    _, _, member, _, _, _, _, root, _, _ = fixture(env)
    assert query(env, member, root).status_code == 200
    with env.engine.begin() as connection:
        receipt = connection.execute(select(s.query_executions.c.receipt)).scalar_one()
        receipt["sources"][0]["output_checksum"] = "0" * 64
        connection.execute(update(s.query_executions).values(receipt=receipt))
    with pytest.raises(IngestionError) as failure:
        asyncio.run(recovery.verify_receipts(env.runtime, 20))
    assert failure.value.code == "lineage_mismatch"


@pytest.mark.parametrize("corruption", ["source", "revision"])
def test_recovery_detects_corrupted_original_or_reconstructed_revision(integration, corruption):
    env = integration
    setup(env)
    if corruption == "source":
        with env.engine.connect() as connection:
            upload = connection.execute(select(s.uploads)).mappings().one()
        env.runtime.service.storage.client.put_object(
            Bucket=env.bucket,
            Key=upload["storage_key"],
            Body=b"corrupted",
        )
    else:
        with env.engine.begin() as connection:
            connection.execute(update(s.revisions).values(output_checksum="0" * 64))
    with pytest.raises(IngestionError) as failure:
        recovery.verify_objects(env.runtime)
    assert failure.value.code in {"storage_integrity", "lineage_mismatch"}


@pytest.mark.parametrize("entry", ["../../outside", "/outside", "link"])
def test_recovery_rejects_traversal_and_links_before_creating_containers(tmp_path, entry):
    root = tmp_path / "deployment"
    backup = root / "backups/20261016T000000Z"
    backup.mkdir(parents=True)
    (root / "ops").mkdir()
    (backup / "database.dump").write_bytes(b"fixture")
    with tarfile.open(backup / "objects.tar.gz", "w:gz") as archive:
        member = tarfile.TarInfo(entry)
        if entry == "link":
            member.type, member.linkname = tarfile.SYMTYPE, "/outside"
            archive.addfile(member)
        else:
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
    (backup / "SHA256SUMS").write_text(
        "".join(
            hashlib.sha256((backup / name).read_bytes()).hexdigest() + "  " + name + "\n"
            for name in ("database.dump", "objects.tar.gz")
        )
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    for name, body in {
        "id": "echo 0",
        "docker": 'printf \'%s\\n\' "$*" >> "$TRACE_PATH"; exit 0',
    }.items():
        path = binary / name
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o700)
    script = tmp_path / "drill.sh"
    script.write_text(
        Path("deploy/vps/restore-drill.sh")
        .read_text()
        .replace("root=/sdb-disk/OISOL_ExecPLUS", f"root='{root}'")
    )
    trace = tmp_path / "trace"
    result = subprocess.run(
        ["bash", str(script), "20261016T000000Z", "919dd0a", "0018"],
        env={**os.environ, "PATH": f"{binary}:{os.environ['PATH']}", "TRACE_PATH": str(trace)},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "unsupported entry" in result.stderr
    assert trace.read_text().splitlines() == ["image inspect oisol-execplus/api:candidate-919dd0a"]
    assert not (tmp_path / "outside").exists()
