"""Use case: Proves row-level features work on big profile-v5 (Parquet) uploads.

What it does: Uploads synthetic 300,000-row CSVs with columnar ingest on and checks data
understanding, guidance, patterns and cleaning, including sampled-versus-exact labels.
"""

import asyncio
import time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from execplus.application.services.patterns import PatternService
from execplus.infrastructure.statistics.scipy_patterns import ScipyPatternStatistics
from test_columnar_integration import enable_columnar
from test_conversational_explorer import ScriptedModel, prepare
from test_understanding import confirm, context

ROWS = 300_000
REGIONS = ("North", "South", "East")


def region(index):
    return "north" if index % 997 == 0 else REGIONS[index % 3]


def amount(index):
    return Decimal(f"{(index % 3) * 100 + index % 50}.{index % 100:02d}")


def big_content(rows=ROWS):
    lines = ["region,channel,amount,units,note"]
    lines += [
        f"{region(index)},{('Web', 'Shop')[index % 2]},{amount(index)},{index % 7},"
        f" note {index % 5} "
        for index in range(rows)
    ]
    return ("\n".join(lines) + "\n").encode()


def exact_means():
    sums: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for index in range(ROWS):
        key = region(index)
        sums[key] = sums.get(key, Decimal(0)) + amount(index)
        counts[key] = counts.get(key, 0) + 1
    return {key: (sums[key] / counts[key]).quantize(Decimal("1e-12")) for key in sums}, counts


def timed(label, call):
    started = time.perf_counter()
    value = call()
    print(f"{label}: {time.perf_counter() - started:.2f}s")
    return value


def setup(env, tmp_path, content):
    enable_columnar(env, tmp_path)
    owner, wid, root = timed(
        "upload+ingest", lambda: prepare(env, ScriptedModel(), content=content)
    )
    return owner, wid, root


@pytest.fixture
def big(integration, tmp_path):
    owner, wid, root = setup(integration, tmp_path, big_content())
    return integration, owner, wid, root


def confirm_units(env, owner, root):
    current = context(env, owner, root)
    for column in current["definition"]["columns"]:
        if column["role"] == "metric":
            column["unit"] = "PKR"
    saved = timed("understanding save", lambda: confirm(env, owner, root, current))
    assert saved.status_code == 201, saved.text


def ask(env, owner, wid, root, question):
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    response = timed(
        question,
        lambda: env.client.post(
            f"/workspaces/{wid}/threads/{tid}/ask",
            headers=owner,
            json={"question": question, "request_id": str(uuid4())},
        ),
    )
    assert response.status_code == 200, response.text
    return response.json()["answer"]


def test_understanding_and_guidance_work_above_the_row_limit(big):
    env, owner, wid, root = big
    current = timed("understanding overview", lambda: context(env, owner, root))
    assert current["column_types"]["amount"] == "decimal"
    confirm_units(env, owner, root)
    assert ask(env, owner, wid, root, "what does region mean")["guidance"]["columns"] == ["region"]
    quality = ask(env, owner, wid, root, "explain region quality issues")["message"]
    assert "region: 'north' and 'North'" in quality or "region: 'North' and 'north'" in quality, (
        quality
    )
    orientation = ask(env, owner, wid, root, "help me with understanding my data")["message"]
    assert "300000 rows" in orientation


def test_patterns_use_exact_group_means_and_a_disclosed_sample(big):
    env, owner, wid, root = big
    confirm_units(env, owner, root)
    actor = env.runtime.identity.authenticate(owner["Authorization"].split()[1])
    did, uid = root.split("/")[4], root.split("/")[6]
    analytics = env.runtime.analytics
    service = PatternService(analytics.uow, analytics, ScipyPatternStatistics())

    def discover():
        return asyncio.run(service.discover(actor, UUID(wid), UUID(did), UUID(uid)))

    evidence = timed("patterns", discover)
    result = evidence["result"]
    assert result["coverage"]["source_rows"] == ROWS
    assert result["coverage"]["sample"]["sampled_rows"] == 10_000
    assert result["coverage"]["sample"]["exact_matching_rows"] == ROWS
    assert any("sample of 10,000 of 300,000 rows" in text for text in result["limitations"])
    findings = result["findings"] + result["exploratory"]
    groups = [
        item
        for item in findings
        if item["type"] == "group_difference" and item["columns"] == ["region", "amount"]
    ]
    assert groups and groups[0]["strength"] == "strong"
    means, counts = exact_means()
    assert {point["x"]: Decimal(point["y"]) for point in groups[0]["chart"]["points"]} == means
    assert {point["x"]: point["count"] for point in groups[0]["chart"]["points"]} == counts
    assert groups[0]["support"] == ROWS
    assert any("are exact" in note for note in groups[0]["notes"])
    for item in findings:
        if item["type"] == "numeric_relationship":
            assert any("sample of 10,000 of 300,000 rows" in note for note in item["notes"])
        if item["type"] == "category_association":
            assert item["support"] == ROWS
    assert timed("pattern reopen", lambda: asyncio.run(service.reopen(actor, UUID(wid), evidence)))
    for key in ("query_id", "totals_query_id"):
        replay = env.client.post(f"/workspaces/{wid}/queries/{evidence[key]}/replay", headers=owner)
        assert replay.status_code == 200, replay.text
    again = discover()
    assert again["result"] == evidence["result"]
    grouped = timed(
        "compare groups",
        lambda: asyncio.run(
            service.discover(
                actor, UUID(wid), UUID(did), UUID(uid), ("amount", "units"), group_by="channel"
            )
        ),
    )
    assert grouped["result"]["coverage"]["source_rows"] == ROWS
    assert grouped["result"]["coverage"]["sample"]["sampled_rows"] == 10_000
    assert "sample of 10,000 of 300,000 rows" in grouped["result"]["limitations"][0]
    assert "totals_query_id" not in grouped
    assert asyncio.run(service.reopen(actor, UUID(wid), grouped)) == grouped


def test_cleaning_previews_a_sample_and_refuses_apply_above_the_budget(big):
    env, owner, _, root = big
    profile = env.client.get(root + "/profile", headers=owner).json()
    body = {"expected_revision_id": profile["id"], "trim": True, "drop_duplicates": True}
    preview = timed(
        "cleaning preview",
        lambda: env.client.post(root + "/cleaning/preview", headers=owner, json=body),
    )
    assert preview.status_code == 200, preview.text
    sample = preview.json()["sample"]
    assert sample["rows"] == 10_000 and sample["source_rows"] == ROWS
    assert "sample of 10,000 of 300,000 rows" in sample["label"]
    assert (
        preview.json()["revision"]["profile"]["row_count"] + preview.json()["removed_rows"]
        == 10_000
    )
    assert all(cell == cell.strip() for row in preview.json()["rows"] for cell in row)
    applied = env.client.post(root + "/cleaning/apply", headers=owner, json=body)
    assert applied.status_code == 422
    assert "up to 200,000 rows" in applied.json()["error"]["message"]
    assert env.client.get(root + "/profile", headers=owner).json()["id"] == profile["id"]


def test_cleaning_applies_to_full_columnar_files_within_the_query_budget(integration, tmp_path):
    env = integration
    owner, _, root = setup(env, tmp_path, big_content(150_000))
    profile = env.client.get(root + "/profile", headers=owner).json()
    body = {"expected_revision_id": profile["id"], "trim": True, "mapping": {"amount": "sales"}}
    preview = env.client.post(root + "/cleaning/preview", headers=owner, json=body)
    assert preview.status_code == 200, preview.text
    assert "sample" not in preview.json()
    applied = timed(
        "cleaning apply 150k",
        lambda: env.client.post(root + "/cleaning/apply", headers=owner, json=body),
    )
    assert applied.status_code == 201, applied.text
    assert applied.json()["revision"]["profile"]["row_count"] == 150_000
    query = env.client.post(
        root + "/query", headers=owner, json={"metric": "sales", "aggregation": "sum"}
    )
    assert query.status_code == 200, query.text
    assert Decimal(query.json()["rows"][0][0]) == sum(amount(index) for index in range(150_000))
