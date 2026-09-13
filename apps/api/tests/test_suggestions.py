"""Use case: Verifies starter questions are derived deterministically from a profile.

What it does: Proves suggestions come only from KPI matches and recommended dimensions.
"""

from execplus.domain.semantics import dataset_view
from execplus.domain.suggestions import suggested_questions


def finance_view():
    return dataset_view(
        {
            "columns": [
                {"name": "date", "type": "date", "role": "dimension", "semantic_tags": ["date"]},
                {"name": "category", "type": "text", "role": "dimension", "semantic_tags": []},
                {
                    "name": "revenue",
                    "type": "decimal",
                    "role": "metric",
                    "semantic_tags": ["revenue"],
                },
            ]
        }
    )


def test_suggested_questions_includes_kpi_and_trend_and_breakdown():
    questions = suggested_questions(finance_view())
    assert "What is the total revenue?" in questions
    assert any("changed over date" in question for question in questions)
    assert any("by category" in question for question in questions)


def test_suggested_questions_is_deterministic():
    assert suggested_questions(finance_view()) == suggested_questions(finance_view())


def test_suggested_questions_respects_limit():
    assert len(suggested_questions(finance_view(), limit=1)) == 1


def test_suggested_questions_empty_for_dataset_without_matches():
    empty = dataset_view({"columns": [{"name": "notes", "type": "text", "role": "dimension"}]})
    assert suggested_questions(empty) == ()
