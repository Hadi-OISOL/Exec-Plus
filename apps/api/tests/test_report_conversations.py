"""Use case: Makes explicit PDF requests act on the correct private saved answer.

What it does: Checks no-prior clarification, durable tool plans, exact reference reopening,
unsupported scope, owner boundaries and refusal to substitute an older answer.
"""

from sqlalchemy import select

from execplus.infrastructure.persistence import schema as s
from test_conversation_jobs import job_path, process, submit
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask
from test_pattern_conversations import setup
from test_studies import add_member


def test_pdf_request_without_previous_answer_asks_for_one(integration):
    env = integration
    owner, _, _, path = setup(env)
    result = ask(env, owner, path, "Make a PDF of this answer")
    assert result["answer"] is None and result["turn"]["kind"] == "ambiguous"
    assert "First ask a question" in result["turn"]["message"]


def test_pdf_job_references_previous_saved_answer_and_reopens_without_downloading(integration):
    env = integration
    owner, wid, _, path = setup(env)
    prior = ask(env, owner, path, "Help me understand this data")
    assert prior["answer"]["kind"] == "overview"
    job = submit(env, owner, path, "Make a PDF of this answer")
    assert process(env) == {"processed": 1}
    response = env.client.get(job_path(job) + "/result", headers=owner)
    assert response.status_code == 200, response.text
    result = response.json()
    answer = result["answer"]
    assert answer["kind"] == "report"
    assert answer["report"]["turn_id"] == prior["turn"]["id"]
    assert answer["report"]["download_url"] == path + f"/turns/{prior['turn']['id']}/export.pdf"
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=owner).json()
        == answer
    )
    repeated = ask(env, owner, path, "Make a PDF of the last answer")
    assert repeated["answer"] == answer
    assert (
        env.client.get(path + f"/turns/{prior['turn']['id']}/answer", headers=owner).json()
        == prior["answer"]
    )
    with env.engine.connect() as conn:
        plan = conn.execute(select(s.jobs.c.plan)).scalar_one()["value"]
        assert [step["operation"] for step in plan["steps"]] == [
            "export_report",
            "assemble_evidence",
        ]
        assert plan["steps"][0]["parameters"]["turn_id"] == prior["turn"]["id"]
        assert not conn.execute(
            select(s.audit_events).where(s.audit_events.c.action == "pdf.exported")
        ).first()
    member, _ = add_member(env, owner, wid, "admin")
    assert (
        env.client.get(path + f"/turns/{result['turn']['id']}/answer", headers=member).status_code
        == 404
    )
    assert env.client.get(answer["report"]["download_url"], headers=member).status_code == 404


def test_report_of_numeric_answer_keeps_original_exact_saved_target(integration):
    env = integration
    owner, _, _, path = setup(env)
    model = ScriptedModel({"kind": "numerical", "plan": {"metric": "amount", "aggregation": "sum"}})
    env.runtime.intent_router.model = model
    prior = ask(env, owner, path, "Total amount?")
    report = ask(env, owner, path, "Export this answer as PDF")
    assert report["answer"]["kind"] == "report"
    assert report["answer"]["report"]["turn_id"] == prior["turn"]["id"]
    assert len(model.requests) == 1
    assert (
        env.client.get(path + f"/turns/{prior['turn']['id']}/answer", headers=owner).json()
        == prior["answer"]
    )


def test_pdf_scope_clarifies_and_does_not_export_an_older_supported_answer(integration):
    env = integration
    owner, _, _, path = setup(env)
    ask(env, owner, path, "Help me understand this data")
    scope = ask(env, owner, path, "Make a PDF of all answers")
    assert scope["answer"] is None and scope["turn"]["kind"] == "ambiguous"
    latest = ask(env, owner, path, "Draw a diagram")
    assert latest["answer"]["kind"] == "diagram"
    refused = ask(env, owner, path, "Make a PDF of this answer")
    assert refused["answer"] is None and refused["turn"]["kind"] == "ambiguous"
    assert "diagrams" in refused["turn"]["message"]
