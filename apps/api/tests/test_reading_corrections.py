"""Use case: Repairs the actual rejected reading shape without exposing its contents.

What it does: Checks fixed correction hints, private diagnostics and the existing two-call limit.
"""

import copy
import json
import logging
from dataclasses import replace

import pytest

from execplus.application.contracts import ModelMessage, ModelResponse
from execplus.application.services.structured_reading import (
    read_validated,
    reading_failure_notice,
    reading_validation_hint,
)
from execplus.domain.dataset_reading import READING_PROMPT, parse_reading
from execplus.domain.guidance import DescriptionContext
from execplus.domain.reading_validation import (
    READING_PROSE_RULES,
    ReadingIssue,
    ReadingValidationError,
)
from execplus.domain.semantics import DatasetView, SemanticColumn

VIEW = DatasetView(
    (SemanticColumn("sales", "decimal", "metric"), SemanticColumn("city", "text", "dimension")),
    frozenset({"sales"}),
    frozenset({"city"}),
)
CONTEXT = DescriptionContext("Saved source", {}, VIEW, None, "inferred")
VALID = {
    "summary": "Recorded sales grouped by city.",
    "connections": [{"columns": ["sales", "city"], "meaning": "Sales and their recorded city."}],
    "explore": [{"metric": "sales", "group_by": "city"}],
}


@pytest.mark.parametrize(
    "field,value,issue",
    [
        ("summary", "PrivateSecret" * 40, ReadingIssue.TEXT_BOUNDS),
        ("summary", "Sales rose 25 percent.", ReadingIssue.PROSE_NUMBERS),
        ("connections", [], ReadingIssue.CONNECTIONS),
        (
            "connections",
            [{"columns": ["PrivateUnknown"], "meaning": "Recorded."}],
            ReadingIssue.FIELDS,
        ),
        (
            "explore",
            [{"metric": "PrivateUnknown", "group_by": "city"}],
            ReadingIssue.EXPLORATION_FIELDS,
        ),
    ],
)
def test_rejected_reading_gives_fixed_issue_without_echoing_model_text(field, value, issue, caplog):
    payload = copy.deepcopy(VALID)
    payload[field] = value
    with pytest.raises(ReadingValidationError) as caught:
        parse_reading(json.dumps(payload), CONTEXT)
    assert caught.value.issue == issue
    code, hint = reading_validation_hint(caught.value)
    assert code == issue.value and hint
    with caplog.at_level(logging.INFO):
        reading_failure_notice(caught.value)
    assert f"issue={issue.value}" in caplog.text
    assert "PrivateSecret" not in caplog.text + hint
    assert "PrivateUnknown" not in caplog.text + hint
    assert "25 percent" not in caplog.text + hint


@pytest.mark.asyncio
async def test_correction_addresses_text_limit_without_replaying_rejected_answer(caplog):
    class Model:
        def __init__(self):
            self.requests = []

        async def complete(self, request):
            self.requests.append(request)
            value = VALID if len(self.requests) > 1 else {**VALID, "summary": "PrivateReply" * 40}
            return ModelResponse(json.dumps(value), "test", "test")

    model = Model()
    with caplog.at_level(logging.INFO):
        result, _, corrected = await read_validated(
            model,
            (ModelMessage("system", "Follow the reading contract."),),
            lambda value: parse_reading(value, CONTEXT),
        )
    assert result == VALID and corrected and len(model.requests) == 2
    hint = model.requests[1].messages[-1].content
    assert "summary at most 360 characters" in hint
    assert "meaning at most 200 characters" in hint
    assert "PrivateReply" not in hint + caplog.text
    assert "attempt=1 issue=text_bounds" in caplog.text


def test_unknown_exception_and_broken_json_never_enter_diagnostics(caplog):
    secret = "private-generated-content"
    code, hint = reading_validation_hint(ValueError(secret))
    assert code == "unclassified" and secret not in hint
    with pytest.raises(json.JSONDecodeError) as caught:
        json.loads(secret)
    with caplog.at_level(logging.WARNING):
        reading_failure_notice(caught.value)
    assert "issue=json" in caplog.text
    assert secret not in caplog.text


@pytest.mark.parametrize("prose_field", ["summary", "meaning"])
@pytest.mark.parametrize(
    "text,issue",
    [
        ("Contains 365 daily records.", ReadingIssue.PROSE_NUMBERS),
        ("Recorded on 2026-10-16.", ReadingIssue.PROSE_NUMBERS),
        ("Contains ٣ records.", ReadingIssue.PROSE_NUMBERS),
        ("See https://private.example/source.", ReadingIssue.PROSE_LINKS),
        ("See http://private.example/source.", ReadingIssue.PROSE_LINKS),
        ("Read `sales` together with city.", ReadingIssue.PROSE_MARKUP),
        ("Read <sales> together with city.", ReadingIssue.PROSE_MARKUP),
        ("Recorded sales > recorded costs.", ReadingIssue.PROSE_MARKUP),
        ("Recorded sales.\nCompare cities.", ReadingIssue.PROSE_CONTROL),
        ("Recorded sales.\tCompare cities.", ReadingIssue.PROSE_CONTROL),
        ("Recorded sales.\x00Compare cities.", ReadingIssue.PROSE_CONTROL),
        ("Recorded sales.\x1fCompare cities.", ReadingIssue.PROSE_CONTROL),
    ],
)
def test_each_prose_issue_has_fixed_private_diagnostic_without_relaxing_checks(
    prose_field, text, issue, caplog
):
    payload = copy.deepcopy(VALID)
    secret = "PrivateRejectedReply"
    rejected = secret + " " + text
    if prose_field == "summary":
        payload["summary"] = rejected
    else:
        payload["connections"][0]["meaning"] = rejected
    with pytest.raises(ReadingValidationError) as caught:
        parse_reading(json.dumps(payload), CONTEXT)
    assert caught.value.issue == issue
    code, hint = reading_validation_hint(caught.value)
    assert code == issue.value
    with caplog.at_level(logging.WARNING):
        reading_failure_notice(caught.value)
    assert f"issue={issue.value}" in caplog.text
    assert "reason=invalid_response" in caplog.text
    assert secret not in caplog.text + hint + str(caught.value)
    assert "private.example" not in caplog.text + hint + str(caught.value)


def test_exact_supplied_field_name_digit_exemption_is_unchanged():
    name = "sales_2026"
    view = DatasetView(
        (SemanticColumn(name, "decimal", "metric"), SemanticColumn("city", "text", "dimension")),
        frozenset({name}),
        frozenset({"city"}),
    )
    ctx = replace(CONTEXT, view=view)
    payload = {
        "summary": "The sales_2026 field records sales by city.",
        "connections": [{"columns": [name, "city"], "meaning": "Compare sales_2026 by city."}],
        "explore": [{"metric": name, "group_by": "city"}],
    }
    assert parse_reading(json.dumps(payload), ctx) == payload
    for invalid in (
        "The Sales_2026 field records sales.",
        "The sales_2027 field records sales.",
        "The sales_2026 field contains 365 records.",
    ):
        with pytest.raises(ReadingValidationError) as caught:
            parse_reading(json.dumps({**payload, "summary": invalid}), ctx)
        assert caught.value.issue == ReadingIssue.PROSE_NUMBERS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,issue,hint_fragment",
    [
        ("There are 365 periods.", ReadingIssue.PROSE_NUMBERS, "copied from descriptions"),
        ("See https://private.example.", ReadingIssue.PROSE_LINKS, "Remove URLs"),
        ("Read `sales` by city.", ReadingIssue.PROSE_MARKUP, "no backticks"),
        ("Recorded sales.\nCompare cities.", ReadingIssue.PROSE_CONTROL, "Remove line breaks"),
    ],
)
async def test_one_correction_uses_safe_subtype_and_initial_plain_sentence_contract(
    text, issue, hint_fragment, caplog
):
    class Model:
        def __init__(self):
            self.requests = []

        async def complete(self, request):
            self.requests.append(request)
            payload = (
                VALID
                if len(self.requests) > 1
                else {
                    **VALID,
                    "summary": "PrivateRejectedReply " + text,
                }
            )
            return ModelResponse(json.dumps(payload), "test", "test")

    model = Model()
    verified = []
    with caplog.at_level(logging.INFO):
        result, _, corrected = await read_validated(
            model,
            (ModelMessage("system", READING_PROMPT),),
            lambda value: parse_reading(value, CONTEXT),
            before_retry=lambda: verified.append(True),
        )
    assert result == VALID and corrected and len(model.requests) == 2 and verified == [True]
    assert READING_PROSE_RULES in model.requests[0].messages[0].content
    correction = model.requests[1].messages[-1].content
    assert READING_PROSE_RULES in correction and hint_fragment in correction
    assert "single-line plain sentence" in correction
    assert "saved description or notes" in correction
    assert "connections.columns and explore.metric/group_by" in correction
    assert f"attempt=1 issue={issue.value}" in caplog.text
    assert "PrivateRejectedReply" not in correction + caplog.text
    assert "private.example" not in correction + caplog.text


@pytest.mark.asyncio
async def test_repeated_prose_failure_stops_after_two_calls_without_replaying_private_text(caplog):
    class Model:
        def __init__(self):
            self.requests = []

        async def complete(self, request):
            self.requests.append(request)
            payload = {**VALID, "summary": "PrivateRejectedReply\nStill malformed."}
            return ModelResponse(json.dumps(payload), "test", "test")

    model = Model()
    with caplog.at_level(logging.INFO), pytest.raises(ReadingValidationError) as caught:
        await read_validated(
            model,
            (ModelMessage("system", READING_PROMPT),),
            lambda value: parse_reading(value, CONTEXT),
        )
    assert caught.value.issue == ReadingIssue.PROSE_CONTROL
    assert len(model.requests) == 2
    assert "attempt=2 issue=prose_control" in caplog.text
    assert "PrivateRejectedReply" not in caplog.text + model.requests[1].messages[-1].content
