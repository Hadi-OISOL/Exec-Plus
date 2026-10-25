"""Use case: Proves profile-v5 uploads are queried from typed Parquet end to end.

What it does: Uploads a 200,000-row CSV through the HTTP API with columnar ingest enabled,
checks the stored manifest, exact grouped sums, receipt replay and legacy uploads beside it.
"""

from decimal import Decimal

from test_workspace_integration import dataset, identity, upload, workspace

from execplus.infrastructure.columnar.converter import DuckDBColumnarConverter
from execplus.infrastructure.columnar.store import S3ColumnarStore


def enable_columnar(env, tmp_path):
    storage = env.runtime.service.storage
    store = S3ColumnarStore(storage.client, env.bucket, tmp_path / "cache", 1024**3)
    env.runtime.service.columnar = store
    env.runtime.service.converter = DuckDBColumnarConverter(memory_limit_mb=512, threads=2)
    env.runtime.analytics.columnar = store
    return store


def big_csv(rows):
    lines = ["region,amount,units"]
    expected: dict[str, Decimal] = {}
    for index in range(rows):
        region = ("North", "South", "East")[index % 3]
        amount = f"{index % 997}.{index % 100:02d}"
        expected[region] = expected.get(region, Decimal(0)) + Decimal(amount)
        lines.append(f"{region},{amount},{index % 7}")
    return ("\n".join(lines) + "\n").encode(), expected


def test_profile_v5_upload_queries_parquet_and_replays(integration, tmp_path):
    env = integration
    owner, _ = identity(env, "columnar@example.test")
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    legacy = upload(env, owner, wid, did, b"region,amount\nNorth,0.10\nNorth,0.20\n")
    assert legacy.status_code == 201, legacy.text
    store = enable_columnar(env, tmp_path)
    content, expected = big_csv(200_000)
    response = upload(env, owner, wid, did, content)
    assert response.status_code == 201, response.text
    assert response.json()["row_count"] == 200_000
    root = f"/workspaces/{wid}/datasets/{did}/uploads/{response.json()['id']}"
    profile = env.client.get(root + "/profile", headers=owner).json()
    assert profile["algorithm"] == "profile-v5"
    manifest = profile["profile"]["columnar"]
    assert profile["output_checksum"] == manifest["sha256"]
    assert manifest["rows"] == 200_000 and manifest["errors"] == {}
    assert [column["type"] for column in profile["profile"]["columns"]] == [
        "text",
        "decimal",
        "integer",
    ]
    query = env.client.post(
        root + "/query",
        headers=owner,
        json={"metric": "amount", "aggregation": "sum", "group_by": ["region"]},
    )
    assert query.status_code == 200, query.text
    assert {row[0]: Decimal(row[1]) for row in query.json()["rows"]} == expected
    assert query.json()["records_analyzed"] == 200_000
    for cached in (tmp_path / "cache").glob("*.parquet"):
        cached.unlink()
    replay = env.client.post(
        f"/workspaces/{wid}/queries/{query.json()['lineage']['query_id']}/replay", headers=owner
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["rows"] == query.json()["rows"]
    legacy_root = f"/workspaces/{wid}/datasets/{did}/uploads/{legacy.json()['id']}"
    assert env.client.get(legacy_root + "/profile", headers=owner).json()["algorithm"] == (
        "profile-v4"
    )
    legacy_query = env.client.post(
        legacy_root + "/query", headers=owner, json={"metric": "amount", "aggregation": "sum"}
    )
    assert legacy_query.json()["rows"] == [["0.300000000000"]]
    assert store.client.head_object(Bucket=env.bucket, Key=manifest["key"])
