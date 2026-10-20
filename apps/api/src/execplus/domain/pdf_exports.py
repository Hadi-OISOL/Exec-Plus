"""Use case: Describes bounded PDF exports of existing authorized answers.

What it does: Defines immutable download actions and exact report content without
accepting HTML, file paths, model calculations or external rendering resources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from execplus.domain.ingestion import IngestionError

if TYPE_CHECKING:
    from execplus.domain.exports import ExportChart

MAX_PDF_ROWS = 1_000
MAX_PDF_COLUMNS = 20
MAX_PDF_CHARACTERS = 250_000
MAX_PDF_PAGES = 100
MAX_PDF_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ReportAnswer:
    thread_id: UUID
    turn_id: UUID
    label: str
    download_url: str
    format: str = "pdf"
    kind: str = "report"


@dataclass(frozen=True, slots=True)
class PdfTable:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class PdfSection:
    title: str
    paragraphs: tuple[str, ...] = ()
    table: PdfTable | None = None


@dataclass(frozen=True, slots=True)
class PdfDocument:
    title: str
    generated_at: datetime
    sections: tuple[PdfSection, ...]
    charts: tuple[ExportChart, ...] = ()


@dataclass(frozen=True, slots=True)
class PdfDownload:
    filename: str
    content: bytes


def wants_pdf_export(question: str) -> bool:
    text = " ".join(question.casefold().split())
    if text in {"pdf", "pdf please", "pdf report"}:
        return True
    return bool(
        re.search(r"\bpdf\b", text)
        and re.search(
            r"\b(make|create|generate|export|download|save|give|turn|convert|"
            r"want|need|get|prepare|print)\b",
            text,
        )
    )


def validate_pdf_export_request(question: str) -> None:
    allowed = {
        "a",
        "an",
        "the",
        "me",
        "pdf",
        "report",
        "file",
        "of",
        "for",
        "from",
        "this",
        "that",
        "last",
        "latest",
        "above",
        "answer",
        "result",
        "as",
        "to",
        "into",
        "in",
        "please",
        "make",
        "create",
        "generate",
        "export",
        "download",
        "save",
        "give",
        "turn",
        "convert",
        "can",
        "could",
        "would",
        "you",
        "downloadable",
        "i",
        "want",
        "need",
        "get",
        "prepare",
        "print",
        "your",
        "my",
        "our",
        "thanks",
        "thank",
        "kindly",
        "it",
    }
    if set(re.findall(r"\w+", question.casefold())) - allowed:
        raise IngestionError(
            "pdf_export_scope",
            "I can make a PDF of the latest answer in this conversation. "
            "For another answer, open it and use its Download PDF button. "
            "Whole-conversation and full-dataset reports are not available yet.",
            422,
        )


def document_text(document: PdfDocument) -> tuple[str, ...]:
    values = [document.title]
    for section in document.sections:
        values.append(section.title)
        values.extend(section.paragraphs)
        if section.table:
            values.extend(section.table.columns)
            for row in section.table.rows:
                values.extend(row)
    return tuple(values)


def validate_document(document: PdfDocument) -> None:
    validate_report_time(document.generated_at)
    for section in document.sections:
        table = section.table
        if table and (
            not table.columns
            or len(table.columns) > MAX_PDF_COLUMNS
            or len(table.rows) > MAX_PDF_ROWS
            or any(len(row) != len(table.columns) for row in table.rows)
        ):
            raise IngestionError(
                "pdf_export_limit",
                "This answer is too wide or long for a PDF. Export supports up to "
                "1,000 returned rows and 20 columns; choose a smaller saved answer.",
                422,
            )
    text = document_text(document)
    if sum(map(len, text)) > MAX_PDF_CHARACTERS:
        raise IngestionError(
            "pdf_export_limit",
            "This answer contains too much text for a PDF. Choose a smaller saved answer.",
            422,
        )
    if any(any(ord(char) < 32 and char != "\n" for char in value) for value in text):
        raise IngestionError(
            "pdf_export_text",
            "This answer includes control characters that the PDF cannot display safely. "
            "The exact saved answer remains available.",
            422,
        )


def validate_report_time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise IngestionError(
            "export_metadata", "The report timestamp must include its time zone.", 422
        )
