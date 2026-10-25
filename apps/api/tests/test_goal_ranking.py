"""Use case: Verifies persona/goal ranking answers and the dataset-purpose-v1 endpoint.

What it does: Uses a fictional leads file where a non-tech record has the highest score, checks
the server ranking against an independent pandas recomputation, the clarifying choices for an
unmatched persona, an unknown role and ambiguous scores, the model-suggestion fallback and the
purpose endpoint's shape, authorization and 404.
"""

import io
import json
from uuid import UUID, uuid4

import pandas as pd
import pytest

from execplus.application.contracts import ModelResponse
from execplus.application.services.intent_router import IntentRouterService
from execplus.application.services.threads import ThreadService
from execplus.domain.goal_ranking import (
    ROUTE,
    choose_score,
    goal_question,
    persona_keywords,
    ranking_fields,
)
from execplus.domain.semantics import dataset_view
from test_workspace_integration import identity, upload, workspace

LEADS_CSV = (
    b"total_score,organization,person,role,need,evidence,contact,location,intent_score,"
    b"fit_score,source,url,posted_at,next_step\n"
    b"99,Sunrise Bakery,Ann Lee,Owner,need an accountant for tax season,"
    b"posted on a local board,ann@x.test,Lahore,9,9,Facebook,https://x.test/1,2026-10-01,Call Ann\n"
    b"92,Acme AI,Bo Chen,CTO,hiring backend engineer to build LLM pipeline,"
    b"job post mentions Python and APIs,bo@x.test,Remote,8,9,LinkedIn,https://x.test/2,"
    b"2026-10-10,Email Bo about the pipeline\n"
    b"88,Pixel Studio,Cy Diaz,Founder,looking for a logo and brand refresh,"
    b"asked for designers on a forum,cy@x.test,Karachi,7,6,Reddit,https://x.test/3,"
    b"2026-10-05,Send portfolio\n"
    b"75,Shopwise,Di Evans,Head of Product,needs a web developer for checkout app,"
    b"freelance listing,di@x.test,Remote,9,7,Upwork,https://x.test/4,2026-10-12,Apply on Upwork\n"
    b"60,DataNest,Ed Fox,COO,want a dashboard for sales data,"
    b"mentions SQL reporting,ed@x.test,Dubai,5,5,LinkedIn,https://x.test/5,2026-09-20,Book call\n"
    b"75,Gearbox,Fay Gill,CEO,migrating platform to cloud,"
    b"hiring software engineers,fay@x.test,Remote,6,8,LinkedIn,https://x.test/6,2026-10-02,"
    b"Intro via Bo\n"
)
NO_TOTAL_CSV = (
    b"organization,need,intent_score,fit_score\n"
    b"Acme AI,backend engineer for LLM pipeline,8,9\n"
    b"Shopwise,web developer for checkout app,9,7\n"
    b"Sunrise Bakery,accountant for tax season,9,9\n"
)
QUESTION = "if I am a software engineer, which lead is the most hot for me?"


class Selector:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return ModelResponse(self.replies.pop(0), "fake-model", "fake")


def leads_view(content=LEADS_CSV):
    frame = pd.read_csv(io.BytesIO(content))
    columns = [
        {
            "name": name,
            "type": "integer" if str(frame[name].dtype).startswith("int") else "text",
            "role": "metric" if str(frame[name].dtype).startswith("int") else "dimension",
        }
        for name in frame.columns
    ]
    return dataset_view({"columns": columns})


@pytest.mark.parametrize(
    ("question", "persona", "for_me"),
    [
        (QUESTION, "software engineer", True),
        ("As a designer, which leads are the best fit?", "designer", False),
        ("Which lead is the best fit for me?", "", True),
        ("I'm a data scientist, show the top leads", "data scientist", False),
    ],
)
def test_goal_questions_are_recognised(question, persona, for_me):
    found = goal_question(question)
    assert found is not None and (found.persona, found.for_me) == (persona, for_me)


@pytest.mark.parametrize(
    "question",
    ["Top 3 categories by revenue", "What is the total revenue by region?", "Show me the data"],
)
def test_ordinary_questions_are_not_goal_rankings(question):
    assert goal_question(question) is None


def test_fields_scores_and_disclosed_default():
    view = leads_view()
    fields = ranking_fields(view)
    assert fields is not None
    assert fields.scores == ("total_score", "intent_score", "fit_score")
    assert fields.labels == ("organization",)
    assert fields.next_step == "next_step"
    assert "url" not in fields.texts and "contact" not in fields.texts
    default = choose_score(QUESTION, fields, view)
    assert (default.column, default.disclosed) == ("total_score", True)
    named = choose_score(QUESTION + " Rank by intent_score.", fields, view)
    assert (named.column, named.disclosed) == ("intent_score", False)
    sales = dataset_view({"columns": [{"name": "amount", "type": "integer", "role": "metric"}]})
    assert ranking_fields(sales) is None


def test_ambiguous_scores_without_a_total_offer_choices():
    view = leads_view(NO_TOTAL_CSV)
    fields = ranking_fields(view)
    choice = choose_score(QUESTION, fields, view)
    assert choice.column is None
    assert choice.choices == (
        "if I am a software engineer, which lead is the most hot for me? Rank by intent_score.",
        "if I am a software engineer, which lead is the most hot for me? Rank by fit_score.",
    )


def pandas_ranking(persona="software engineer", score="total_score"):
    frame = pd.read_csv(io.BytesIO(LEADS_CSV))
    keywords = persona_keywords(persona)
    texts = ["organization", "person", "role", "need", "evidence", "location", "source"]

    def hits(row):
        tokens = set(
            " ".join(str(row[name]) for name in texts).casefold().replace(",", " ").split()
        )
        tokens = {token.strip(".") for token in tokens}
        return {
            word
            for word in keywords
            if word in tokens or (len(word) >= 5 and any(t.startswith(word) for t in tokens))
        }

    frame["matches"] = frame.apply(lambda row: len(hits(row)), axis=1)
    kept = frame[frame["matches"] > 0]
    kept = kept.sort_values([score, "matches"], ascending=[False, False], kind="stable")
    return list(kept["organization"]), len(kept)


async def leads_thread(env, content=LEADS_CSV, model=None, interpretation=False, email=None):
    headers, actor = identity(env, email or f"{uuid4().hex[:8]}@example.test")
    wid = workspace(env, headers)
    created = env.client.post(
        f"/workspaces/{wid}/datasets", headers=headers, json={"name": "AI Leads — Master"}
    )
    did = created.json()["id"]
    response = upload(env, headers, wid, did, content, "leads.csv", "text/csv")
    assert response.status_code == 201, response.text
    model = model or Selector()
    router = IntentRouterService(
        model, env.runtime.analytics, context_enabled=True, interpretation_enabled=interpretation
    )
    threads = ThreadService(env.runtime.threads.uow, router)
    uid = UUID(response.json()["id"])
    thread = await threads.start_thread(actor, UUID(wid), UUID(did), uid)
    return headers, actor, UUID(wid), uid, model, threads, thread


@pytest.mark.asyncio
async def test_software_engineer_gets_the_hottest_matching_lead(integration):
    _, actor, wid, _, model, threads, thread = await leads_thread(integration)
    answer, turn = await threads.ask(actor, wid, thread.id, QUESTION)
    assert turn.status == "complete" and turn.model_route == ROUTE
    message = answer.message
    assert message.startswith(
        "As a software engineer, your hottest lead is Acme AI "
        "(total_score 92, intent_score 8, fit_score 9). Their need — "
        "“hiring backend engineer to build LLM pipeline”"
    )
    assert "Next step: “Email Bo about the pipeline”." in message
    order, kept = pandas_ranking()
    top = message.split("Top matches\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert [line.split(". ", 1)[1].split(" — ", 1)[0] for line in top] == order[:5]
    assert "Sunrise Bakery" not in message and "Pixel Studio" not in message
    assert f"I kept the {kept} of all 6 leads" in message
    assert "I read “hot” as highest total_score" in message
    assert answer.suggestions == (
        QUESTION.rstrip("?") + "? Rank by intent_score.",
        QUESTION.rstrip("?") + "? Rank by fit_score.",
    )
    assert model.requests == []
    answer, turn = await threads.ask(actor, wid, thread.id, answer.suggestions[0])
    assert turn.model_route == ROUTE
    assert "your hottest lead is Shopwise (intent_score 9" in answer.message
    order, _ = pandas_ranking(score="intent_score")
    assert order[0] == "Shopwise"


@pytest.mark.asyncio
async def test_unmatched_persona_asks_one_question_with_grounded_choices(integration):
    _, actor, wid, _, _, threads, thread = await leads_thread(integration)
    answer, turn = await threads.ask(
        actor, wid, thread.id, "As a pastry chef, which lead is best for me?"
    )
    assert answer is None and turn.kind == "ambiguous"
    assert turn.message.startswith("None of the 6 leads mention “pastry chef”")
    choices = turn.evidence["clarification"]["choices"]
    assert choices[0] == "As a software engineer, which leads are the best fit for me?"
    assert all(choice.startswith("As a ") for choice in choices)
    answer, turn = await threads.ask(actor, wid, thread.id, choices[0])
    assert turn.status == "complete" and "Acme AI" in answer.message


@pytest.mark.asyncio
async def test_for_me_asks_what_you_do_then_uses_saved_memory(integration):
    headers, actor, wid, _, _, threads, thread = await leads_thread(integration)
    answer, turn = await threads.ask(actor, wid, thread.id, "Which lead is the best fit for me?")
    assert answer is None and turn.message.startswith("What do you do?")
    assert turn.evidence["clarification"]["choices"]
    saved = integration.client.put(
        f"/workspaces/{wid}/agent-memory",
        headers=headers,
        json={"expected_version": 0, "role": "Backend developer"},
    )
    assert saved.status_code == 200, saved.text
    answer, turn = await threads.ask(actor, wid, thread.id, "Which lead is the best fit for me?")
    assert turn.status == "complete"
    assert answer.message.startswith("For you, your best-fit lead is Acme AI")


@pytest.mark.asyncio
async def test_ambiguous_scores_clarify_then_rank_by_the_chosen_score(integration):
    _, actor, wid, _, _, threads, thread = await leads_thread(integration, NO_TOTAL_CSV)
    answer, turn = await threads.ask(actor, wid, thread.id, QUESTION)
    assert answer is None and "Which one should decide what counts as hot" in turn.message
    choices = turn.evidence["clarification"]["choices"]
    answer, turn = await threads.ask(actor, wid, thread.id, choices[1])
    assert turn.status == "complete"
    assert answer.message.startswith(
        "As a software engineer, your hottest lead is Acme AI (fit_score 9, intent_score 8)"
    )
    assert "I read “hot”" not in answer.message


@pytest.mark.asyncio
async def test_model_may_suggest_columns_and_words_but_bad_replies_fall_back(integration):
    reply = json.dumps(
        {"score_column": "intent_score", "text_columns": ["need"], "keywords": ["checkout"]}
    )
    selector = Selector(reply, json.dumps({"score_column": "total_score", "keywords": ["9"]}))
    _, actor, wid, _, _, threads, thread = await leads_thread(
        integration, model=selector, interpretation=True
    )
    answer, turn = await threads.ask(actor, wid, thread.id, QUESTION)
    assert turn.model_route == "fake:fake-model:goal-ranking-v1"
    assert "your hottest lead is Shopwise (intent_score 9" in answer.message
    assert "whose need mention" in answer.message
    answer, turn = await threads.ask(actor, wid, thread.id, QUESTION)
    assert turn.model_route == ROUTE
    assert "your hottest lead is Acme AI (total_score 92" in answer.message
    assert len(selector.requests) == 2


def test_purpose_endpoint_shape_scoping_and_404(integration):
    headers, _ = identity(integration, "purpose@example.test")
    wid = workspace(integration, headers)
    did = integration.client.post(
        f"/workspaces/{wid}/datasets", headers=headers, json={"name": "AI Leads — Master"}
    ).json()["id"]
    uid = upload(integration, headers, wid, did, LEADS_CSV, "leads.csv", "text/csv").json()["id"]
    path = f"/workspaces/{wid}/uploads/{uid}/dataset-purpose"
    response = integration.client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "version",
        "summary",
        "benefits",
        "suggested_questions",
        "profile_question",
    }
    assert body["version"] == "dataset-purpose-v1"
    assert body["summary"].startswith("AI Leads — Master lists 6 leads.")
    assert body["suggested_questions"][0] == {
        "title": "Find the leads that best fit you",
        "question": "Which leads are the best fit for me?",
    }
    assert {"title", "question"} == set(body["suggested_questions"][1])
    assert body["suggested_questions"][1]["question"] == (
        "Which source has the highest average intent_score?"
    )
    assert body["profile_question"]["question"].startswith("What do you do?")
    assert body["profile_question"]["choices"][0] == "Software engineer"
    assert all(isinstance(text, str) for text in body["benefits"])
    missing = integration.client.get(
        f"/workspaces/{wid}/uploads/{uuid4()}/dataset-purpose", headers=headers
    )
    assert missing.status_code == 404
    outsider, _ = identity(integration, "outsider-purpose@example.test")
    assert integration.client.get(path, headers=outsider).status_code in {403, 404}
    assert integration.client.get(path).status_code == 401
