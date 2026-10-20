"""Use case: Keeps the synthetic recovery runner bounded and isolated.

What it does: Rejects existing targets, corrupt or unsafe archives, symlinks and
overwritten evidence before the operator runner mutates any target.
"""

import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    spec = importlib.util.spec_from_file_location(
        "local_recovery", SCRIPTS / "rehearse_local_recovery.py"
    )
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
finally:
    sys.path.remove(str(SCRIPTS))


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:") as stream:
        for name, value, kind in entries:
            item = tarfile.TarInfo(name)
            item.size = len(value)
            item.type = kind
            if kind == tarfile.SYMTYPE:
                item.linkname = "/outside"
            stream.addfile(item, io.BytesIO(value))
    return output.getvalue()


def entry(key="workspace/source.csv", body=b"revenue\n10\n"):
    return {"key": key, "bytes": len(body), "sha256": recovery.digest(body)}


def test_local_recovery_checks_complete_object_archive_without_extracting():
    body = b"revenue\n10\n"
    value = archive([("workspace/source.csv", body, tarfile.REGTYPE)])
    assert recovery.unpack_objects(value, [entry()]) == {"workspace/source.csv": body}


@pytest.mark.parametrize(
    "name", ["../source", "/absolute", "dir/../source", "dir//source", "dir\\source"]
)
def test_local_recovery_rejects_unsafe_object_names_even_in_manifest(name):
    body = b"revenue\n10\n"
    value = archive([(name, body, tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="Unsafe"):
        recovery.unpack_objects(value, [entry(name)])


@pytest.mark.parametrize("mutation", ["link", "duplicate", "missing", "extra", "corrupt", "size"])
def test_local_recovery_rejects_incomplete_or_corrupt_objects(mutation):
    body = b"revenue\n10\n"
    rows = [("workspace/source.csv", body, tarfile.REGTYPE)]
    expected = [entry()]
    if mutation == "link":
        rows[0] = ("workspace/source.csv", body, tarfile.SYMTYPE)
    elif mutation == "duplicate":
        rows += rows
    elif mutation == "missing":
        rows = []
    elif mutation == "extra":
        rows += [("other", b"x", tarfile.REGTYPE)]
    elif mutation == "corrupt":
        expected[0]["sha256"] = "0" * 64
    else:
        expected[0]["bytes"] += 1
    with pytest.raises(ValueError):
        recovery.unpack_objects(archive(rows), expected)


def test_local_recovery_archive_limits_and_duplicate_manifest(monkeypatch):
    expected = entry()
    value = archive([("workspace/source.csv", b"revenue\n10\n", tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="Duplicate"):
        recovery.unpack_objects(value, [expected, expected])
    monkeypatch.setattr(recovery, "MAX_BYTES", 2)
    with pytest.raises(ValueError, match="bound"):
        recovery.unpack_objects(value, [expected])


def test_local_recovery_checks_dump_hash_length_and_symlink(tmp_path):
    target = tmp_path / "dump"
    body = b"fictional dump"
    target.write_bytes(body)
    metadata = {"bytes": len(body), "sha256": recovery.digest(body)}
    assert recovery.checked_bytes(target, metadata) == body
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        recovery.checked_bytes(target, metadata)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="linked"):
        recovery.checked_bytes(link, metadata)


class Database:
    def __init__(self, existing):
        self.existing, self.statements = existing, []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return self

    def fetchone(self):
        return (1,) if self.existing else None


@pytest.mark.parametrize(
    "name", ["execplus", "production", "execplus_restore_0123456789ab;DROP", "../target"]
)
def test_local_recovery_rejects_nongenerated_database_names(name):
    connection = Database(False)
    with pytest.raises(ValueError, match="generated"):
        recovery.create_empty_database(connection, name)
    assert not connection.statements


def test_local_recovery_refuses_existing_database_even_if_empty():
    connection = Database(True)
    with pytest.raises(ValueError, match="already exists"):
        recovery.create_empty_database(connection, "execplus_restore_0123456789ab")
    assert len(connection.statements) == 1
    fresh = Database(False)
    recovery.create_empty_database(fresh, "execplus_restore_0123456789ab")
    assert len(fresh.statements) == 2


def test_local_recovery_refuses_existing_bucket_and_evidence(tmp_path):
    name = "execplus-restore-0123456789ab"

    class Bucket:
        def list_buckets(self):
            return {"Buckets": [{"Name": name}]}

        def create_bucket(self, **kwargs):
            pytest.fail("Existing bucket must never be reused")

    with pytest.raises(ValueError, match="already exists"):
        recovery.create_empty_bucket(Bucket(), name)
    with pytest.raises(ValueError, match="new output"):
        recovery.rehearse(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_local_recovery_settings_disable_models_and_select_readonly_target():
    settings = recovery.settings_for(
        {"pg_port": 25432, "object_port": 29000}, "execplus_restore_0123456789ab", readonly=True
    )
    assert "127.0.0.1:25432/execplus_restore_0123456789ab" in settings.database_url
    assert "default_transaction_read_only" in settings.database_url
    assert settings.object_store_bucket == "execplus-restore-0123456789ab"
    assert settings.llm_mode == settings.email_mode == settings.vector_mode == "disabled"
    assert settings.llm_selection_model == settings.llm_api_key == ""
    assert not settings.webhook_destinations
