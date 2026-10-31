"""Use case: Proves the onboarding profile is validated, actor-private and advisory only.

What it does: Covers questionnaire validation, merged memory context, /me/profile versions,
isolation between users, forget, greeting by name and unchanged saved answers.
"""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from execplus.domain.agent_memory import MEMORY_PROMPT, AgentMemory
from execplus.domain.ingestion import IngestionError
from execplus.domain.user_profile import QUESTIONNAIRE, UserProfile, validate_answers
from execplus.infrastructure.persistence import schema as s
from test_agent_memory import evidence
from test_dataset_guidance import ask
from test_dataset_reading import READING, prepare
from test_unified_conversation import setup
from test_workspace_integration import identity

ANSWERS = {
    "role": "Analyst",
    "industry": "Retail",
    "goals": ["Track KPIs", "Forecast", "Track KPIs"],
    "language": "English",
    "regions_currency": "  Pakistan, PKR  ",
}


def save(env, headers, version=0, **changes):
    body = {"expected_version": version, "preferred_name": "Hadi", "answers": ANSWERS, **changes}
    return env.client.put("/me/profile", headers=headers, json=body)


def test_questionnaire_is_fixed_and_answers_are_validated():
    assert 16 <= len(QUESTIONNAIRE) <= 20
    assert {q.kind for q in QUESTIONNAIRE} == {"text", "single", "multi"}
    kept = validate_answers(ANSWERS)
    assert kept["goals"] == ["Track KPIs", "Forecast"]
    assert kept["regions_currency"] == "Pakistan, PKR"
    assert validate_answers({"goals": [], "anything_else": "  "}) == {}
    for bad in (
        {"unknown": "x"},
        {"preferred_name": "Hadi"},
        {"role": "Hacker"},
        {"goals": "Forecast"},
        {"goals": ["Forecast", "Fly"]},
        {"anything_else": "x" * 121},
        {"anything_else": "bad\x00"},
        ["role"],
    ):
        with pytest.raises(IngestionError):
            validate_answers(bad)


def test_profile_context_merges_into_memory_without_changing_empty_memory():
    uid = uuid4()
    empty = AgentMemory(uuid4(), uid, profile=UserProfile(uid))
    assert empty.context() == {} and "profile_version" not in empty.reference()
    profile = UserProfile(uid, 2, "Hadi", {**validate_answers(ANSWERS), "next_steps": "Yes"})
    memory = AgentMemory(uuid4(), uid, 1, "Owner", "", "concise", profile=profile)
    assert memory.context() == {
        "role": "Owner",
        "focus": "",
        "explanation_style": "concise",
        "profile": {
            "preferred_name": "Hadi",
            "role": "Analyst",
            "industry": "Retail",
            "goals": ["Track KPIs", "Forecast"],
            "language": "English",
        },
    }
    assert memory.reference()["profile_version"] == 2
    assert "Never use profile answers for numbers" in MEMORY_PROMPT


def test_profile_is_versioned_actor_private_and_forgettable(integration):
    env = integration
    owner, user = identity(env, "profile-owner@example.test")
    other, _ = identity(env, "profile-other@example.test")
    assert env.client.get("/me/profile").status_code == 401
    pending = env.client.get("/me/profile", headers=owner).json()
    assert pending["status"] == "pending" and pending["version"] == 0
    assert pending["questionnaire"][0]["id"] == "preferred_name"
    saved = save(env, owner)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["status"] == "completed" and body["version"] == 1
    assert body["preferred_name"] == "Hadi" and body["user_id"] == str(user.id)
    assert body["answers"]["goals"] == ["Track KPIs", "Forecast"]
    assert save(env, owner).status_code == 409
    assert save(env, owner, version=1, answers={"role": "Hacker"}).status_code == 422
    assert save(env, owner, version=1, extra="x").status_code == 422
    assert env.client.get("/me/profile", headers=owner).json()["version"] == 1
    theirs = env.client.get("/me/profile", headers=other).json()
    assert theirs["status"] == "pending" and theirs["answers"] == {}
    skipped = save(env, other, status="skipped", answers={"role": "Manager"}).json()
    assert skipped["status"] == "skipped" and skipped["completed_at"] is None
    assert env.client.get("/me/profile", headers=owner).json()["preferred_name"] == "Hadi"
    forgotten = env.client.delete("/me/profile?expected_version=1", headers=owner)
    assert forgotten.status_code == 200, forgotten.text
    assert forgotten.json() == {
        **forgotten.json(),
        "status": "pending",
        "version": 2,
        "preferred_name": "",
        "answers": {},
    }
    with env.engine.connect() as connection:
        events = connection.execute(
            select(s.account_events).where(s.account_events.c.action.like("profile.%"))
        ).fetchall()
    assert sorted(event.action for event in events) == [
        "profile.completed",
        "profile.forgotten",
        "profile.skipped",
    ]
    assert "Pakistan" not in str(events) and "Hadi" not in str(events)


def test_profile_reaches_prompt_and_greeting_but_never_rewrites_saved_answers(integration):
    env = integration
    owner, _wid, _root, path, model = prepare(env, READING, READING)
    assert save(env, owner).status_code == 200
    first = ask(env, owner, path, "Help me understand this data")
    prompt = json.loads(model.requests[-1].messages[-1].content)
    assert prompt["personal_memory"] == {
        "profile": {
            "preferred_name": "Hadi",
            "role": "Analyst",
            "industry": "Retail",
            "goals": ["Track KPIs", "Forecast"],
            "language": "English",
        }
    }
    assert MEMORY_PROMPT in model.requests[-1].messages[0].content
    turn_id = first["turn"]["id"]
    assert evidence(env, turn_id)["agent_memory"] == {
        "version": 0,
        "updated_at": None,
        "profile_version": 1,
    }
    assert "Pakistan" not in json.dumps(evidence(env, turn_id))
    answer_path = path + f"/turns/{turn_id}/answer"
    assert env.client.get(answer_path, headers=owner).json() == first["answer"]
    assert save(env, owner, version=1, preferred_name="H.").status_code == 200
    replay = env.client.get(answer_path, headers=owner)
    assert replay.status_code == 200 and replay.json() == first["answer"]
    assert evidence(env, turn_id)["agent_memory"]["profile_version"] == 1
    second = ask(env, owner, path, "Help me understand this data")
    assert evidence(env, second["turn"]["id"])["agent_memory"]["profile_version"] == 2
    assert (
        json.loads(model.requests[-1].messages[-1].content)["personal_memory"]["profile"][
            "preferred_name"
        ]
        == "H."
    )
    with env.engine.connect() as connection:
        assert connection.execute(select(s.query_executions)).first() is None


def test_offline_greeting_uses_preferred_name(integration):
    env = integration
    owner, _wid, _root, path, _model = setup(env)
    assert ask(env, owner, path, "hello")["answer"]["message"].startswith("Hey! ")
    assert save(env, owner).status_code == 200
    assert ask(env, owner, path, "hello")["answer"]["message"].startswith("Hey, Hadi! ")
