"""Use case: Repairs the actual rejected reading shape without exposing its contents.

What it does: Checks fixed correction hints, private diagnostics and the existing two-call limit.
"""

import copy
import json
import logging

import pytest

from execplus.application.contracts import ModelMessage, ModelResponse
from execplus.application.services.structured_reading import (
    read_validated,
    reading_failure_notice,
    reading_validation_hint,
)
from execplus.domain.dataset_reading import parse_reading
from execplus.domain.guidance import DescriptionContext
from execplus.domain.reading_validation import ReadingIssue, ReadingValidationError
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
        ("summary", "Sales rose 25 percent.", ReadingIssue.PROSE_EVIDENCE),
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
