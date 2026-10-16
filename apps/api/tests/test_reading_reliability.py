"""Use case: Makes qualitative explanations recover without guessing why data is unavailable.

What it does: Tests governed suggestions, truncated-provider correction and private diagnostics.
"""

import asyncio
import copy
import json
from dataclasses import FrozenInstanceError

import httpx
import pytest

from execplus.application.contracts import ModelMessage, ModelResponse
from execplus.application.progress import execution_progress
from execplus.application.services.structured_reading import (
    read_validated,
    reading_failure_notice,
    reading_failure_reason,
)
from execplus.domain.dataset_reading import parse_reading, reading_input
from execplus.domain.errors import IncompleteModelResponseError, ProviderUnavailableError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.reading_catalog import READING_RECIPES, exploration_catalog
from execplus.domain.semantics import DatasetView, SemanticColumn
from execplus.infrastructure.models.openai_compatible import OpenAICompatibleLanguageModel
from test_data_brief import BriefModel, good_reply, uploaded
from test_dataset_guidance import ask
from test_dataset_reading import READING, prepare
from test_understanding import context


def governed_view():
    return DatasetView(
        (
            SemanticColumn("record_id", "integer", "identifier"),
            SemanticColumn("segment", "text", "dimension"),
            SemanticColumn("revenue", "decimal", "metric"),
            SemanticColumn("ignored_cost", "decimal", "ignored"),
            SemanticColumn("day", "date", "dimension"),
        ),
        frozenset({"revenue"}),
        frozenset({"segment", "day"}),
    )


def test_catalog_recipes_use_only_current_fields_and_available_registered_operations():
    view = governed_view()
    catalog = exploration_catalog(view)
    assert catalog["metric_fields"] == ["revenue"]
    assert catalog["group_fields"] == ["segment", "day"]
    assert [recipe["key"] for recipe in catalog["recipes"]] == [
        "structure",
        "quality",
        "date_range",
        "records",
        "measures",
        "groups",
    ]
    profile_only = exploration_catalog(view, frozenset({"inspect_profile", "execute_python"}))
    assert not profile_only["metric_fields"] and not profile_only["group_fields"]
    assert {recipe["operation"] for recipe in profile_only["recipes"]} == {"inspect_profile"}
    empty = exploration_catalog(DatasetView((), frozenset(), frozenset()))
    assert [recipe["key"] for recipe in empty["recipes"]] == ["structure", "quality"]
    with pytest.raises(FrozenInstanceError):
        READING_RECIPES[0].operation = "execute_python"


def test_wide_reading_catalog_matches_bounded_prompt_and_rejects_unsupplied_suggestions():
    columns = tuple(SemanticColumn(f"measure_{i}", "decimal", "metric") for i in range(90))
    view = DatasetView(columns, frozenset(column.name for column in columns), frozenset())
    ctx = DescriptionContext("Wide file", {}, view, None, "inferred")
    sent = json.loads(reading_input(ctx, []))
    assert sent["columns_truncated"]
    assert sent["exploration_catalog"]["metric_fields"] == [c.name for c in columns[:80]]
    assert not sent["exploration_catalog"]["group_fields"]
    reading = {
        "summary": "Recorded measures.",
        "connections": [{"columns": ["measure_0"], "meaning": "A recorded measure."}],
        "explore": [{"metric": "measure_89", "group_by": ""}],
    }
    with pytest.raises(ValueError, match="Unknown exploration field"):
        parse_reading(json.dumps(reading), ctx)
    reading["explore"][0]["metric"] = "measure_0"
    assert parse_reading(json.dumps(reading), ctx)["explore"] == reading["explore"]


def test_reading_model_gets_exact_governed_catalog_without_ignored_metrics(integration):
    owner, _, _, path, model = prepare(integration, READING)
    answer = ask(integration, owner, path, "Help me understand this data")["answer"]
    sent = json.loads(model.requests[0].messages[1].content)
    assert sent["exploration_catalog"]["metric_fields"] == ["revenue"]
    assert "city" in sent["exploration_catalog"]["group_fields"]
    assert not sent["columns_truncated"]
    assert "What is the average of revenue by city?" in answer["guidance"]["suggestions"]


@pytest.mark.asyncio
async def test_truncated_provider_reply_gets_fresh_correction_without_identical_provider_retries(
    monkeypatch,
):
    calls = []
    checked = []

    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if len(calls) == 1 else "stop",
                        "message": {
                            "content": "private unfinished data"
                            if len(calls) == 1
                            else '{"ok":true}'
                        },
                    }
                ]
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handle))
    )
    model = OpenAICompatibleLanguageModel(
        "https://model.test",
        "test-only",
        "small",
        "large",
        "hosted",
        max_attempts=3,
        max_output_tokens=1024,
    )
    parsed, _, repaired = await read_validated(
        model,
        (ModelMessage("user", "authorized metadata"),),
        json.loads,
        before_retry=lambda: checked.append(True),
    )
    assert parsed == {"ok": True} and repaired and checked == [True]
    assert len(calls) == 2
    assert calls[0]["messages"] == calls[1]["messages"][:-1]
    assert "fresh, complete JSON" in calls[1]["messages"][-1]["content"]
    assert "private unfinished data" not in json.dumps(calls)
    assert all(call["max_tokens"] == 1024 and call["model"] == "large" for call in calls)


@pytest.mark.parametrize(
    "error,reason,notice,issue",
    [
        (
            IncompleteModelResponseError("private-partial"),
            "incomplete_response",
            "ended before",
            "incomplete",
        ),
        (
            ProviderUnavailableError("private-key"),
            "provider_unavailable",
            "service is unavailable",
            "unclassified",
        ),
        (ValueError("private-response"), "invalid_response", "did not pass", "unclassified"),
        (TimeoutError("private-deadline"), "deadline", "took too long", "unclassified"),
    ],
)
def test_failure_diagnostics_never_include_sensitive_exception_content(
    caplog, error, reason, notice, issue
):
    assert reading_failure_reason(error) == reason
    assert notice in reading_failure_notice(error)
    assert caplog.messages == [
        f"qualitative_reading_fallback reason={reason}",
        f"qualitative_reading_validation issue={issue}",
    ]
    assert "private-" not in caplog.text


def test_repeated_provider_truncation_falls_back_after_two_calls_preserving_saved_data(
    integration, caplog
):
    model = BriefModel(
        IncompleteModelResponseError("private-first"),
        IncompleteModelResponseError("private-second"),
        good_reply(),
    )
    owner, _, root = uploaded(integration, model)
    before = copy.deepcopy(context(integration, owner, root))
    response = integration.client.post(root + "/data-brief", headers=owner)
    assert response.status_code == 200
    result = response.json()
    assert result["source"] == "profile"
    assert "ended before it was complete" in result["notice"]
    assert "Your file is still available" in result["notice"]
    assert len(model.requests) == 2 and len(model.outcomes) == 1
    assert "private-first" not in response.text + caplog.text
    assert "private-second" not in response.text + caplog.text
    assert context(integration, owner, root) == before


def test_chat_truncation_can_recover_without_replaying_partial_text(integration):
    owner, _, _, path, model = prepare(
        integration, IncompleteModelResponseError("discard-private-reply"), READING
    )
    result = ask(integration, owner, path, "Help me understand this data")
    assert "What this data is about" in result["answer"]["message"]
    assert len(model.requests) == 2
    assert "discard-private-reply" not in str(model.requests) + str(result)


@pytest.mark.asyncio
async def test_truncation_correction_respects_shared_deadline_and_cancels_remaining_work():
    class SlowCorrection:
        calls = 0
        cancelled = False

        async def complete(self, request):
            self.calls += 1
            if self.calls == 1:
                raise IncompleteModelResponseError("cut")
            try:
                await asyncio.sleep(5)
                return ModelResponse("{}", "fixture", "fixture")
            finally:
                self.cancelled = True

    model = SlowCorrection()
    with pytest.raises(TimeoutError):
        await read_validated(model, (), json.loads, timeout_seconds=0.02)
    assert model.calls == 2 and model.cancelled


@pytest.mark.asyncio
async def test_truncation_correction_cannot_exceed_existing_model_call_budget():
    class Budget:
        calls = 0

        async def model_call(self):
            self.calls += 1
            if self.calls > 1:
                raise IngestionError("job_budget", "Model-call limit.", 422)

    model = BriefModel(IncompleteModelResponseError("cut"), good_reply())
    budget = Budget()
    with execution_progress(budget), pytest.raises(IngestionError, match="Model-call limit"):
        await read_validated(model, (), json.loads)
    assert budget.calls == 2 and len(model.requests) == 1
