"""Use case: Updates the existing VC feature report after verified deliveries.

What it does: Preserves its sections and styles while rebuilding dated evidence and
64-item counts from the maintained audit; python-docx is optional report tooling.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
from collections import Counter
from importlib import import_module
from pathlib import Path
from typing import Any


def build_report(audit_path: Path, output: Path) -> None:
    Document = import_module("docx").Document
    WD_TABLE_ALIGNMENT = import_module("docx.enum.table").WD_TABLE_ALIGNMENT
    WD_CELL_VERTICAL_ALIGNMENT = import_module("docx.enum.table").WD_CELL_VERTICAL_ALIGNMENT
    WD_ALIGN_PARAGRAPH = import_module("docx.enum.text").WD_ALIGN_PARAGRAPH
    OxmlElement = import_module("docx.oxml").OxmlElement
    qn = import_module("docx.oxml.ns").qn
    Inches = import_module("docx.shared").Inches
    Pt = import_module("docx.shared").Pt
    RGBColor = import_module("docx.shared").RGBColor
    RT = import_module("docx.opc.constants").RELATIONSHIP_TYPE
    repository_root = Path(__file__).resolve().parents[1]
    AUDIT = json.loads(audit_path.read_text())
    DATE = datetime.date.fromisoformat(AUDIT["date"]).strftime("%-d %B %Y")
    ROWS = AUDIT["rows"]
    COUNTS = Counter(row["status"] for row in ROWS)
    NAVY = "17324D"
    TEAL = "116B63"
    GRAY = "526274"
    STATUS = {
        "done": ("Done", "E5F2ED", "21654D"),
        "partial": ("Partly done", "FFF1D8", "875617"),
        "missing": ("Not yet", "F5E7E7", "863F3F"),
    }
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.2677)
    section.page_height = Inches(11.6929)
    section.top_margin = Inches(0.63)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)
    section.header_distance = Inches(0.25)
    section.footer_distance = Inches(0.27)
    styles = doc.styles
    for style_name in ["Normal", "Body Text", "List Bullet", "List Number"]:
        style = styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(10.5)
        style.font.color.rgb = RGBColor.from_string(NAVY)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.line_spacing = 1.08
    for name, size in [("Title", 28), ("Heading 1", 20), ("Heading 2", 13), ("Heading 3", 11)]:
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(NAVY)
        style.paragraph_format.space_before = Pt(9)
        style.paragraph_format.space_after = Pt(7)
        style.paragraph_format.keep_with_next = True
    styles["Caption"].font.size = Pt(9)
    styles["Caption"].font.color.rgb = RGBColor.from_string(GRAY)
    header = section.header.paragraphs[0]
    header.text = "EXECPLUS  /  PRODUCT DELIVERY REVIEW"
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.bold = True
    header.runs[0].font.color.rgb = RGBColor.from_string(TEAL)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = footer.add_run(f"{DATE}  •  Page ")
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor.from_string(GRAY)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    footer.add_run(" of ").font.size = Pt(8)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "NUMPAGES")
    footer._p.append(field)
    props = doc.core_properties
    props.title = "ExecPlus — VC Feature Delivery Report"
    props.subject = "64-request audit, competitor comparison and remaining delivery work"
    props.author = "ExecPlus product review"
    props.keywords = "ExecPlus, VC checklist, feature audit, Polymer, ThoughtSpot"
    props.comments = f"Product evidence updated {DATE}; competitor sources reviewed 5 October 2026."
    props.modified = datetime.datetime.now(datetime.timezone.utc)

    def para(text: Any = "", style: Any = None, size: Any = None, bold: Any = False) -> Any:
        p = doc.add_paragraph(text, style)
        if size:
            for run in p.runs:
                run.font.size = Pt(size)
        if bold:
            for run in p.runs:
                run.bold = True
        return p

    def shade(cell: Any, color: Any) -> Any:
        prop = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), color)
        prop.append(shd)

    def margins(cell: Any, value: Any = 65) -> Any:
        prop = cell._tc.get_or_add_tcPr()
        mar = OxmlElement("w:tcMar")
        for side in ("top", "left", "bottom", "right"):
            node = OxmlElement("w:" + side)
            node.set(qn("w:w"), str(value))
            node.set(qn("w:type"), "dxa")
            mar.append(node)
        prop.append(mar)

    def hyperlink(paragraph: Any, text: Any, url: Any) -> Any:
        relation = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), relation)
        run = OxmlElement("w:r")
        properties = OxmlElement("w:rPr")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), TEAL)
        properties.append(color)
        underline = OxmlElement("w:u")
        underline.set(qn("w:val"), "single")
        properties.append(underline)
        run.append(properties)
        node = OxmlElement("w:t")
        node.text = text
        run.append(node)
        link.append(run)
        paragraph._p.append(link)

    def table(headers: Any, widths: Any, font_size: Any = 10) -> Any:
        t = doc.add_table(rows=1, cols=len(headers))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        t.style = "Table Grid"
        for col, width in zip(t.columns, widths, strict=True):
            col.width = Inches(width)
        repeat = OxmlElement("w:tblHeader")
        t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for cell, text, width in zip(t.rows[0].cells, headers, widths, strict=True):
            cell.width = Inches(width)
            cell.text = text
            shade(cell, NAVY)
            margins(cell, 80)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(font_size)
                    r.font.color.rgb = RGBColor(255, 255, 255)
        return t

    def add_row(
        t: Any,
        values: Any,
        widths: Any,
        font_size: Any = 9.5,
        status_index: Any = None,
        status_key: Any = None,
    ) -> Any:
        row = t.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for i, (cell, text, width) in enumerate(zip(row.cells, values, widths, strict=True)):
            cell.width = Inches(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            margins(cell, 65)
            cell.text = str(text)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.widow_control = True
                for run in p.runs:
                    run.font.size = Pt(font_size)
            if len(t.rows) % 2 == 0:
                shade(cell, "F8FAFB")
            if i == status_index and status_key:
                (_label, bg, fg) = STATUS[status_key]
                shade(cell, bg)
                for r in cell.paragraphs[0].runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor.from_string(fg)
        return row

    def new_page(title: Any, intro: Any = None) -> Any:
        heading = doc.add_heading(title, level=1)
        heading.paragraph_format.page_break_before = True
        if intro:
            para(intro)

    def bullets(items: Any) -> Any:
        for text in items:
            para(text, "List Bullet")

    para("Purpose: explain what is delivered, partly delivered and still missing.", size=9)
    doc.add_heading("ExecPlus", 0)
    para("VC feature delivery report", size=18, bold=True)
    para(
        f"As of {DATE}  •  Based on the current repository and recorded private-demo evidence",
        size=10,
    )
    para(AUDIT["narrative"]["p01"], size=13, bold=True)
    widths = [2.32, 2.32, 2.32]
    t = table(["DONE", "PARTLY DONE", "NOT YET IMPLEMENTED"], widths, 10)
    row = add_row(
        t, [str(COUNTS["done"]), str(COUNTS["partial"]), str(COUNTS["missing"])], widths, 23
    )
    for cell, status in zip(row.cells, ["done", "partial", "missing"], strict=True):
        shade(cell, STATUS[status][1])
        for r in cell.paragraphs[0].runs:
            r.bold = True
            r.font.color.rgb = RGBColor.from_string(STATUS[status][2])
    para(
        f"{len(ROWS)} requested feature lines reviewed. "
        f"{COUNTS['partial'] + COUNTS['missing']} still need work: "
        f"{COUNTS['partial']} partly delivered + {COUNTS['missing']} not yet implemented.",
        bold=True,
    )
    widths = [3.15, 0.95, 0.95, 0.95, 0.96]
    t = table(["VC section", "Total", "Done", "Partly", "Not yet"], widths)
    for name in dict.fromkeys(row["section"] for row in ROWS):
        items = [r for r in ROWS if r["section"] == name]
        c = Counter(r["status"] for r in items)
        label = (
            "Integrations with other solutions"
            if name == "Integration with other Solutions"
            else name
        )
        add_row(t, [label, len(items), c["done"], c["partial"], c["missing"]], widths, 10)
    para("What is strongest today", "Heading 2")
    para(AUDIT["narrative"]["p02"])
    para("What is most clearly missing", "Heading 2")
    para(AUDIT["narrative"]["p03"])
    para("How to read the counts", "Heading 2")
    para(AUDIT["narrative"]["p04"], size=10)
    para(AUDIT["narrative"]["p05"], size=9.5)
    GROUPS = AUDIT["evidence_groups"]
    SECTION_INTROS = AUDIT["section_intros"]
    for section_name in dict.fromkeys(row["section"] for row in ROWS):
        title = (
            "Integrations with other solutions"
            if section_name == "Integration with other Solutions"
            else section_name
        )
        new_page(title, SECTION_INTROS[section_name])
        items = [row for row in ROWS if row["section"] == section_name]
        c = Counter(row["status"] for row in items)
        para(
            f"{len(items)} requests  •  {c['done']} done  •  "
            f"{c['partial']} partly done  •  {c['missing']} not yet",
            size=10,
            bold=True,
        )
        widths = [0.3, 1.94, 0.77, 3.95]
        t = table(["#", "VC request", "Status", "What works / what is left"], widths, 9.5)
        for row in items:
            note = row["note"]
            note += " [" + ", ".join(row["evidence_groups"]) + "]"
            add_row(
                t,
                [row["id"], row["feature"], STATUS[row["status"]][0], note],
                widths,
                9.3,
                2,
                row["status"],
            )
        para(
            f"Evidence labels [E1-E{len(GROUPS)}] refer to repository sources near the report end.",
            size=8.5,
        )
        if section_name == "Month 1":
            para(AUDIT["narrative"]["p06"], size=9)
        if section_name == "Improve activation":
            para(AUDIT["narrative"]["p07"], size=9)
    new_page("How we compare with the targets", AUDIT["narrative"]["p08"])
    para(AUDIT["narrative"]["p09"], size=9.5)
    SOURCES = AUDIT["comparison_sources"]
    COMPARISON = AUDIT["comparison_rows"]
    widths = [0.88, 1.86, 1.87, 2.35]
    t = table(["Area", "Polymer", "ThoughtSpot", "ExecPlus today"], widths, 9.5)
    for values in COMPARISON:
        row = add_row(t, values, widths, 9.2)
        for cell in row.cells[1:3]:
            text = cell.text
            import re

            match = re.search(" \\[([^]]+)\\]$", text)
            if match:
                cell.text = text[: match.start()] + " "
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1
                for run in p.runs:
                    run.font.size = Pt(9.2)
                for index, key in enumerate(match.group(1).split(", ")):
                    if index:
                        p.add_run(" / ")
                    hyperlink(p, key, SOURCES[key][1])
    para("Competitive positioning", "Heading 2")
    para(AUDIT["narrative"]["p10"], size=10)
    para(AUDIT["narrative"]["p11"], size=9)
    new_page("What should happen next", AUDIT["narrative"]["p12"])
    widths = [1.38, 3.92, 1.66]
    t = table(["Workstream", "Plain-language outcome", "Roadmap"], widths, 10)
    for row in [
        ("Customer access", AUDIT["narrative"]["p13"], "Phase 5"),
        ("Finish the analysis flow", AUDIT["narrative"]["p14"], "4D next; 4C delivered"),
        ("Connect live sources", AUDIT["narrative"]["p15"], "4E, then Phase 6"),
        ("Commercial operation", AUDIT["narrative"]["p16"], "Phase 5"),
        ("Launch evidence", AUDIT["narrative"]["p17"], "Phase 5"),
        ("Advanced decisions", AUDIT["narrative"]["p18"], "Phase 6: Frozen"),
    ]:
        add_row(t, row, widths, 10)
    para("A gap in the original Month 1 promise", "Heading 2")
    para(AUDIT["narrative"]["p19"])
    para("Eight launch checks are still open", "Heading 2")
    para(AUDIT["narrative"]["p20"])
    para("Useful work beyond the VC checklist", "Heading 2")
    bullets(
        [
            "Exact numerical results with original files and replayable calculation evidence.",
            "Reviewed business meanings, private goals and versioned studies.",
            "Data-and-document conversation with citations.",
            AUDIT["narrative"]["p21"],
        ]
    )
    para(AUDIT["narrative"]["p22"], size=9)
    para("Advertising rule", "Heading 2")
    para(AUDIT["narrative"]["p23"], size=10, bold=True)
    new_page("Evidence and counting method")
    para(AUDIT["narrative"]["p24"])
    para(AUDIT["narrative"]["p25"])
    para(AUDIT["narrative"]["p26"])
    widths = [1.48, 5.48]
    t = table(
        ["Evidence group", "Repository records and example implementation/test evidence"],
        widths,
        9.5,
    )
    for key, (label, paths) in GROUPS.items():
        assert all(repository_root.joinpath(path).exists() for path in paths), paths
        chosen = paths[:3]
        add_row(t, [key + " — " + label, "\n".join(chosen)], widths, 8.5)
    para("Counting rules", "Heading 2")
    bullets(
        [
            AUDIT["narrative"]["p27"],
            AUDIT["narrative"]["p28"],
            AUDIT["narrative"]["p29"],
            AUDIT["narrative"]["p30"],
        ]
    )
    new_page("Official comparison sources", AUDIT["narrative"]["p31"])
    for prefix, title in [("P", "Polymer"), ("T", "ThoughtSpot")]:
        para(title, "Heading 2")
        for key, (label, url) in SOURCES.items():
            if key.startswith(prefix):
                p = para(size=10)
                p.add_run(key + "  ").bold = True
                hyperlink(p, label, url)
    para("Interpretation limits", "Heading 2")
    para(AUDIT["narrative"]["p32"])
    para(AUDIT["narrative"]["p33"])
    para(AUDIT["narrative"]["p34"])
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    print(json.dumps({"output": str(output), "counts": dict(COUNTS)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "product-feature-audit.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.source.read_text())
    rows = audit["rows"]
    if [row["id"] for row in rows] != list(range(1, 65)):
        parser.error("The source must preserve the original 64 ordered feature IDs.")
    if any(row["status"] not in {"done", "partial", "missing"} for row in rows):
        parser.error("Feature statuses must be done, partial or missing.")
    if args.output.suffix.lower() != ".docx":
        parser.error("The output must be a DOCX file.")
    if args.output.exists():
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = args.output.parent / "report-backups" / f"{args.output.stem}-{stamp}.docx"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.output, backup)
    try:
        build_report(args.source, args.output)
    except ModuleNotFoundError as error:
        if error.name == "docx":
            parser.exit(
                1,
                "Optional report tooling is missing. Install python-docx separately "
                "or supply its isolated PYTHONPATH.\n",
            )
        raise


if __name__ == "__main__":
    main()
