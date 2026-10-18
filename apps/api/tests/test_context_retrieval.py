"""Use case: Checks bounded recall without model prose or persistent indexes.

What it does: Covers identifier matching, ambiguity, budgets and unrelated new tasks.
"""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from execplus.domain.context_retrieval import (
    references_earlier_result,
    retrieve_result,
    tokenize,
)
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.threads import ThreadTurn


def turn(question):
    return ThreadTurn(
        uuid4(), uuid4(), question, "numerical", uuid4(), None, datetime.now(timezone.utc)
    )


def test_tokenizer_ports_compounds_unicode_and_stopwords():
    assert tokenize("getUserId net_revenue THE 東京 Umsatz2") == (
        "get",
        "user",
        "id",
        "getuserid",
        "net",
        "revenue",
        "netrevenue",
        "東京",
        "umsatz2",
    )


def test_older_explicit_result_survives_six_recent_unrelated_turns():
    earlier = turn("total revenue North")
    turns = [earlier, *(turn("count records South") for _ in range(8))]
    assert retrieve_result("Explain earlier total revenue result", turns) == earlier


@pytest.mark.parametrize("question", ["total revenue", "Explain that simply", "only North"])
def test_new_or_implicit_task_never_triggers_retrieval(question):
    assert not references_earlier_result(question)
    with pytest.raises(ClarificationRequiredError):
        retrieve_result(question, [turn("total revenue")])


def test_ties_and_no_match_require_clarification():
    turns = [turn("total revenue North"), turn("total revenue South")]
    for question in ["Explain earlier revenue result", "Explain prior profit calculation"]:
        with pytest.raises(ClarificationRequiredError):
            retrieve_result(question, turns)


def test_distinguishing_scope_selects_unique_result():
    north, south = turn("total revenue North"), turn("total revenue South")
    assert retrieve_result("Explain earlier North revenue result", [north, south]) == north


def test_failed_pattern_and_model_prose_do_not_rank():
    good = turn("total revenue")
    failed = replace(turn("total revenue North"), status="failed")
    pattern = replace(turn("total revenue North"), evidence={"patterns": {"version": "v1"}})
    prose = replace(turn("count records"), message="total revenue North")
    assert retrieve_result("Explain earlier revenue result", [good, failed, pattern, prose]) == good


def test_character_and_item_budgets_fail_closed():
    target = turn("total revenue")
    with pytest.raises(ClarificationRequiredError):
        retrieve_result("Explain earlier revenue result", [target, turn("x" * 16001)])
    with pytest.raises(ClarificationRequiredError):
        retrieve_result(
            "Explain earlier revenue result", [target, *(turn("records") for _ in range(100))]
        )


def test_unmatched_condition_never_selects_a_broader_result():
    with pytest.raises(ClarificationRequiredError):
        retrieve_result("Explain earlier North revenue result", [turn("total revenue")])


@pytest.mark.parametrize("exclusion", ["not", "except", "excluding", "without", "don't use"])
def test_negative_reference_does_not_select_excluded_population(exclusion):
    with pytest.raises(ClarificationRequiredError):
        retrieve_result(
            f"Explain earlier revenue result {exclusion} North",
            [turn("total revenue North"), turn("total revenue South")],
        )
