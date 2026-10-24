"""Use case: Preserves literal saved evidence in bounded printable documents.

What it does: Exercises real PDF generation, pagination, text coverage, hostile markup,
font coverage and explicit limits without invoking a model or a network renderer.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from threading import Lock

import pytest
from pypdf import PdfReader

from execplus.domain.ingestion import IngestionError
from execplus.domain.pdf_exports import (
    PdfDocument,
    PdfSection,
    PdfTable,
    validate_document,
    validate_pdf_export_request,
    wants_pdf_export,
)
from execplus.infrastructure.exports import reportlab_pdf
from execplus.infrastructure.exports.reportlab_pdf import ReportLabPdfRenderer


def document(table=None, text="Fictional saved evidence"):
    return PdfDocument(
        "Syntelio - saved answer",
        datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc),
        (PdfSection("Exact values", (text,), table),),
    )


def read_pdf(value):
    assert value.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(value))
    return reader, "\n".join(page.extract_text() for page in reader.pages)


def test_every_returned_row_survives_real_pdf_pagination_with_repeated_headers():
    rows = tuple((f"UniqueRecord{i:04}", f"9007199254740993.{i:012}") for i in range(1000))
    reader, text = read_pdf(
        ReportLabPdfRenderer().render(document(PdfTable(("Record", "Exact amount"), rows)))
    )
    assert len(reader.pages) > 20
    for page in reader.pages:
        page_text = page.extract_text()
        assert "Record" in page_text and "Exact amount" in page_text
        assert "Syntelio | Page" in page_text
    for label, amount in rows:
        assert label in text and amount in text


def test_wide_tables_keep_all_columns_and_same_original_row_numbers():
    columns = tuple(f"Column{i:02}" for i in range(20))
    rows = tuple(tuple(f"R{r:02}C{c:02}" for c in range(20)) for r in range(12))
    _, text = read_pdf(ReportLabPdfRenderer().render(document(PdfTable(columns, rows))))
    for value in (*columns, *(cell for row in rows for cell in row)):
        assert value in text
    assert "Columns 1-5 of 20" in text and "Columns 16-20 of 20" in text


def test_long_single_cell_splits_without_silent_truncation():
    words = [f"Word{i:04}" for i in range(1200)]
    reader, text = read_pdf(
        ReportLabPdfRenderer().render(document(PdfTable(("Description",), ((" ".join(words),),))))
    )
    assert len(reader.pages) > 1
    for word in words:
        assert word in text
    assert all("Description" in page.extract_text() for page in reader.pages)


def test_multiple_and_edge_spaces_in_source_strings_remain_distinguishable():
    _, text = read_pdf(
        ReportLabPdfRenderer().render(
            document(PdfTable(("Category",), (("  North  Region  ",), ("North Region",))))
        )
    )
    assert "  North  Region  " in text and "\nNorth Region\n" in text


def test_concurrent_exports_do_not_share_mutable_font_state_or_document_text(monkeypatch):
    original = reportlab_pdf.SimpleDocTemplate.build
    guard = Lock()
    active, maximum = 0, 0

    def monitored(template, *args, **kwargs):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        try:
            time.sleep(0.02)
            return original(template, *args, **kwargs)
        finally:
            with guard:
                active -= 1

    monkeypatch.setattr(reportlab_pdf.SimpleDocTemplate, "build", monitored)
    labels = ("PrivateAlpha Café", "PrivateBeta Ελληνικά", "PrivateGamma Москва", "PrivateDelta €")
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(
            pool.map(lambda text: ReportLabPdfRenderer().render(document(text=text)), labels)
        )
    for label, output in zip(labels, outputs, strict=True):
        _, text = read_pdf(output)
        assert label in text
        assert all(other not in text for other in labels if other != label)
    assert maximum == 1


def test_literal_markup_null_zero_and_supported_unicode_are_preserved_without_links():
    literal = '<img src="https://example.test/secret"/> <b>literal</b> & <a href="file:///etc/passwd">x</a>'
    rows = (("0", "Missing (null)", "-0.000000000001"),)
    reader, text = read_pdf(
        ReportLabPdfRenderer().render(
            document(
                PdfTable(("Zero", "Absent", "Decimal"), rows), literal + " Café Ελληνικά Москва €"
            )
        )
    )
    normalized = " ".join(text.split())
    assert literal in normalized
    assert "Café Ελληνικά Москва €" in normalized
    assert "Missing (null)" in text and "-0.000000000001" in text
    assert all(not page.get("/Annots") for page in reader.pages)
    assert "/JavaScript" not in str(reader.trailer)
    assert any(
        "/FontFile2" in font.get_object().get("/FontDescriptor", {})
        for page in reader.pages
        for font in page["/Resources"]["/Font"].values()
    )


@pytest.mark.parametrize("text", ["中文", "emoji 😀", "line\tcolumn", "escape\x00"])
def test_unsupported_text_is_refused_instead_of_replaced(text):
    with pytest.raises(IngestionError) as failure:
        ReportLabPdfRenderer().render(document(text=text))
    assert failure.value.code == "pdf_export_text" and failure.value.status == 422


@pytest.mark.parametrize(
    "table",
    [
        PdfTable(("x",), (("1",),) * 1001),
        PdfTable(("x",) * 21, ()),
        PdfTable(("x",), (("1", "2"),)),
    ],
)
def test_oversized_or_malformed_tables_are_not_truncated(table):
    with pytest.raises(IngestionError, match="PDF") as failure:
        validate_document(document(table))
    assert failure.value.code == "pdf_export_limit"


def test_text_page_and_byte_limits_refuse_whole_export(monkeypatch):
    renderer = ReportLabPdfRenderer()
    with pytest.raises(IngestionError) as failure:
        renderer.render(document(text="x" * 250001))
    assert failure.value.code == "pdf_export_limit"
    monkeypatch.setattr(reportlab_pdf, "MAX_PDF_PAGES", 1)
    with pytest.raises(IngestionError) as failure:
        renderer.render(document(PdfTable(("row",), tuple((str(i),) for i in range(100)))))
    assert failure.value.code == "pdf_export_limit"
    monkeypatch.setattr(reportlab_pdf, "MAX_PDF_BYTES", 20)
    with pytest.raises(IngestionError) as failure:
        renderer.render(document())
    assert failure.value.code == "pdf_export_limit"


@pytest.mark.parametrize(
    "question",
    [
        "make a PDF",
        "Please export this answer as PDF",
        "PDF",
        "Create a PDF of the latest answer",
        "I want a PDF of this answer",
        "Can I get a PDF?",
        "prepare a PDF please",
        "make a PDF of your answer thanks",
        "export as PDF",
    ],
)
def test_explicit_latest_answer_pdf_requests_are_bounded(question):
    assert wants_pdf_export(question)
    validate_pdf_export_request(question)


@pytest.mark.parametrize(
    "question",
    [
        "Make a PDF of all answers",
        "Export the first answer as PDF",
        "Make a PDF of the full dataset",
        "make a PDF excluding costs",
    ],
)
def test_other_scope_cannot_silently_become_latest_answer(question):
    assert wants_pdf_export(question)
    with pytest.raises(IngestionError) as failure:
        validate_pdf_export_request(question)
    assert failure.value.code == "pdf_export_scope"
