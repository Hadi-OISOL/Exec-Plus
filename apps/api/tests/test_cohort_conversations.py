"""Real source projection, private replay, follow-up context and portable outputs."""

from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select, update

from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask
from test_result_exports import download_text
from test_studies import add_member, prepare
from test_understanding import context


def setup(env):
    content = b"stage,reading,crop\n" + b"Ready,2,A\n" * 10 + b"Growing,4,B\n" * 20
    owner, _actor, wid, _did, _uid, root = prepare(env, content, domain="research")
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    return owner, wid, root, f"/workspaces/{wid}/threads/{tid}"


def compare(env, owner, path):
    result = ask(
        env, owner, path, 'Compare records where "stage" equals "Ready" with other records'
    )
    assert result["answer"] is not None, result
    assert result["answer"]["kind"] == "patterns"
    return result


def test_canonical_comparison_replays_exactly_and_keeps_member_private(integration):
    env = integration
    owner, wid, root, path = setup(env)
    before = context(env, owner, root)
    result = compare(env, owner, path)
    answer = result["answer"]
    assert answer["patterns"]["coverage"]["target_rows"] == 10
    assert answer["patterns"]["numeric"][0]["difference"] == "-2"
    url = path + f"/turns/{result['turn']['id']}/answer"
    assert env.client.get(url, headers=owner).json() == answer
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404
    assert context(env, owner, root) == before


@pytest.mark.parametrize("format", ["pdf", "xlsx", "csv"])
def test_comparison_download_matches_saved_values_and_denies_other_actor(integration, format):
    env = integration
    owner, wid, _, path = setup(env)
    result = compare(env, owner, path)
    url = path + f"/turns/{result['turn']['id']}/export.{format}"
    text = download_text(env.client.get(url, headers=owner), format)
    assert "Ready" in text and "reading" in text and "-2" in text
    member, _ = add_member(env, owner, wid, "admin")
    assert env.client.get(url, headers=member).status_code == 404


def test_target_context_survives_followup_without_sending_raw_rows(integration):
    env = integration
    owner, _, _, path = setup(env)
    compare(env, owner, path)
    model = ScriptedModel(
        {
            "kind": "cohort_comparison",
            "target_column": "stage",
            "target_value": "Ready",
            "columns": ["reading"],
        }
    )
    env.runtime.intent_router.model = model
    result = ask(env, owner, path, "What differs for those records?")
    assert result["answer"]["patterns"]["target"]["value"] == "Ready", result
    assert model.requests
    prompt = model.requests[-1].messages[-1].content
    assert "Ready" in prompt and "target_column" in prompt
    assert "Ready,2,A" not in prompt


def test_saved_comparison_tamper_refuses_replay(integration):
    env = integration
    owner, _, _, path = setup(env)
    result = compare(env, owner, path)
    tid = UUID(result["turn"]["id"])
    with env.engine.begin() as conn:
        evidence = deepcopy(
            conn.execute(
                select(s.thread_turns.c.evidence).where(s.thread_turns.c.id == tid)
            ).scalar_one()
        )
        evidence["patterns"]["result"]["coverage"]["target_rows"] = 999
        conn.execute(
            update(s.thread_turns).where(s.thread_turns.c.id == tid).values(evidence=evidence)
        )
    assert env.client.get(path + f"/turns/{tid}/answer", headers=owner).status_code == 409
