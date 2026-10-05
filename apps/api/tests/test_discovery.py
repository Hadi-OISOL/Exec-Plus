"""Use case: Verifies automatic exploration without compulsory business setup.

What it does: Checks exact results, replay, partial failures, meaning and tenant isolation.
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from execplus.domain.discovery import discovery_steps
from execplus.domain.guidance import DescriptionContext
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel, prepare
from test_understanding import confirm, context
from test_workspace_integration import identity

CONTENT = b"city,revenue,quantity\nKarachi,0.10,2\nKarachi,0.20,3\nLahore,,5\n"


def setup(env, content=CONTENT):
    model = ScriptedModel()
    owner, wid, root = prepare(env, model, content=content)
    return owner, wid, root, model


def test_new_upload_immediately_has_exact_findings_and_replay_without_meaning_form(integration):
    env = integration
    owner, wid, root, model = setup(env)
    response = env.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 200, response.text
    brief = response.json()
    assert brief["shape"] == {"rows": 3, "columns": 3, "metrics": 2, "dimensions": 1}
    assert brief["definition_state"] == "inferred"
    findings = {finding["id"]: finding for finding in brief["findings"]}
    assert findings["revenue:avg"]["query"]["rows"] == [["0.150000000000"]]
    assert findings["revenue:min"]["query"]["rows"] == [["0.100000000000"]]
    assert findings["revenue:max"]["query"]["rows"] == [["0.200000000000"]]
    assert findings["city:count"]["query"]["rows"] == [["Karachi", 2], ["Lahore", 1]]
    assert "Karachi has 2 rows" in findings["city:count"]["text"]
    assert "Column meaning and units are inferred" in findings["revenue:avg"]["text"]
    assert "1 empty cells" in brief["quality"][0]["text"]
    for finding in findings.values():
        query = finding["query"]
        lineage = query["lineage"]
        assert lineage["model_route"] == "deterministic:discovery-v1"
        assert lineage["receipt"]["sources"] == brief["sources"]
        replay = env.client.post(
            f"/workspaces/{wid}/queries/{lineage['query_id']}/replay", headers=owner
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["rows"] == query["rows"]
    with env.engine.connect() as connection:
        assert connection.execute(select(s.understandings)).first() is None
        assert len(connection.execute(select(s.query_executions)).all()) == 7
    assert not model.requests


def test_text_only_file_produces_real_category_counts(integration):
    owner, _, root, _ = setup(integration, b"category,note\nA,One\nB,Two\nA,Three\n")
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    assert len(brief["findings"]) == 1
    assert brief["findings"][0]["id"] == "category:count"
    assert brief["findings"][0]["query"]["rows"] == [["A", 2], ["B", 1]]


def test_numeric_identifiers_years_and_ratings_are_not_automatic_measures():
    table = TableData(
        ("CustomerID", "PostalCode", "Year", "Rating", "UnitPrice"),
        (("100", "200", "2025", "4", "0.10"), ("101", "201", "2026", "5", "0.20")),
    )
    metadata = profile(table)
    ctx = DescriptionContext("Retail", metadata, dataset_view(metadata), None, "inferred")
    steps = discovery_steps(ctx)
    assert {step.metric for step in steps} == {"UnitPrice"}
    assert len(steps) == 3
    assert metadata["columns"][0]["role"] == "metric"


@pytest.mark.parametrize("state", ["inferred", "rejected", "needs_review"])
def test_saved_uncertain_meaning_keeps_profile_help_and_blocks_calculation(integration, state):
    env = integration
    owner, _, root, _ = setup(env)
    current = context(env, owner, root)
    assert confirm(env, owner, root, current, current["definition"], state=state).status_code == 201
    brief = env.client.get(root + "/discovery", headers=owner).json()
    assert brief["findings"] == []
    assert brief["quality"]
    assert "definition needs review" in brief["summary"]
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


def test_confirmed_metric_filters_and_unit_are_applied(integration):
    env = integration
    owner, _, root, _ = setup(env)
    current = context(env, owner, root)
    definition = current["definition"]
    definition["columns"][1]["currency"] = "PKR"
    definition["metrics"] = [
        {
            "name": "Karachi revenue",
            "column": "revenue",
            "aggregation": "sum",
            "filters": [{"column": "city", "operator": "eq", "value": "Karachi"}],
        }
    ]
    assert confirm(env, owner, root, current, definition).status_code == 201
    brief = env.client.get(root + "/discovery", headers=owner).json()
    revenue = [finding for finding in brief["findings"] if finding["metric"] == "revenue"]
    assert len(revenue) == 1
    assert revenue[0]["query"]["rows"] == [["0.300000000000"]]
    assert "Declared unit: PKR" in revenue[0]["text"]
    assert "understanding_id" in brief["sources"][0]


def test_mixed_currencies_do_not_silently_produce_global_money_findings(integration):
    owner, _, root, _ = setup(integration, b"currency,revenue\nPKR,10\nUSD,20\n")
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    assert [finding["id"] for finding in brief["findings"]] == ["currency:count"]
    assert any("Group or filter by currency" in item for item in brief["limitations"])


def test_bad_measure_does_not_hide_valid_findings_or_reveal_cell_contents(integration):
    owner, _, root, _ = setup(integration, b"amount,quantity,city\n1e100,2,A\n2e100,4,B\n")
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    assert any(finding["id"] == "quantity:avg" for finding in brief["findings"])
    assert any("amount" in text for text in brief["limitations"])
    assert "1e100" not in str(brief) and "2e100" not in str(brief)


def test_discovery_is_tenant_scoped_and_missing_sources_are_not_cached(integration):
    env = integration
    owner, wid, root, _ = setup(env)
    outsider, _ = identity(env, "outsider-discovery@example.test")
    assert env.client.get(root + "/discovery", headers=outsider).status_code == 404
    assert env.client.get(root + "/discovery", headers=owner).status_code == 200
    with env.runtime.analytics.uow() as repo:
        upload = repo.upload(UUID(wid), UUID(root.split("/")[4]), UUID(root.split("/")[6]))
    env.runtime.analytics.storage.delete(upload)
    assert env.client.get(root + "/discovery", headers=owner).status_code == 503


def test_definition_change_during_discovery_requires_new_brief(integration, monkeypatch):
    env = integration
    owner, _, root, _ = setup(env)
    current = context(env, owner, root)
    executor = env.runtime.analytics.executor
    execute = executor.execute
    changed = False

    async def changing_execute(*args, **kwargs):
        nonlocal changed
        result = await execute(*args, **kwargs)
        if not changed:
            changed = True
            response = await asyncio.to_thread(confirm, env, owner, root, current)
            assert response.status_code == 201
        return result

    monkeypatch.setattr(executor, "execute", changing_execute)
    response = env.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 422
    assert "meaning changed" in response.text


def test_unsupported_alias_retains_profile_help(integration):
    owner, _, root, _ = setup(integration, b"__value,quantity\n1,2\n3,4\n")
    response = integration.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 200
    brief = response.json()
    assert brief["findings"] == []
    assert any("reserved alias" in item for item in brief["limitations"])


def test_new_calendar_components_do_not_trigger_false_date_warnings(integration):
    owner, _, root, _ = setup(integration, b"day,quantity\n3,2\n4,4\n")
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    assert all(item["code"] != "invalid_dates" for item in brief["quality"])
    assert not any("day is not recognized" in item for item in brief["limitations"])


def test_negative_finding_does_not_mistake_adjustments_for_errors(integration):
    owner, _, root, _ = setup(integration, b"Quantity\n-2\n4\n")
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    minimum = next(item for item in brief["findings"] if item["id"] == "Quantity:min")
    assert minimum["query"]["rows"] == [[-2]]
    assert "Negative values are present" in minimum["text"]
    assert "before treating them as errors" in minimum["text"]


def test_missing_largest_category_does_not_suggest_a_literal_missing_filter(integration):
    owner, _, root, _ = setup(integration, b"category,revenue\n,1\n,2\n,3\nA,4\nB,5\n")
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    finding = next(item for item in brief["findings"] if item["id"] == "category:count")
    assert "(missing) has 3 rows" in finding["text"]
    assert finding["question"] == "Check data quality"


def test_confirmed_identifier_role_is_not_selected_as_an_automatic_distribution(integration):
    env = integration
    owner, _, root, _ = setup(env, b"Account,revenue\nA,1\nB,2\nA,3\n")
    current = context(env, owner, root)
    definition = current["definition"]
    definition["columns"][0]["role"] = "identifier"
    assert confirm(env, owner, root, current, definition).status_code == 201
    brief = env.client.get(root + "/discovery", headers=owner).json()
    assert all(finding["id"] != "Account:count" for finding in brief["findings"])
