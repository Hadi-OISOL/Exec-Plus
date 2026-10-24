"""Use case: Summarises a free-text survey or feedback column without inventing themes (D16).

What it does: Picks the text field a question is about and counts, from exact grouped
response counts, how many responses mention each frequent word and two-word phrase, with
stop words removed and Urdu script / Roman Urdu tolerated. Counts are not sentiment or causes.
"""

import re
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise

from execplus.domain.guidance import mentioned_columns, words
from execplus.domain.models import Scalar
from execplus.domain.semantics import DatasetView

FREE_TEXT_ROUTE = "deterministic:free-text-summary-v1"

_TEXT_NAME_WORDS = frozenset(
    {
        "comment",
        "comments",
        "feedback",
        "review",
        "reviews",
        "complaint",
        "complaints",
        "remark",
        "remarks",
        "note",
        "notes",
        "response",
        "responses",
        "reason",
        "suggestion",
        "suggestions",
        "opinion",
        "text",
        "verbatim",
        "description",
        "issue",
        "issues",
        "message",
    }
)

_STOP_TEXT = (
    "a an the and or but if then so of to in on at by for with from as is are was were be been "
    "being it its this that these those there here i me my we our you your he she they them "
    "their his her what which who whom how when where why do does did done have has had having "
    "will would can could should shall may might must am very really just also too more most "
    "some any all much many such than only own same other about into over after before again "
    "up down out off once get got lot lots one ok okay etc "
    "hai hain ha ka ki ke ko se mein me main aur bhi ye yeh wo woh tha thi the tou to ap aap "
    "hum ham mera meri mere apna apni kya ek par pe ne raha rahi rahe hota hoti hote kar karna "
    "کا کی کے کو سے میں اور بھی یہ وہ تھا تھی تھے پر نے ہے ہیں ہو تو ایک کیا"
)
STOP_WORDS = frozenset(_STOP_TEXT.split())

_MARKS = re.compile("[ً-ٰٟۖ-ۭ]")
_LETTERS = str.maketrans(
    {
        "\u064a": "\u06cc",
        "\u0649": "\u06cc",
        "\u0643": "\u06a9",
        "\u0647": "\u06c1",
        "\u0629": "\u06c1",
    }
)


def tokens(text: str) -> list[str]:
    normalized = _MARKS.sub("", text.casefold()).translate(_LETTERS)
    found = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", normalized)
    return [token for token in found if len(token) > 1 and token not in STOP_WORDS]


def free_text_column(question: str, view: DatasetView) -> str | None:
    """The named text field, else the one field whose name says it holds written responses."""
    text_fields = [
        column.name
        for column in view.columns
        if column.type == "text"
        and column.name in view.dimensions
        and "identifier" not in column.tags
    ]
    named = [name for name in mentioned_columns(question, view) if name in text_fields]
    if named:
        return named[0]
    hinted = [name for name in text_fields if _TEXT_NAME_WORDS & set(words(name).split())]
    return hinted[0] if len(hinted) == 1 else None


@dataclass(frozen=True, slots=True)
class FreeTextSummary:
    column: str
    responses: int
    records: int
    distinct: int
    written_words: int
    top_words: tuple[tuple[str, int], ...]
    top_phrases: tuple[tuple[str, int], ...]
    examples: tuple[tuple[str, int], ...]


def summarise(
    column: str, rows: tuple[tuple[Scalar, ...], ...], records: int, limit: int = 10
) -> FreeTextSummary:
    """Rows are (response text, exact number of records with that text)."""
    word_counts: Counter[str] = Counter()
    phrase_counts: Counter[str] = Counter()
    answered: list[tuple[str, int]] = []
    written = 0
    for value, count in rows:
        text = "" if value is None else str(value).strip()
        if not text or not isinstance(count, int):
            continue
        answered.append((text, count))
        written += len(text.split()) * count
        found = tokens(text)
        for token in set(found):
            word_counts[token] += count
        for phrase in {f"{a} {b}" for a, b in pairwise(found)}:
            phrase_counts[phrase] += count

    def ranked(counter: Counter[str], minimum: int) -> tuple[tuple[str, int], ...]:
        ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        return tuple(item for item in ordered if item[1] >= minimum)[:limit]

    examples = sorted(answered, key=lambda item: (-item[1], -len(item[0]), item[0]))[:3]
    return FreeTextSummary(
        column,
        sum(count for _, count in answered),
        records,
        len(answered),
        written,
        ranked(word_counts, 1),
        ranked(phrase_counts, 2)[:5],
        tuple((text[:160] + ("…" if len(text) > 160 else ""), count) for text, count in examples),
    )


def is_free_text(summary: FreeTextSummary) -> bool:
    """Written answers, not a short category label: varied and two or more words on average."""
    return summary.distinct > 1 and summary.written_words >= 2 * summary.responses


def summary_message(
    summary: FreeTextSummary, dataset: str, truncated: bool, documents: bool
) -> str:
    def counted(items: tuple[tuple[str, int], ...]) -> str:
        return "\n".join(
            f"{index}. {text} — {count} response{'s' if count != 1 else ''}"
            for index, (text, count) in enumerate(items, 1)
        )

    scope = (
        f"the first {summary.distinct:,} different answers in {summary.column}"
        if truncated
        else f"{summary.responses:,} written answers in {summary.column}"
        f" (of {summary.records:,} records in {dataset})"
    )
    parts = [
        ("I counted" if documents else "There are no documents to search here, so I counted")
        + f" words in {scope}. "
        "These are exact word counts from the rows, not sentiment, themes or causes."
    ]
    if summary.top_words:
        parts.append("Most frequent words (number of answers that use each word)\n")
        parts[-1] += counted(summary.top_words)
    if summary.top_phrases:
        parts.append("Common two-word phrases\n" + counted(summary.top_phrases))
    if summary.examples:
        parts.append(
            "Example answers\n"
            + "\n".join(
                f'- "{text}"' + (f" ({count} times)" if count > 1 else "")
                for text, count in summary.examples
            )
        )
    if not summary.top_words:
        parts.append(f"{summary.column} has no written answers to count.")
    return "\n\n".join(parts)
