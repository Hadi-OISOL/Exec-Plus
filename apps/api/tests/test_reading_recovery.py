"""Use case: Keeps beginner readings useful when a model reply needs correction.

What it does: Tests bounded recovery, saved answers, focused questions and publication guards.
"""

import asyncio
import copy
import json
from uuid import UUID

import pytest
from sqlalchemy import delete, select

from execplus.application.contracts import ModelMessage, ModelResponse
from execplus.application.progress import execution_progress
from execplus.application.services.structured_reading import read_validated
from execplus.domain.data_brief import ground_brief, model_input, next_question, parse_brief
from execplus.domain.dataset_reading import render_reading
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData, profile
from execplus.domain.semantics import dataset_view
from execplus.domain.understanding import infer_definition
from execplus.infrastructure.persistence import schema as s
from test_data_brief import BriefModel, good_reply, prepared, uploaded
from test_understanding import confirm, context


def test_twenty_column_count_failure_is_repaired_without_loosening_numeric_validation(integration):
    headers = ["day", "amount", *(f"factor_{index}" for index in range(18))]
    content = (
        ",".join(headers)
        + "\n2026-01-01,12,"
        + ",".join("1" for _ in range(18))
        + "\n2026-01-02,15,"
        + ",".join("2" for _ in range(18))
        + "\n"
    ).encode()
    valid = good_reply(summary="Daily readings and factors to review.", columns=[], grain="record")
    invalid = {**valid, "summary": "Daily readings with 18 integer factors."}
    model = BriefModel(invalid, valid)
    owner, _, root = uploaded(integration, model, content=content)
    response = integration.client.post(root + "/data-brief", headers=owner)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["source"] == "model" and result["repaired"]
    assert result["summary"] == valid["summary"] and len(result["columns"]) == 20
    assert len(model.requests) == 2
    assert model.requests[1].messages[:2] == model.requests[0].messages
    assert "18 integer factors" not in model.requests[1].messages[-1].content
    assert "Do not count fields" in model.requests[1].messages[-1].content
    assert context(integration, owner, root)["version"] == 0


@pytest.mark.parametrize("bad", ['{"summary":', "x" * 32_001], ids=["truncated", "oversized"])
def test_truncated_or_oversized_reply_has_one_short_correction(integration, bad):
    model = BriefModel(bad, good_reply())
    owner, _, root = uploaded(integration, model)
    result = integration.client.post(root + "/data-brief", headers=owner).json()
    assert result["source"] == "model" and result["repaired"]
    assert len(model.requests) == 2
    assert bad not in model.requests[1].messages[-1].content


def test_repeated_invalid_reply_falls_back_after_two_calls_with_a_real_question(integration):
    model = BriefModel("invalid", "still invalid", good_reply())
    owner, _, root = uploaded(integration, model)
    result = integration.client.post(root + "/data-brief", headers=owner).json()
    assert result["source"] == "profile" and result["model_route"] is None
    assert len(model.requests) == 2 and len(model.outcomes) == 1
    assert result["next_question"]["column"] in {c["name"] for c in result["columns"]}


def test_draft_answers_reach_prompt_and_cannot_be_replaced_or_asked_again(integration):
    model = BriefModel(good_reply(grain="customer"))
    owner, _, root = uploaded(integration, model)
    current = context(integration, owner, root)
    definition = copy.deepcopy(current["definition"])
    definition["description"] = "Recorded payments after refunds."
    definition["grain"] = "record"
    for column in definition["columns"]:
        column["meaning"] = "Saved " + column["name"]
        if column["role"] == "metric":
            column["unit"] = "USD"
    assert confirm(integration, owner, root, current, definition, "needs_review").status_code == 201
    before = context(integration, owner, root)
    result = integration.client.post(root + "/data-brief", headers=owner).json()
    assert result["grain"] == "record" and result["next_question"] is None
    for column in result["columns"]:
        assert column["meaning"] == "Saved " + column["name"]
        assert not column["uncertain"] and not column["question"]
    assert next(c for c in result["columns"] if c["name"] == "amt")["unit"] == "USD"
    prompt = json.loads(model.requests[0].messages[1].content)
    assert prompt["saved_description"] == definition["description"]
    amount = next(c for c in prompt["columns"] if c["name"] == "amt")
    assert amount["saved_meaning"] == "Saved amt" and amount["saved_unit"] == "USD"
    assert context(integration, owner, root) == before


def test_invented_unit_is_not_offered_as_an_answer_but_explicit_name_unit_can_be_reviewed():
    source, definition = prepared()
    parsed = parse_brief(json.dumps(good_reply()), source, definition)
    grounded = ground_brief(parsed, definition, preserve_saved=False)
    amount = next(column for column in grounded["columns"] if column["name"] == "amt")
    assert amount["unit"] == "" and amount["uncertain"] and "unit" in amount["question"]
    source = profile(TableData(("temperature_C",), (("10",), ("20",))))
    definition = infer_definition(source)
    parsed = parse_brief(
        json.dumps(good_reply(columns=[dict(name="temperature_C", unit="C", role="metric")])),
        source,
        definition,
    )
    assert ground_brief(parsed, definition, False)["columns"][0]["unit"] == "C"


def test_focused_question_uses_saved_answers_and_never_asks_ignored_fields():
    _, definition = prepared()
    definition["grain"] = "unknown"
    assert next_question(definition)["kind"] == "grain"
    definition["grain"] = "record"
    for column in definition["columns"]:
        column["meaning"] = "Reviewed " + column["name"]
    focused = next_question(definition)
    assert focused["column"] == "amt" and focused["kind"] == "unit"
    next(c for c in definition["columns"] if c["name"] == "amt")["role"] = "ignored"
    assert next_question(definition) is None


def test_model_payload_retains_bounded_saved_fields_for_wide_sources():
    headers = tuple(f"factor_{index}" for index in range(100))
    source = profile(TableData(headers, (tuple("1" for _ in headers),)))
    definition = infer_definition(source)
    for column in definition["columns"]:
        column["meaning"] = "Meaning of " + column["name"]
    sent = json.loads(model_input(source, definition))
    assert len(sent["columns"]) == 80
    assert all(c["saved_meaning"] for c in sent["columns"])
    assert "factor_99" not in json.dumps(sent)


@pytest.mark.parametrize("outcome", [good_reply(), "invalid", ProviderUnavailableError("down")])
def test_changed_saved_answers_prevent_repair_or_publication(integration, outcome):
    env = integration

    class ChangingModel:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            current = await asyncio.to_thread(context, env, owner, root)
            definition = copy.deepcopy(current["definition"])
            definition["description"] = "Changed while reading."
            saved = await asyncio.to_thread(
                confirm, env, owner, root, current, definition, "needs_review"
            )
            assert saved.status_code == 201
            if isinstance(outcome, Exception):
                raise outcome
            content = outcome if isinstance(outcome, str) else json.dumps(outcome)
            return ModelResponse(content, "test", "test")

    model = ChangingModel()
    owner, _, root = uploaded(env, model)
    response = env.client.post(root + "/data-brief", headers=owner)
    assert response.status_code == 409, response.text
    assert model.calls == 1
    with env.engine.connect() as connection:
        assert not connection.execute(
            select(s.audit_events).where(s.audit_events.c.action == "data_brief.drafted")
        ).first()


@pytest.mark.parametrize("outcome", [good_reply(), "invalid", ProviderUnavailableError("down")])
def test_revoked_permission_prevents_retry_and_fallback_disclosure(integration, outcome):
    env = integration

    class RevokingModel:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            with env.engine.begin() as connection:
                connection.execute(
                    delete(s.memberships).where(s.memberships.c.workspace_id == UUID(wid))
                )
            if isinstance(outcome, Exception):
                raise outcome
            content = outcome if isinstance(outcome, str) else json.dumps(outcome)
            return ModelResponse(content, "test", "test")

    model = RevokingModel()
    owner, wid, root = uploaded(env, model)
    result = env.client.post(root + "/data-brief", headers=owner)
    assert result.status_code in {403, 404}
    assert model.calls == 1


@pytest.mark.asyncio
async def test_reading_repair_honors_model_call_budget_before_provider_call():
    class Budget:
        calls = 0

        async def model_call(self):
            self.calls += 1
            if self.calls > 1:
                raise IngestionError("job_budget", "Model-call limit.", 422)

    model = BriefModel("invalid", good_reply())
    budget = Budget()
    with execution_progress(budget), pytest.raises(IngestionError, match="Model-call limit"):
        await read_validated(model, (ModelMessage("user", "metadata"),), json.loads)
    assert len(model.requests) == 1 and budget.calls == 2


def test_slow_reading_falls_back_after_one_shared_deadline(integration):
    class SlowModel:
        calls = 0
        cancelled = False

        async def complete(self, request):
            self.calls += 1
            try:
                await asyncio.sleep(5)
            finally:
                self.cancelled = True
            return ModelResponse(json.dumps(good_reply()), "test", "test")

    model = SlowModel()
    owner, _, root = uploaded(integration, model)
    integration.runtime.data_brief.reading_timeout_seconds = 0.02
    response = integration.client.post(root + "/data-brief", headers=owner)
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "profile"
    assert model.calls == 1 and model.cancelled


def test_revision_changed_during_model_reading_is_not_returned(integration):
    env = integration

    class RevisingModel:
        async def complete(self, request):
            current = await asyncio.to_thread(context, env, owner, root)
            applied = await asyncio.to_thread(
                env.client.post,
                root + "/cleaning/apply",
                headers=owner,
                json={"expected_revision_id": current["revision_id"], "trim": True},
            )
            assert applied.status_code == 201, applied.text
            return ModelResponse(json.dumps(good_reply()), "test", "test")

    owner, _, root = uploaded(env, RevisingModel())
    response = env.client.post(root + "/data-brief", headers=owner)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "source_changed"


@pytest.mark.asyncio
async def test_correction_shares_initial_deadline_and_cancels_provider_work():
    class SlowCorrection:
        calls = 0
        cancelled = False

        async def complete(self, request):
            self.calls += 1
            try:
                await asyncio.sleep(0.03)
                return ModelResponse("invalid" if self.calls == 1 else "{}", "test", "test")
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    model = SlowCorrection()
    with pytest.raises(TimeoutError):
        await read_validated(
            model, (ModelMessage("user", "metadata"),), json.loads, timeout_seconds=0.05
        )
    assert model.calls == 2 and model.cancelled


@pytest.mark.asyncio
async def test_caller_cancellation_never_starts_a_correction():
    started = asyncio.Event()
    finished = asyncio.Event()

    class Pending:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

    model = Pending()
    task = asyncio.create_task(
        read_validated(model, (ModelMessage("user", "metadata"),), json.loads)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert model.calls == 1 and finished.is_set()


@pytest.mark.asyncio
async def test_async_retry_check_finishes_before_reusing_authorized_context():
    checked = False

    async def recheck():
        nonlocal checked
        await asyncio.sleep(0)
        checked = True
        raise IngestionError("source_changed", "Saved context changed.", 409)

    model = BriefModel("invalid", "{}")
    with pytest.raises(IngestionError, match="Saved context changed"):
        await read_validated(
            model, (ModelMessage("user", "metadata"),), json.loads, before_retry=recheck
        )
    assert checked and len(model.requests) == 1


def test_reading_with_no_model_exploration_still_asks_one_actual_missing_detail():
    source, definition = prepared()
    definition["grain"] = "record"
    for column in definition["columns"]:
        column["meaning"] = "Reviewed " + column["name"]
    ctx = DescriptionContext("Orders", source, dataset_view(source), definition, "confirmed")
    reading = {
        "summary": "Order records with payment details.",
        "connections": [{"columns": ["amt", "status"], "meaning": "Payment details."}],
        "explore": [],
    }
    message, _ = render_reading(ctx, reading, [])
    assert message.count("One thing to clarify") == 1
    assert "What unit is amt recorded in?" in message
    assert "What does amt" not in message and "single row" not in message
