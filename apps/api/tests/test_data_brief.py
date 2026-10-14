"""Use case: Proves the upload reading is validated, private to its caller and usable as context.

What it does: Checks reply validation, the profile fallback and the real API without a live model.
"""

import json

import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import _describe_view
from execplus.domain.data_brief import (
    fallback_brief,
    model_input,
    parse_brief,
    sample_values,
    system_prompt,
)
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import apply_definition, infer_definition
from test_workspace_integration import dataset, identity, upload, workspace

HEADERS = ("order_id", "amt", "status", "order_date")
ROWS = (
    ("1", "1250", "paid", "2026-01-03"),
    ("2", "980", "paid", "2026-01-05"),
    ("3", "4300", "SecretRefundCode", "2026-01-09"),
)


def prepared():
    table = TableData(HEADERS, ROWS)
    source = profile(table)
    return source, infer_definition(source)


def good_reply(**changes):
    reply = dict(
        summary="Customer orders with an order value and a payment status.",
        grain="order",
        columns=[
            dict(name="amt", meaning="Order value", role="metric", unit="PKR", uncertain=False),
            dict(
                name="status",
                meaning="Payment state",
                role="dimension",
                uncertain=True,
                question="What do the status codes mean?",
            ),
        ],
        questions=["Is this every order or only a sample?"],
    )
    reply.update(changes)
    return reply


def test_valid_reply_lists_uncertain_columns_first_and_covers_every_column():
    source, definition = prepared()
    brief = parse_brief(json.dumps(good_reply()), source, definition)
    assert brief["source"] == "model"
    assert brief["columns"][0]["name"] == "status"
    assert {item["name"] for item in brief["columns"]} == set(HEADERS)
    amount = next(item for item in brief["columns"] if item["name"] == "amt")
    assert (amount["meaning"], amount["unit"], amount["role"]) == ("Order value", "PKR", "metric")


def test_fenced_json_and_numbers_taken_from_metadata_are_accepted():
    source, definition = prepared()
    reply = good_reply(summary="Orders from 2026-01-03 with 4 columns across 3 rows.")
    brief = parse_brief("```json\n" + json.dumps(reply) + "\n```", source, definition)
    assert brief["summary"].startswith("Orders from")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda reply: reply.update(summary="Total revenue was 5530 across all orders."),
        lambda reply: reply.update(columns=[dict(name="invented", meaning="x")]),
        lambda reply: reply.update(columns=[dict(name="amt"), dict(name="amt")]),
        lambda reply: reply.update(extra="field"),
        lambda reply: reply.update(summary=""),
        lambda reply: reply.update(summary="x" * 300),
        lambda reply: reply.update(columns="amt"),
        lambda reply: reply.update(columns=[dict(name="amt", meaning="Worth 999 each")]),
    ],
)
def test_unsupported_replies_are_rejected(mutation):
    source, definition = prepared()
    reply = good_reply()
    mutation(reply)
    with pytest.raises(ValueError):
        parse_brief(json.dumps(reply), source, definition)


def test_whole_data_questions_do_not_repeat_column_or_row_questions():
    source, definition = prepared()
    reply = good_reply(
        questions=[
            "What does one row represent?",
            "What is the currency for 'amt'?",
            "Is this every order or only a sample?",
        ]
    )
    brief = parse_brief(json.dumps(reply), source, definition)
    assert brief["questions"] == ["Is this every order or only a sample?"]


def test_whole_data_question_identical_to_a_column_question_is_dropped():
    source, definition = prepared()
    reply = good_reply(questions=["What do the status codes mean?", "Is this a sample?"])
    brief = parse_brief(json.dumps(reply), source, definition)
    assert brief["questions"] == ["Is this a sample?"]


def test_invalid_json_is_rejected():
    source, definition = prepared()
    with pytest.raises(ValueError):
        parse_brief("not json", source, definition)


def test_non_numeric_column_cannot_be_claimed_as_a_measure_and_bad_grain_keeps_inferred():
    source, definition = prepared()
    reply = good_reply(grain="galaxy")
    reply["columns"] = [dict(name="status", meaning="State", role="metric")]
    brief = parse_brief(json.dumps(reply), source, definition)
    assert next(item for item in brief["columns"] if item["name"] == "status")["role"] == (
        "dimension"
    )
    assert brief["grain"] == definition["grain"]


def test_model_input_contains_profile_metadata_but_never_row_values():
    source, definition = prepared()
    text = model_input(source, definition)
    assert "SecretRefundCode" not in text
    assert "amt" in text and "distinct_values" in text


def test_fallback_asks_about_units_without_a_model():
    source, definition = prepared()
    brief = fallback_brief(source, definition)
    assert brief["source"] == "profile"
    amount = next(item for item in brief["columns"] if item["name"] == "amt")
    assert amount["uncertain"] and "unit" in amount["question"]
    assert brief["columns"][0]["uncertain"]


def test_confirmed_meaning_reaches_the_planner_context():
    source, definition = prepared()
    for column in definition["columns"]:
        if column["name"] == "amt":
            column["meaning"] = "Order value after discount"
            column["unit"] = "PKR"
    view = apply_definition(dataset_view(source), definition)
    context = _describe_view(view)
    assert "Order value after discount" in context and "PKR" in context


class BriefModel:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        content = outcome if isinstance(outcome, str) else json.dumps(outcome)
        return ModelResponse(content, "brief-model", "test")


ORDERS = b"order_id,amt,status\n1,1250,SecretRefundCode\n2,980,paid\n3,4300,paid\n"


def uploaded(env, model, email="brief@example.test", content=ORDERS):
    owner, _ = identity(env, email)
    wid = workspace(env, owner)
    did = dataset(env, owner, wid)
    created = upload(env, owner, wid, did, content, "sales.csv", "text/csv")
    assert created.status_code == 201
    env.runtime.data_brief.model = model
    return owner, wid, f"/workspaces/{wid}/datasets/{did}/uploads/{created.json()['id']}"


def test_endpoint_returns_a_validated_model_reading_without_sending_row_values(integration):
    model = BriefModel(good_reply())
    owner, _, root = uploaded(integration, model)
    response = integration.client.post(f"{root}/data-brief", headers=owner)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "model" and body["model_route"] == "test:brief-model"
    assert body["notice"] == "" and body["can_edit"] and not body["already_confirmed"]
    assert body["state"] == "inferred" and body["version"] == 0
    assert "SecretRefundCode" not in " ".join(m.content for m in model.requests[0].messages)


@pytest.mark.parametrize(
    "outcome, notice",
    [
        (ProviderUnavailableError("down"), "unavailable"),
        ("not json at all", "could not be verified"),
        (good_reply(summary="Revenue was 99999."), "could not be verified"),
    ],
)
def test_endpoint_falls_back_to_profile_questions_when_the_model_cannot_be_used(
    integration, outcome, notice
):
    owner, _, root = uploaded(integration, BriefModel(outcome))
    response = integration.client.post(f"{root}/data-brief", headers=owner)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "profile" and notice in body["notice"]
    assert body["model_route"] is None and body["columns"]


def test_confirmed_upload_is_not_sent_to_the_model_again(integration):
    model = BriefModel(good_reply())
    owner, _, root = uploaded(integration, model, "confirmed@example.test")
    first = integration.client.post(f"{root}/data-brief", headers=owner).json()
    definition = first["definition"]
    definition["grain"] = "order"
    saved = integration.client.post(
        f"{root}/understanding",
        headers=owner,
        json=dict(
            revision_id=first["revision_id"],
            expected_version=first["version"],
            state="confirmed",
            definition=definition,
        ),
    )
    assert saved.status_code == 201, saved.text
    again = integration.client.post(f"{root}/data-brief", headers=owner).json()
    assert again["already_confirmed"] is True and again["state"] == "confirmed"
    assert len(model.requests) == 1


def test_another_users_upload_cannot_be_read(integration):
    model = BriefModel(good_reply())
    _, _, root = uploaded(integration, model, "owner-only@example.test")
    stranger, _ = identity(integration, "stranger@example.test")
    response = integration.client.post(f"{root}/data-brief", headers=stranger)
    assert response.status_code in {403, 404}
    assert model.requests == []
    assert integration.client.post(f"{root}/data-brief").status_code == 401


def sampled_table():
    table = TableData(
        ("order_id", "customer_name", "email", "amt", "st"),
        (
            ("1", "Ali Raza", "ali@example.test", "1250", "P"),
            ("2", "Sara Khan", "sara@example.test", "980", "R"),
            ("3", "Omar Sheikh", "omar@example.test", "4300", "P"),
            ("4", "Hina Malik", "hina@example.test", "640", "C"),
        ),
    )
    source = profile(table)
    return table, source, infer_definition(source)


def test_samples_withhold_identifiers_and_personal_columns_and_bound_the_rest():
    table, _, definition = sampled_table()
    samples = sample_values(table, definition, 2)
    assert samples["columns"]["order_id"] == ["(withheld)"]
    assert samples["columns"]["customer_name"] == ["(withheld)"]
    assert samples["columns"]["email"] == ["(withheld)"]
    assert samples["columns"]["st"][0] == "P" and len(samples["columns"]["st"]) == 2
    assert len(samples["rows"]) == 3
    assert all(row["email"] == "(withheld)" for row in samples["rows"])
    assert "Ali Raza" not in json.dumps(samples) and "ali@example.test" not in json.dumps(samples)


def test_model_input_adds_samples_only_when_given():
    table, source, definition = sampled_table()
    without = model_input(source, definition)
    assert "example_values" not in without and "example_rows" not in without
    withs = model_input(source, definition, sample_values(table, definition, 4))
    assert "example_values" in withs and "example_rows" in withs
    assert "ali@example.test" not in withs
    assert "codes" in system_prompt(sample_values(table, definition, 4))
    assert "codes" not in system_prompt(None)


def test_numbers_that_appear_in_sampled_values_may_be_repeated_by_the_model():
    table, source, definition = sampled_table()
    samples = sample_values(table, definition, 4)
    reply = good_reply(columns=[dict(name="amt", meaning="Often 1250 or 640", role="metric")])
    with pytest.raises(ValueError):
        parse_brief(json.dumps(reply), source, definition)
    brief = parse_brief(json.dumps(reply), source, definition, samples)
    assert next(item for item in brief["columns"] if item["name"] == "amt")["meaning"]


CODED = (
    b"order_id,customer_name,amt,st\n1,Ali Raza,1250,P\n2,Sara Khan,980,R\n3,Omar Sheikh,4300,P\n"
)


def test_endpoint_sends_a_bounded_sample_only_when_enabled(integration):
    reply = good_reply(
        columns=[
            dict(name="amt", meaning="Order value", role="metric", uncertain=False),
            dict(name="st", meaning="Status code", role="dimension", uncertain=True),
        ]
    )
    model = BriefModel(reply, reply)
    owner, _, root = uploaded(integration, model, "sampled@example.test", CODED)
    off = integration.client.post(f"{root}/data-brief", headers=owner).json()
    assert off["source"] == "model" and off["sampled"] is False
    assert "example_values" not in model.requests[0].messages[1].content
    integration.runtime.data_brief.sample_limit = 6
    on = integration.client.post(f"{root}/data-brief", headers=owner).json()
    sent = model.requests[1].messages[1].content
    assert on["source"] == "model" and on["sampled"] is True
    assert '"P"' in sent and '"R"' in sent and "example_rows" in sent
    assert "Ali Raza" not in sent and "Sara Khan" not in sent
    assert "codes" in model.requests[1].messages[0].content


def test_wide_files_send_a_bounded_column_window_and_ask_for_a_bounded_reply():
    headers = tuple(f"metric_{index}" for index in range(150))
    table = TableData(headers, (tuple("1" for _ in headers), tuple("2" for _ in headers)))
    source = profile(table)
    definition = infer_definition(source)
    samples = sample_values(table, definition, 4)
    payload = json.loads(model_input(source, definition, samples))
    assert len(payload["columns"]) == 80
    assert set(payload["example_rows"][0]) == {column["name"] for column in payload["columns"]}
    assert "at most 20 columns" in system_prompt(samples)
    assert payload["column_count"] == 150


def test_endpoint_reports_whether_a_model_is_configured(integration):
    model = BriefModel(ProviderUnavailableError("down"))
    owner, _, root = uploaded(integration, model, "enabled@example.test")
    assert (
        integration.client.post(f"{root}/data-brief", headers=owner).json()["model_enabled"]
        is False
    )
    integration.runtime.data_brief.model_enabled = True
    model.outcomes.append(ProviderUnavailableError("down"))
    again = integration.client.post(f"{root}/data-brief", headers=owner).json()
    assert again["model_enabled"] is True and again["source"] == "profile"
