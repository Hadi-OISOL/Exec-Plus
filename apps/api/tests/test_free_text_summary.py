"""Use case: Regression tests for D16, free-text survey questions on a file without documents.

What it does: Replays the observed "textual" model plan through a scripted planner and the
real thread, router and query services, and checks the deterministic word counts against an
independent pandas count; unit tests cover field choice and Urdu / Roman Urdu tokenising.
"""

import io
import json
from uuid import UUID

import pandas as pd
import pytest

from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.free_text import (
    FREE_TEXT_ROUTE,
    free_text_column,
    is_free_text,
    summarise,
    tokens,
)
from execplus.domain.semantics import dataset_view
from test_harness_context_integration import Planner
from test_workspace_integration import dataset, identity, upload, workspace

SURVEY_CSV = (
    "respondent_id,region,nps,feedback\n"
    "1,North,3,Delivery was late and the box was damaged\n"
    "2,South,9,Great service\n"
    "3,North,2,Late delivery again\n"
    "4,South,4,Customer support never answered my call\n"
    "5,North,1,delivery late phir se\n"
    "6,East,8,Great service\n"
    "7,East,5,\n"
    "8,West,2,ڈلیوری دیر سے آئی\n"
).encode()
TEXTUAL = {"kind": "textual", "query": "customer complaints"}


def survey_view():
    return dataset_view(
        {
            "columns": [
                {"name": "respondent_id", "type": "integer", "role": "dimension"},
                {"name": "region", "type": "text", "role": "dimension"},
                {"name": "nps", "type": "integer", "role": "metric"},
                {"name": "feedback", "type": "text", "role": "dimension"},
            ]
        }
    )


def test_field_choice_prefers_a_named_text_field_then_a_written_answers_name():
    view = survey_view()
    assert free_text_column("What are customers complaining about?", view) == "feedback"
    assert free_text_column("What words appear in region?", view) == "region"
    assert (
        free_text_column(
            "What are customers complaining about?",
            dataset_view({"columns": [{"name": "region", "type": "text", "role": "dimension"}]}),
        )
        is None
    )


def test_tokens_drop_stop_words_and_tolerate_urdu_script_and_roman_urdu():
    assert tokens("Delivery was LATE and the box was damaged") == [
        "delivery",
        "late",
        "box",
        "damaged",
    ]
    assert tokens("delivery late phir se") == ["delivery", "late", "phir"]
    assert tokens("ڈلیوری دیر سے آئی") == ["ڈلیوری", "دیر", "آئی"]
    assert tokens("كتاب ہَے") == ["کتاب"]


def test_short_category_labels_are_not_treated_as_written_answers():
    labels = summarise("region", (("North", 3), ("South", 2)), 5)
    assert not is_free_text(labels)


def pandas_mentions(word):
    frame = pd.read_csv(io.BytesIO(SURVEY_CSV))
    answers = frame["feedback"].dropna().str.lower().str.split()
    return int(answers.map(lambda parts: word in parts).sum())


@pytest.mark.asyncio
async def test_complaints_question_without_documents_counts_words_in_the_feedback_field(
    integration,
):
    headers, actor = identity(integration, "survey@example.test")
    wid = workspace(integration, headers)
    did = dataset(integration, headers, wid)
    response = upload(integration, headers, wid, did, SURVEY_CSV, "survey.csv", "text/csv")
    assert response.status_code == 201, response.text
    model = Planner(TEXTUAL)
    router = IntentRouterService(model, integration.runtime.analytics, context_enabled=True)
    threads = ThreadService(integration.runtime.threads.uow, router)
    thread = await threads.start_thread(actor, UUID(wid), UUID(did), UUID(response.json()["id"]))
    answer, turn = await threads.ask(
        actor, UUID(wid), thread.id, "What are customers complaining about?"
    )
    assert turn.status == "complete"
    assert turn.model_route == FREE_TEXT_ROUTE
    assert answer.columns == ("feedback",)
    message = answer.message
    assert "not sentiment, themes or causes" in message
    assert "7 written answers in feedback (of 8 records" in message
    assert f"1. delivery — {pandas_mentions('delivery')} responses" in message
    assert f"2. late — {pandas_mentions('late')} responses" in message
    assert "great — 2 responses" in message
    assert "delivery late — 2 responses" in message
    assert '"Great service" (2 times)' in message
    assert len(model.requests) == 1
    assert json.loads(json.dumps(turn.evidence["guide"]))["columns"] == ["feedback"]
