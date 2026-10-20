"""Use case: Rehearses recovery using newly generated fictional data only.

What it does: Creates cached-image disposable PostgreSQL/object-store containers,
seeds a synthetic workflow, checks a bounded backup, restores fresh empty targets,
then reuses the read-only recovery verifier. Never accepts an existing backup,
database URL, bucket, credentials, or deployment directory.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

import boto3
import psycopg
from alembic import command
from alembic.config import Config
from create_synthetic_workflow_kit import VERSION, artifacts
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from verify_recovery_snapshot import fingerprints, verify

from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.main import create_app

ROOT = Path(__file__).resolve().parents[1]
MAX_OBJECTS = 100
MAX_BYTES = 32 * 1024 * 1024
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
MINIO_IMAGE = "minio/minio:RELEASE.2023-03-13T19-46-17Z"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def checked_bytes(path: Path, expected: dict[str, Any]) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Backup member is missing, linked or above the rehearsal bound.")
    value = path.read_bytes()
    if len(value) != expected["bytes"] or digest(value) != expected["sha256"]:
        raise ValueError("Backup checksum or length differs from the retained manifest.")
    return value


def unpack_objects(value: bytes, expected: list[dict[str, Any]]) -> dict[str, bytes]:
    """Validate the whole archive before writing anything; never extract onto disk."""
    if len(value) > MAX_BYTES or len(expected) > MAX_OBJECTS:
        raise ValueError("Object archive exceeds the rehearsal bound.")
    wanted = {item["key"]: item for item in expected}
    if len(wanted) != len(expected):
        raise ValueError("Duplicate object manifest key.")
    found: dict[str, bytes] = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(value), mode="r:") as archive:
        for item in archive:
            key = item.name
            if (
                not item.isfile()
                or key not in wanted
                or key in found
                or "\\" in key
                or PurePosixPath(key).is_absolute()
                or any(part in {"", ".", ".."} for part in key.split("/"))
                or item.size != wanted[key]["bytes"]
                or item.size < 0
            ):
                raise ValueError("Unsafe, duplicate or undeclared object archive entry.")
            total += item.size
            if len(found) >= MAX_OBJECTS or total > MAX_BYTES:
                raise ValueError("Object archive exceeds the rehearsal bound.")
            stream = archive.extractfile(item)
            if stream is None:
                raise ValueError("Object entry cannot be read.")
            body = stream.read(MAX_BYTES + 1)
            if len(body) != item.size or digest(body) != wanted[key]["sha256"]:
                raise ValueError("Object checksum differs from the retained manifest.")
            found[key] = body
    if set(found) != set(wanted):
        raise ValueError("Object archive is incomplete.")
    return found


def docker(*arguments: str, content: bytes | None = None) -> bytes:
    return subprocess.run(
        ["docker", *arguments], input=content, capture_output=True, check=True, timeout=120
    ).stdout


@contextmanager
def disposable_services() -> Iterator[dict[str, Any]]:
    """Only cached images; cleanup uses the exact IDs returned by our own creation."""
    images = {
        name: docker("image", "inspect", name, "--format", "{{.Id}}").decode().strip()
        for name in (POSTGRES_IMAGE, MINIO_IMAGE)
    }
    label = "execplus-synthetic-recovery-" + uuid4().hex[:12]
    network = docker("network", "create", "--label", "execplus.rehearsal=" + label, label)
    containers: list[str] = []
    try:
        for image, port, extra, command_args in (
            (
                POSTGRES_IMAGE,
                "5432",
                [
                    "--tmpfs",
                    "/var/lib/postgresql/data:rw,size=512m",
                    "-e",
                    "POSTGRES_USER=execplus",
                    "-e",
                    "POSTGRES_PASSWORD=execplus",
                ],
                [],
            ),
            (
                MINIO_IMAGE,
                "9000",
                [
                    "--tmpfs",
                    "/data:rw,size=128m",
                    "-e",
                    "MINIO_ROOT_USER=execplus",
                    "-e",
                    "MINIO_ROOT_PASSWORD=change-me",
                ],
                ["server", "/data"],
            ),
        ):
            identifier = (
                docker(
                    "run",
                    "-d",
                    "--pull=never",
                    "--label",
                    "execplus.rehearsal=" + label,
                    "--network",
                    label,
                    "--memory=768m",
                    "--cpus=2",
                    "-p",
                    "127.0.0.1::" + port,
                    *extra,
                    image,
                    *command_args,
                )
                .decode()
                .strip()
            )
            containers.append(identifier)
        bindings = [
            json.loads(docker("inspect", item))[0]["NetworkSettings"]["Ports"]
            for item in containers
        ]
        pg_port = int(bindings[0]["5432/tcp"][0]["HostPort"])
        object_port = int(bindings[1]["9000/tcp"][0]["HostPort"])
        dsn = f"postgresql://execplus:execplus@127.0.0.1:{pg_port}/postgres"
        client = boto3.client(
            "s3",
            endpoint_url=f"http://127.0.0.1:{object_port}",
            aws_access_key_id="execplus",
            aws_secret_access_key="change-me",
            region_name="us-east-1",
        )
        for attempt in range(60):
            try:
                with psycopg.connect(dsn, connect_timeout=1):
                    pass
                client.list_buckets()
                break
            except Exception:
                if attempt == 59:
                    raise RuntimeError("Disposable local services did not become ready.") from None
                time.sleep(0.25)
        yield {
            "postgres": containers[0],
            "dsn": dsn,
            "pg_port": pg_port,
            "object_port": object_port,
            "client": client,
            "images": images,
        }
    finally:
        for identifier in reversed(containers):
            docker("rm", "-f", identifier)
        docker("network", "rm", network.decode().strip())


def create_empty_database(connection: Any, name: str) -> None:
    if not re.fullmatch(r"execplus_(fixture|restore)_[a-f0-9]{12}", name):
        raise ValueError("Only generated synthetic fixture/restore database names are allowed.")
    if connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
        raise ValueError("The target database already exists; existing targets are never reused.")
    connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def create_empty_bucket(client: Any, bucket: str) -> None:
    if not re.fullmatch(r"execplus-(fixture|restore)-[a-f0-9]{12}", bucket):
        raise ValueError("Only generated synthetic buckets are allowed.")
    if bucket in {item["Name"] for item in client.list_buckets()["Buckets"]}:
        raise ValueError("The target bucket already exists; existing targets are never reused.")
    client.create_bucket(Bucket=bucket)


def settings_for(services: dict[str, Any], name: str, *, readonly: bool = False) -> Settings:
    url = make_url(f"postgresql+psycopg://execplus:execplus@127.0.0.1:{services['pg_port']}/{name}")
    if readonly:
        url = url.set(query={"options": "-c default_transaction_read_only=on"})
    settings_kwargs: dict[str, Any] = {"_env_file": None}
    return Settings(
        **settings_kwargs,
        environment="test",
        database_url=url.render_as_string(hide_password=False),
        object_store_endpoint=f"http://127.0.0.1:{services['object_port']}",
        object_store_bucket=name.replace("_", "-"),
        object_store_access_key="execplus",
        object_store_secret_key="change-me",
        llm_mode="disabled",
        llm_base_url="http://127.0.0.1:9",
        llm_api_key="",
        llm_small_model="",
        llm_large_model="",
        llm_selection_base_url="",
        llm_selection_model="",
        llm_selection_api_key="",
        email_mode="disabled",
        smtp_password="",
        vector_mode="disabled",
        webhook_master_secret="",
        webhook_destinations={},
    )


def seed(settings: Settings) -> dict[str, Any]:
    """Use the ordinary authorized API; explicit fictional meanings are confirmed."""
    runtime = build_runtime(settings)
    try:
        if not isinstance(runtime.identity, LocalSessionIdentity):
            raise ValueError("Recovery fixture requires local identity.")
        token = runtime.identity.provision("recovery-operator@example.test")
        operator_headers = {"Authorization": "Bearer " + token}
        runtime.operations.change_staff("recovery-operator@example.test", "admin")
        kit = artifacts()
        manifest = json.loads(kit["manifest.json"])
        results = {}
        with TestClient(create_app(settings, runtime)) as client:
            signup = client.post(
                "/auth/register",
                json={
                    "email": "recovery-native@example.test",
                    "password": "Fictional local recovery password 47",
                    "display_name": "Fictional Recovery Person",
                    "workspace_name": "Fictional recovery",
                },
            )
            if signup.status_code != 202:
                raise RuntimeError("Synthetic native registration failed.")
            login = client.post(
                "/auth/login",
                json={
                    "email": "recovery-native@example.test",
                    "password": "Fictional local recovery password 47",
                },
            )
            if login.status_code != 200:
                raise RuntimeError("Synthetic native login failed.")
            headers = {"Authorization": "Bearer " + login.json()["token"]}

            def request(method: str, path: str, **kwargs: Any) -> Any:
                response = client.request(method, path, headers=headers, **kwargs)
                if response.status_code not in {200, 201, 204}:
                    raise RuntimeError(
                        f"Synthetic seed failed: {method} {path}: {response.status_code}"
                    )
                return response.json() if response.content else None

            wid = request("GET", "/workspaces")[0]["id"]
            plan = request("GET", f"/workspaces/{wid}/plan")
            if plan["assignment"]["plan_key"] != "demo":
                raise ValueError("Synthetic native workspace did not receive its local Demo plan.")
            request(
                "PUT",
                f"/workspaces/{wid}/onboarding-progress",
                json={
                    "expected_version": 0,
                    "active_step": "meaning",
                    "skipped_steps": [],
                    "paused": True,
                    "finished": False,
                },
            )
            policy = client.put(
                "/admin/incidents/thresholds/exports",
                headers=operator_headers,
                json={
                    "expected_version": 0,
                    "enabled": True,
                    "window_minutes": 5,
                    "minimum_requests": 10,
                    "minimum_failures": 3,
                    "failure_basis_points": 500,
                },
            )
            if policy.status_code != 200:
                raise RuntimeError("Synthetic staff alert policy failed.")
            for filename, metric, expected in (
                ("finance-daily.csv", "revenue", "12714"),
                ("sales-orders.csv", "revenue", "2340"),
                ("hr-workforce.csv", "salary", "30900"),
            ):
                entry = next(item for item in manifest["datasets"] if item["file"] == filename)
                dataset = request("POST", f"/workspaces/{wid}/datasets", json={"name": filename})
                path = f"/workspaces/{wid}/datasets/{dataset['id']}/uploads"
                response = client.post(
                    path + "?filename=" + filename,
                    content=kit[filename],
                    headers={**headers, "Content-Type": "text/csv"},
                )
                if response.status_code != 201:
                    raise RuntimeError(
                        "Synthetic source upload failed: " + str(response.status_code)
                    )
                root = path + "/" + response.json()["id"]
                current = request("GET", root + "/understanding")
                definition = current["definition"]
                definition["domain"] = entry["domain"]
                definition["grain"] = "record"
                definition["description"] = (
                    "Explicitly fictional recovery fixture: " + entry["one_row"]
                )
                for column in definition["columns"]:
                    if column["name"] in entry["units"]:
                        column["unit"] = entry["units"][column["name"]]
                        column["unit_column"] = ""
                request(
                    "POST",
                    root + "/understanding",
                    json={
                        "revision_id": current["revision_id"],
                        "expected_version": current["version"],
                        "state": "confirmed",
                        "definition": definition,
                    },
                )
                result = request(
                    "POST",
                    root + "/query",
                    json={
                        "metric": metric,
                        "aggregation": "sum",
                        "group_by": [],
                        "filters": [],
                    },
                )
                actual = Decimal(str(result["rows"][0][0]))
                if actual != Decimal(expected):
                    raise ValueError(
                        "Synthetic source calculation disagrees with independent oracle."
                    )
                results[filename] = {"metric": metric, "expected": expected, "actual": str(actual)}
            # Flush actual local HTTP observations; no made-up incident or alert is inserted.
            if not asyncio.run(runtime.incidents.collect_once()):
                raise RuntimeError("Synthetic operational observations did not persist.")
        return {
            "fixture_version": VERSION,
            "calculations": results,
            "native_account": True,
            "local_demo_plan": True,
            "private_onboarding_progress": True,
            "staff_alert_policy": True,
            "actual_local_http_metrics_flushed": True,
        }
    finally:
        runtime.engine.dispose()


def backup_objects(client: Any, bucket: str) -> tuple[bytes, list[dict[str, Any]]]:
    items = client.list_objects_v2(Bucket=bucket, MaxKeys=MAX_OBJECTS + 1)
    if items.get("IsTruncated") or len(items.get("Contents", [])) > MAX_OBJECTS:
        raise ValueError("Too many synthetic objects for this rehearsal.")
    output, entries, total = io.BytesIO(), [], 0
    with tarfile.open(fileobj=output, mode="w:") as archive:
        for item in sorted(items.get("Contents", []), key=lambda row: row["Key"]):
            total += item["Size"]
            if total > MAX_BYTES:
                raise ValueError("Synthetic object bytes exceed the rehearsal bound.")
            body = client.get_object(Bucket=bucket, Key=item["Key"])["Body"].read(MAX_BYTES + 1)
            if len(body) != item["Size"]:
                raise ValueError("Synthetic object length changed during backup.")
            metadata = tarfile.TarInfo(item["Key"])
            metadata.size = len(body)
            archive.addfile(metadata, io.BytesIO(body))
            entries.append({"key": item["Key"], "bytes": len(body), "sha256": digest(body)})
    return output.getvalue(), entries


def rehearse(output: Path) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new output directory; previous evidence is never overwritten.")
    output.mkdir(parents=True, mode=0o700)
    report: dict[str, Any] = {"scope": "synthetic-local-recovery", "passed": False}
    started = time.perf_counter()
    try:
        with disposable_services() as services:
            suffix = uuid4().hex[:12]
            source, target = "execplus_fixture_" + suffix, "execplus_restore_" + suffix
            with psycopg.connect(services["dsn"], autocommit=True) as connection:
                create_empty_database(connection, source)
                create_empty_database(connection, target)
            for name in (source, target):
                create_empty_bucket(services["client"], name.replace("_", "-"))
            source_settings = settings_for(services, source)
            engine = create_engine(source_settings.database_url)
            try:
                config = Config(str(ROOT / "alembic.ini"))
                config.set_main_option("script_location", str(ROOT / "migrations"))
                with engine.begin() as connection:
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                report["seed"] = seed(source_settings)
                before = fingerprints(engine)
                with engine.connect() as connection:
                    version = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                dump = docker(
                    "exec", services["postgres"], "pg_dump", "-Fc", "-U", "execplus", "-d", source
                )
                if len(dump) > MAX_BYTES:
                    raise ValueError("Synthetic database dump exceeds the rehearsal bound.")
                archive, objects = backup_objects(
                    services["client"], source_settings.object_store_bucket
                )
                manifest = {
                    "format": "execplus-synthetic-backup-v1",
                    "synthetic_only": True,
                    "schema_version": version,
                    "fixture_version": VERSION,
                    "images": services["images"],
                    "objects": objects,
                    "source_tables": before,
                    "files": {
                        name: {"bytes": len(value), "sha256": digest(value)}
                        for name, value in (
                            ("database.dump", dump),
                            ("objects.tar", archive),
                        )
                    },
                    "code_sha256": {
                        str(path.relative_to(ROOT)): digest(path.read_bytes())
                        for directory in (
                            ROOT / "apps/api/src",
                            ROOT / "migrations",
                            ROOT / "scripts",
                        )
                        for path in sorted(directory.rglob("*.py"))
                    },
                }
                for name, value in (("database.dump", dump), ("objects.tar", archive)):
                    (output / name).write_bytes(value)
                manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
                (output / "manifest.json").write_bytes(manifest_bytes)
                restored_objects = unpack_objects(
                    checked_bytes(output / "objects.tar", manifest["files"]["objects.tar"]), objects
                )
                checked_dump = checked_bytes(
                    output / "database.dump", manifest["files"]["database.dump"]
                )
                # Fresh target only; no --clean, deletion, overwritten DB or existing bucket.
                docker(
                    "exec",
                    "-i",
                    services["postgres"],
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "-U",
                    "execplus",
                    "-d",
                    target,
                    content=checked_dump,
                )
                for key, body in restored_objects.items():
                    services["client"].put_object(
                        Bucket=target.replace("_", "-"), Key=key, Body=body
                    )
                verified = asyncio.run(
                    verify(settings_for(services, target, readonly=True), version, 20)
                )
                if verified["tables"] != before or fingerprints(engine) != before:
                    raise ValueError("Source/restore table fingerprints do not agree.")
                if verified["receipts"]["replayed"] < 3:
                    raise ValueError("Representative synthetic receipt replay was incomplete.")
                report.update(
                    {
                        "passed": True,
                        "manifest_sha256": digest(manifest_bytes),
                        "schema_version": version,
                        "verified_objects": verified["verified_objects"],
                        "receipts": verified["receipts"],
                        "tables_equal": True,
                        "source_unchanged": True,
                        "restored_database_read_only": True,
                        "table_count": len(before),
                    }
                )
            finally:
                engine.dispose()
    except BaseException as error:
        report["failure_type"] = type(error).__name__
        raise
    finally:
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        report["external_gates"] = [
            "off-server custody",
            "production restore",
            "retention policy",
            "formal RTO/RPO",
        ]
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # This isolated CLI never inherits application/provider configuration.
    for key in tuple(os.environ):
        if key.startswith(("EXECPLUS_", "AWS_", "OPENAI_", "ANTHROPIC_", "DEEPSEEK_")):
            del os.environ[key]
    report = rehearse(args.output.resolve())
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "output": str(args.output),
                "elapsed_seconds": report["elapsed_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
