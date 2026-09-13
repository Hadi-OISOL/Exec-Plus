"""Use case: Verifies a generated summary is only accepted when fully evidence-grounded.

What it does: Proves numbers matching evidence pass and any unlisted number is rejected.
"""

from decimal import Decimal

from execplus.domain.summary_guard import extract_numbers, is_grounded


def test_extract_numbers_parses_integers_decimals_and_commas():
    assert extract_numbers("Revenue was 10,000 and cost was 2800.50.") == (
        Decimal("10000"),
        Decimal("2800.50"),
    )


def test_extract_numbers_ignores_non_numeric_text():
    assert extract_numbers("Revenue grew steadily across regions.") == ()


def test_is_grounded_accepts_numbers_present_in_evidence():
    text = "Total revenue reached 10000, up from 8000."
    evidence = (Decimal("10000"), Decimal("8000"))
    assert is_grounded(text, evidence)


def test_is_grounded_accepts_small_rounding_difference_within_tolerance():
    text = "Revenue was 10000.00."
    evidence = (Decimal("9999.999"),)
    assert is_grounded(text, evidence, tolerance=Decimal("0.01"))


def test_is_grounded_rejects_a_number_absent_from_evidence():
    text = "Revenue reached 999999."
    evidence = (Decimal("10000"),)
    assert not is_grounded(text, evidence)


def test_is_grounded_true_for_text_with_no_numbers():
    assert is_grounded("Revenue grew across all regions.", (Decimal("10000"),))


def test_extract_numbers_ignores_dates_embedded_in_the_text():
    text = (
        "Total revenue is 10000, while cost is 2800. Figures were 400 on 2026-01-01, "
        "800 on 2026-02-01, and 1600 on 2026-04-01."
    )
    assert extract_numbers(text) == (
        Decimal("10000"),
        Decimal("2800"),
        Decimal("400"),
        Decimal("800"),
        Decimal("1600"),
    )


def test_is_grounded_accepts_a_real_summary_that_repeats_dates():
    text = (
        "Total revenue is 10000, while cost is 2800 under the Services category. The "
        "date-by-date figures are 400 on 2026-01-01, 800 on 2026-02-01, and 1600 on "
        "2026-04-01."
    )
    evidence = (Decimal("10000"), Decimal("2800"), Decimal("400"), Decimal("800"), Decimal("1600"))
    assert is_grounded(text, evidence)


def test_extract_numbers_still_reads_a_negative_number_not_glued_to_a_date():
    assert extract_numbers("Revenue fell by -19 versus last month.") == (Decimal("-19"),)
