"""Use case: Finds an explicitly referenced earlier private calculation.

What it does: Ranks authorized question skeletons under a character budget; never
uses model prose or changes saved memory. Tokenizer ported from Trellis
104ee0b/packages/core/src/tokenize.ts, MIT, Copyright (c) 2026 Hadi Abbas.
See apps/web/public/third-party/trellis/LICENSE.txt.
"""

import re
import unicodedata
from collections.abc import Sequence

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.threads import ThreadTurn

_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "is",
        "it",
        "for",
        "on",
        "as",
        "at",
        "be",
        "by",
        "was",
        "are",
        "this",
        "that",
        "with",
        "from",
        "we",
        "you",
        "not",
        "but",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "its",
        "their",
        "they",
        "them",
        "so",
        "if",
        "then",
        "than",
        "when",
        "what",
        "which",
        "how",
        "why",
        "can",
        "could",
        "should",
        "would",
        "will",
        "may",
        "might",
        "must",
        "also",
        "into",
        "over",
        "about",
        "after",
        "before",
        "between",
        "during",
        "without",
        "within",
        "through",
        "use",
        "using",
        "used",
    ]
)
_REFERENCE_WORDS = frozenset(
    [
        "earlier",
        "previous",
        "prior",
        "result",
        "results",
        "calculation",
        "calculations",
        "answer",
        "answers",
        "explain",
        "show",
        "tell",
        "me",
        "again",
        "please",
        "simply",
        "return",
        "back",
        "revisit",
    ]
)


def tokenize(text: str) -> tuple[str, ...]:
    # Python's stdlib regex lacks Unicode property classes; retain L/N categories explicitly.
    normalized = "".join(
        char if char == "_" or unicodedata.category(char)[0] in "LN" else " " for char in text
    )
    out: list[str] = []
    for chunk in normalized.split():
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", chunk)
        split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", split)
        parts = [
            part
            for part in re.split(r"[_\s]+", split.lower())
            if len(part) >= 2 and part not in _STOPWORDS
        ]
        out.extend(parts)
        whole = chunk.lower().replace("_", "")
        if len(parts) > 1 and len(whole) >= 2 and whole not in _STOPWORDS:
            out.append(whole)
    return tuple(out)


def references_earlier_result(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:earlier|previous|prior)\b.{0,100}\b(?:results?|calculations?|answers?)\b"
            r"|\b(?:results?|calculations?|answers?)\b.{0,100}\b(?:earlier|previous|prior)\b",
            question,
            re.IGNORECASE,
        )
    )


def retrieve_result(question: str, authorized_turns: Sequence[ThreadTurn]) -> ThreadTurn:
    """Caller authorizes ownership/source access before passing any candidate.

    This index is disposable. Selection requires explicit recall and a unique
    lexical match; current sources and memory must still be checked after replay.
    """
    if not references_earlier_result(question):
        raise ClarificationRequiredError("Name the earlier calculation you want to revisit.")
    if re.search(
        r"\b(?:not|except|excluding|without|exclude|neither|nor)\b|n['\u2019]t\b",
        question,
        re.IGNORECASE,
    ):
        raise ClarificationRequiredError(
            "Name the earlier calculation you want to use, including its positive conditions."
        )
    terms = set(tokenize(question[:2000])) - _REFERENCE_WORDS
    remaining = 16000  # Hard character bound, not an estimated tokenizer guarantee.
    ranked: list[tuple[int, ThreadTurn]] = []
    for turn in reversed(authorized_turns[-100:]):
        if turn.status != "complete" or not turn.query_id or turn.evidence.get("patterns"):
            continue
        # Never rank a partial question: truncation could hide its distinguishing scope.
        if len(turn.question) > remaining:
            break
        remaining -= len(turn.question)
        score = len(terms & (set(tokenize(turn.question)) - _REFERENCE_WORDS))
        if score and score == len(terms):
            ranked.append((score, turn))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        raise ClarificationRequiredError(
            "Which earlier calculation do you mean? Name its measure and conditions."
        )
    return ranked[0][1]
