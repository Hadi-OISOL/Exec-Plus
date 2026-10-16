"""Use case: Keeps saved-answer PDF downloads exact and private.

What it does: Exercises real source replay and HTTP attachments, access revocation,
private audit evidence, historical definitions and render-time races.
"""

import asyncio
from io import BytesIO
from threading import Event
from uuid import UUID, uuid4

import pytest
from pypdf import PdfReader
from sqlalchemy import delete, select, update

from execplus.application.services.pdf_exports import PdfExportService
from execplus.domain.ingestion import IngestionError
from execplus.domain.pdf_exports import PdfDocument, PdfSection
from execplus.infrastructure.persistence import schema as s
from test_conversational_explorer import ScriptedModel
from test_dataset_guidance import ask
from test_studies import add_member, prepare
from test_understanding import confirm, context
from test_workspace_integration import identity, workspace


def setup(env, *, grouped=False):
    owner, actor, wid, _, _, root = prepare(env)
    tid = env.client.post(root + "/threads", headers=owner).json()["id"]
    path = f"/workspaces/{wid}/threads/{tid}"
    model = ScriptedModel(
        {
            "kind": "numerical",
            "plan": {
                "metric": "amount",
                "aggregation": "sum",
                "group_by": ["city"] if grouped else [],
            },
        }
    )
    env.runtime.intent_router.model = model
    answer = ask(env, owner, path, "Total amount by city?" if grouped else "Total amount?")
    assert answer["answer"] is not None, answer
    url = path + f"/turns/{answer['turn']['id']}/export.pdf"
    return owner, actor, wid, root, path, answer, url, model


def text_of(response):
    assert response.status_code == 200, response.text
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)


def exported_events(env):
    with env.engine.connect() as conn:
        return conn.execute(
            select(s.audit_events).where(s.audit_events.c.action == "pdf.exported")
        ).all()


@pytest.mark.parametrize("grouped", [False, True])
def test_download_has_exact_values_units_receipt_and_no_model_or_source_writes(
    integration, grouped
):
    env = integration
    owner, _, wid, root, path, answer, url, model = setup(env, grouped=grouped)
    before = context(env, owner, root)
    response = env.client.get(url, headers=owner)
    text = text_of(response)
    expected = ("0.100000000000", "0.200000000000") if grouped else ("0.300000000000",)
    assert all(value in text for value in expected)
    assert "PKR" in text and "execution-v1" in text
    assert "Current recorded source at generation" in text
    assert "Source evidence 1" in text and "source_checksum" in text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="execplus-answer-{answer["turn"]["id"]}.pdf"'
    )
    assert context(env, owner, root) == before and len(model.requests) == 1
    assert (
        env.client.get(path + f"/turns/{answer['turn']['id']}/answer", headers=owner).json()
        == answer["answer"]
    )
    assert len(exported_events(env)) == 1
    with env.engine.connect() as conn:
        assert len(conn.execute(select(s.query_executions)).all()) == 1
    member, _ = add_member(env, owner, wid, "admin")
    audit = env.client.get(f"/workspaces/{wid}/audit-history", headers=member)
    assert audit.status_code == 200, audit.text
    assert not any(row["action"] == "pdf.exported" for row in audit.json()["events"])
    owner_audit = env.client.get(f"/workspaces/{wid}/audit-history", headers=owner).json()
    assert any(row["action"] == "pdf.exported" for row in owner_audit["events"])


def test_member_owner_outsider_and_wrong_scope_cannot_download_anothers_answer(integration):
    env = integration
    owner, _, wid, root, _, _, url, _ = setup(env)
    member, member_actor = add_member(env, owner, wid, "admin")
    outsider, _ = identity(env, "pdf-outsider@example.test")
    other = workspace(env, outsider)
    for headers, target in [
        (member, url),
        (outsider, url),
        (outsider, url.replace(wid, other)),
        (owner, url.replace(url.rsplit("/", 2)[1], str(uuid4()))),
    ]:
        assert env.client.get(target, headers=headers).status_code in {403, 404}
    assert env.client.get(url).status_code == 401
    member_tid = env.client.post(root + "/threads", headers=member).json()["id"]
    member_path = f"/workspaces/{wid}/threads/{member_tid}"
    result = ask(env, member, member_path, "Help me understand this data")
    member_url = member_path + f"/turns/{result['turn']['id']}/export.pdf"
    assert env.client.get(member_url, headers=owner).status_code == 404
    assert env.client.get(member_url, headers=member).status_code == 200
    with env.engine.begin() as conn:
        conn.execute(delete(s.memberships).where(s.memberships.c.user_id == member_actor.id))
    assert env.client.get(member_url, headers=member).status_code == 404
    assert len(exported_events(env)) == 1


def test_qualitative_pdf_preserves_saved_explanation_and_historical_definitions(integration):
    env = integration
    owner, _, _, root, path, _, _, _ = setup(env)
    answer = ask(env, owner, path, "Help me understand this data")
    assert answer["answer"]["kind"] == "overview"
    current = context(env, owner, root)
    current["definition"]["description"] = "New definition that did not belong to the saved answer"
    assert confirm(env, owner, root, current).status_code == 201
    response = env.client.get(path + f"/turns/{answer['turn']['id']}/export.pdf", headers=owner)
    text = text_of(response)
    assert "saved qualitative explanation" in text and "Historical source snapshot" in text
    assert "New definition that did not belong" not in text
    assert " ".join(answer["answer"]["message"].split()) in " ".join(text.split())


def test_source_integrity_failure_is_not_exported_or_audited(integration):
    env = integration
    owner, _, _, root, _, _, url, _ = setup(env)
    uid = UUID(root.split("/")[-1])
    with env.engine.begin() as conn:
        conn.execute(update(s.uploads).where(s.uploads.c.id == uid).values(checksum="0" * 64))
    response = env.client.get(url, headers=owner)
    assert response.status_code == 409 and response.json()["error"]["code"] == "lineage_mismatch"
    assert not exported_events(env)


def test_source_definition_change_during_render_discards_bytes(integration, monkeypatch):
    env = integration
    owner, _, _, root, _, _, url, _ = setup(env)
    renderer = env.runtime.pdf_exports.renderer
    original = renderer.render
    current = context(env, owner, root)
    current["definition"]["description"] = "Changed while rendering"

    def change(document):
        value = original(document)
        assert confirm(env, owner, root, current).status_code == 201
        return value

    monkeypatch.setattr(renderer, "render", change)
    response = env.client.get(url, headers=owner)
    assert response.status_code == 409 and response.json()["error"]["code"] == "source_changed"
    assert not exported_events(env)


def test_revocation_during_render_prevents_download(integration, monkeypatch):
    env = integration
    owner, actor, _, _, _, _, url, _ = setup(env)
    renderer = env.runtime.pdf_exports.renderer
    original = renderer.render

    def revoke(document):
        value = original(document)
        with env.engine.begin() as conn:
            conn.execute(delete(s.memberships).where(s.memberships.c.user_id == actor.id))
        return value

    monkeypatch.setattr(renderer, "render", revoke)
    assert env.client.get(url, headers=owner).status_code == 404
    assert not exported_events(env)


def test_unsupported_and_incomplete_saved_answers_never_download(integration):
    env = integration
    owner, _, _, _, path, answer, url, _ = setup(env)
    diagram = ask(env, owner, path, "Draw a diagram")
    unsupported = env.client.get(path + f"/turns/{diagram['turn']['id']}/export.pdf", headers=owner)
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "pdf_export_unsupported"
    with env.engine.begin() as conn:
        conn.execute(
            update(s.thread_turns)
            .where(s.thread_turns.c.id == UUID(answer["turn"]["id"]))
            .values(status="failed")
        )
    response = env.client.get(url, headers=owner)
    assert response.status_code == 409
    assert not exported_events(env)


def test_cancelled_render_holds_slot_until_worker_finishes(monkeypatch):
    async def scenario():
        started, release = Event(), Event()

        class Renderer:
            def render(self, document):
                started.set()
                assert release.wait(5)
                return b"never delivered"

        service = PdfExportService(None, None, Renderer())
        source = PdfDocument("Fictional", None, (PdfSection("Source"),))

        async def prepare(*args):
            return source, ()

        monkeypatch.setattr(service, "_prepare", prepare)
        await service._render_slots.acquire()
        task = asyncio.create_task(service.download(None, uuid4(), uuid4(), uuid4()))
        try:
            assert await asyncio.to_thread(started.wait, 3)
            task.cancel()
            await asyncio.sleep(0)
            with pytest.raises(IngestionError) as failure:
                await service.download(None, uuid4(), uuid4(), uuid4())
            assert failure.value.code == "pdf_export_busy"
            assert not task.done()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            service._render_slots.release()
        assert not service._render_slots.locked()

    asyncio.run(scenario())
