"""Use case: Verifies units and domains suggested from column names stay suggestions.

What it does: Checks name parsing, agriculture detection, reading prefill and identifier wording.
"""

import pytest

from execplus.application.services.discovery import _metadata
from execplus.domain.data_brief import fallback_brief, ground_brief, missing_question
from execplus.domain.guidance import DescriptionContext
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import (
    UNIT_SOURCE,
    infer_definition,
    questions,
    suggested_unit,
    unit_suggestions,
)

FARM = TableData(
    (
        "id",
        "Soil_Type",
        "Soil_pH",
        "Soil_Moisture",
        "Electrical_Conductivity",
        "Temperature_C",
        "Humidity",
        "Rainfall_mm",
        "Sunlight_Hours",
        "Wind_Speed_kmh",
        "Crop_Type",
        "Irrigation_Type",
        "Field_Area_hectare",
    ),
    (
        (
            "1",
            "Clay",
            "6.1",
            "20.5",
            "1.2",
            "21.4",
            "60.1",
            "500.2",
            "6.5",
            "3.1",
            "Rice",
            "Drip",
            "2.5",
        ),
        (
            "2",
            "Silt",
            "7.2",
            "30.5",
            "2.2",
            "25.4",
            "70.1",
            "800.2",
            "7.5",
            "4.1",
            "Wheat",
            "Canal",
            "3.5",
        ),
    ),
)


@pytest.mark.parametrize(
    ("name", "unit", "currency"),
    [
        ("Rainfall_mm", "mm", ""),
        ("Temperature_C", "°C", ""),
        ("Wind_Speed_kmh", "km/h", ""),
        ("Wind_Speed_km_h", "km/h", ""),
        ("Field_Area_hectare", "hectare", ""),
        ("Sunlight_Hours", "hours", ""),
        ("Soil_pH", "pH", ""),
        ("Humidity", "%", ""),
        ("Discount_pct", "%", ""),
        ("Rainfall (mm)", "mm", ""),
        ("Height_m", "m", ""),
        ("Revenue_USD", "", "USD"),
    ],
)
def test_unambiguous_names_suggest_units(name, unit, currency):
    assert suggested_unit(name) == dict(unit=unit, currency=currency, source=UNIT_SOURCE)


@pytest.mark.parametrize(
    "name",
    [
        "Soil_Moisture",
        "Electrical_Conductivity",
        "Organic_Carbon",
        "Price_per_kg",
        "Grade_C",
        "Temp_Min",
        "Revenue_m",
        "Orders",
    ],
)
def test_ambiguous_names_stay_questions(name):
    assert suggested_unit(name) is None


def test_farm_proposal_suggests_units_and_agriculture_without_filling_definition():
    metadata = profile(FARM)
    definition = infer_definition(metadata)
    assert definition["domain"] == "agriculture"
    assert all(not column["unit"] and not column["currency"] for column in definition["columns"])
    suggestions = {item["column"]: item["unit"] for item in unit_suggestions(definition)}
    assert suggestions == {
        "Soil_pH": "pH",
        "Temperature_C": "°C",
        "Humidity": "%",
        "Rainfall_mm": "mm",
        "Sunlight_Hours": "hours",
        "Wind_Speed_kmh": "km/h",
        "Field_Area_hectare": "hectare",
    }
    asked = questions(definition, metadata)
    assert {item["question"] for item in unit_suggestions(definition)} <= set(asked)
    assert "What unit does Soil_Moisture measure?" in asked
    assert infer_definition(metadata, "research")["domain"] == "research"


def test_saved_units_suppress_suggestions():
    definition = infer_definition(profile(FARM))
    for column in definition["columns"]:
        if column["name"] == "Rainfall_mm":
            column["unit"] = "inches"
    assert "Rainfall_mm" not in {item["column"] for item in unit_suggestions(definition)}


def test_reading_prefills_name_units_as_labelled_suggestions_only():
    metadata = profile(FARM)
    definition = infer_definition(metadata)
    brief = ground_brief(fallback_brief(metadata, definition), definition, preserve_saved=False)
    rows = {row["name"]: row for row in brief["columns"]}
    assert rows["Rainfall_mm"]["unit"] == "mm"
    assert rows["Rainfall_mm"]["unit_source"] == UNIT_SOURCE
    assert rows["Soil_Moisture"]["unit"] == "" and rows["Soil_Moisture"]["unit_source"] == ""
    answered = {"meaning": "Described by the owner"}
    assert missing_question({**rows["Rainfall_mm"], **answered}) is None
    assert missing_question({**rows["Soil_Moisture"], **answered})[0] == "unit"
    assert all(not column["unit"] for column in definition["columns"])


def test_identifier_wording_agrees_with_count():
    def summary(table):
        metadata = profile(table)
        context = DescriptionContext("f", metadata, dataset_view(metadata), None, "inferred")
        return _metadata(context)["summary"]

    assert "id looks like an identifier: use it" in summary(FARM)
    two = TableData(("id", "code", "amount"), (("1", "A1", "2.5"), ("2", "B2", "3.5")))
    assert "look like identifiers: use them" in summary(two)
