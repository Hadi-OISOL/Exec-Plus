"""Verify staged harness defaults, bounded recall hints and honest sample prompts."""

from uuid import uuid4

import pytest

from execplus.application.contracts import KnowledgeChunk
from execplus.config import Settings
from execplus.domain.data_brief import system_prompt
from execplus.domain.ingestion import IngestionError
from execplus.domain.jobs import ResourceBudget
from execplus.infrastructure.knowledge import ReferenceHybridRanker, discovery_terms


def test_harness_switches_default_to_legacy_paths():
    settings = Settings(_env_file=None)
    assert not settings.agent_context_enabled
    assert not settings.agent_orchestration_enabled
    assert not settings.agent_synthesis_enabled
    assert not settings.agent_retrieval_expansion_enabled
    assert ResourceBudget().max_queries == 1
    assert ResourceBudget(max_queries=2).max_queries == 2
    with pytest.raises(IngestionError):
        ResourceBudget(max_queries=3)


def test_sample_prompt_describes_only_the_actual_input_mode():
    without = system_prompt(None)
    with_samples = system_prompt({"columns": {"crop": ["fictional"]}, "rows": []})
    assert "do not see source row values" in without
    assert "example rows" not in without
    assert "example rows" in with_samples
    assert "never see row values" not in with_samples
    assert "do not see source row values" not in with_samples
    assert "Never state any number" in with_samples


def test_recall_expansion_is_optional_and_keeps_authorized_chunk_identity():
    wid, did = uuid4(), uuid4()
    authorized = KnowledgeChunk(uuid4(), wid, did, "Personnel handbook", {})
    unrelated = KnowledgeChunk(uuid4(), wid, did, "Crops growing", {})
    chunks = (authorized, unrelated)
    assert ReferenceHybridRanker().rank("employees", chunks, 5) == ()
    hits = ReferenceHybridRanker(expand_terms=True).rank("employees", chunks, 5)
    assert [hit.chunk for hit in hits] == [authorized]
    assert ReferenceHybridRanker(expand_terms=True).rank("employees", (), 5) == ()


def test_expansion_does_not_invent_column_aliases_or_transitive_knowledge():
    assert discovery_terms({"Soil_Moisture", "profit", "harvest"}) == set()
    assert "personnel" in discovery_terms({"employees"})
    assert "employees" not in discovery_terms({"employees"})


def test_direct_document_evidence_outranks_synonym_hint():
    wid, did = uuid4(), uuid4()
    direct = KnowledgeChunk(uuid4(), wid, did, "Employees", {})
    candidate = KnowledgeChunk(uuid4(), wid, did, "Personnel", {})
    hits = ReferenceHybridRanker(expand_terms=True).rank("employees", (candidate, direct), 5)
    assert [hit.chunk for hit in hits] == [direct, candidate]
