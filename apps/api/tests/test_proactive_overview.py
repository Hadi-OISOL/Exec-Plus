"""Checks automatic maps and conditional exploration use only current authorized metadata."""

import pytest

from test_dataset_access import fixture
from test_discovery import setup
from test_understanding import confirm, context


def test_overview_maps_visible_fields_without_model_or_definition_writes(integration):
    owner, _, root, model = setup(integration)
    response = integration.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 200, response.text
    brief = response.json()
    diagram = brief["diagram"]
    assert diagram["shown_fields"] == diagram["total_fields"] == 3
    assert {node["label"] for node in diagram["nodes"] if node["kind"] == "field"} == {
        "city",
        "revenue",
        "quantity",
    }
    assert all(edge["relation"] == "contains" for edge in diagram["edges"])
    assert brief["scenario_metrics"] == []
    assert not model.requests


def test_what_if_suggestions_require_complete_confirmed_fixed_units(integration):
    owner, _, root, _ = setup(
        integration, b"city,Soil_Moisture,revenue,unknown\nA,10,2,1\nB,20,,2\n"
    )
    current = context(integration, owner, root)
    definition = current["definition"]
    for column in definition["columns"]:
        if column["name"] == "Soil_Moisture":
            column["unit"] = "%"
        elif column["name"] == "revenue":
            column["unit"] = "USD"
    response = confirm(integration, owner, root, current, definition)
    assert response.status_code == 201, response.text
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    assert brief["scenario_metrics"] == [{"metric": "Soil_Moisture", "aggregation": "avg"}]


def test_overview_map_does_not_reintroduce_hidden_columns_or_rows(integration):
    _, _, member, _, _, _, _, root, _, _ = fixture(integration)
    response = integration.client.get(root + "/discovery", headers=member)
    assert response.status_code == 200, response.text
    brief = response.json()
    assert {node["label"] for node in brief["diagram"]["nodes"] if node["kind"] == "field"} == {
        "city",
        "amount",
    }
    assert '"cost"' not in response.text and "Lahore" not in response.text
    assert brief["shape"]["rows"] == 2


def test_wide_schema_does_not_silently_publish_partial_map(integration):
    names = [f"field_{index}" for index in range(81)]
    content = (",".join(names) + "\n" + ",".join(["text"] * 81) + "\n").encode()
    owner, _, root, _ = setup(integration, content)
    response = integration.client.get(root + "/discovery", headers=owner)
    assert response.status_code == 200, response.text
    assert response.json()["diagram"] is None
    assert "80" in response.json()["diagram_notice"]


@pytest.mark.parametrize("aggregation", ["sum", "avg", "count", "min", "max"])
def test_scenario_shortcut_respects_declared_calculation(integration, aggregation):
    owner, _, root, _ = setup(integration, b"city,revenue\nA,10\nB,20\n")
    current = context(integration, owner, root)
    definition = current["definition"]
    definition["columns"][1]["currency"] = "USD"
    definition["metrics"] = [
        {
            "name": "Recorded revenue",
            "column": "revenue",
            "aggregation": aggregation,
            "filters": [],
        }
    ]
    response = confirm(integration, owner, root, current, definition)
    assert response.status_code == 201, response.text
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    expected = (
        [{"metric": "revenue", "aggregation": aggregation}] if aggregation in {"sum", "avg"} else []
    )
    assert brief["scenario_metrics"] == expected


def test_varying_currency_has_no_aggregate_what_if_shortcut(integration):
    owner, _, root, _ = setup(integration, b"currency,revenue\nUSD,10\nPKR,20\n")
    current = context(integration, owner, root)
    definition = current["definition"]
    definition["columns"][1]["unit_column"] = "currency"
    response = confirm(integration, owner, root, current, definition)
    assert response.status_code == 201, response.text
    brief = integration.client.get(root + "/discovery", headers=owner).json()
    assert brief["scenario_metrics"] == []
