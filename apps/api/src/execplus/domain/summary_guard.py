"""Use case: Verifies a generated narrative only states executed evidence.

What it does: Rejects any summary that states a number absent from the supplied
evidence, so a management summary can never introduce an unverified figure.
"""

import re
from decimal import Decimal, InvalidOperation

_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# A leading "-" only counts as a sign when it is not itself glued to a preceding
# digit (e.g. the "-01" inside a date or an id like "SKU-1234"), so dates and
# similar compound tokens are not misread as extra, ungrounded numbers.
_NUMBER_PATTERN = re.compile(r"(?<!\d)-?\d[\d,]*\.?\d*")
_DEFAULT_TOLERANCE = Decimal("0.01")


def _parse(token: str) -> Decimal | None:
    cleaned = token.replace(",", "").strip(".")
    if not cleaned or cleaned == "-":
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def extract_numbers(text: str) -> tuple[Decimal, ...]:
    # Dates are labels, not business figures the guard needs to verify; stripping
    # them first prevents their digits from being read as unrelated numbers.
    without_dates = _ISO_DATE_PATTERN.sub(" ", text)
    values = (_parse(token) for token in _NUMBER_PATTERN.findall(without_dates))
    return tuple(value for value in values if value is not None)


def is_grounded(
    text: str, evidence: tuple[Decimal, ...], tolerance: Decimal = _DEFAULT_TOLERANCE
) -> bool:
    for number in extract_numbers(text):
        if not any(abs(number - value) <= tolerance for value in evidence):
            return False
    return True
