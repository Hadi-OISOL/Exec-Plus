"""Use case: Decides which reader may open an uploaded file before any bytes are parsed.

What it does: Combines the filename extension with leading magic bytes and returns one
canonical format name, or a stable 415 error for unsupported or mismatched content.
"""

from pathlib import PurePosixPath

from execplus.domain.ingestion import IngestionError

HEAD_BYTES = 4096
ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SAS7BDAT_MAGIC = b"\xc2\xea\x81\x60\xb3\x14\x11\xcf\xbd\x92\x08\x00\x09\xc7\x31\x8c\x18\x1f\x10\x11"
TEXT_BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")
BINARY_MAGIC = (
    *ZIP_MAGIC,
    OLE_MAGIC,
    b"\x1f\x8b",
    b"BZh",
    b"\xfd7zXZ\x00",
    b"PAR1",
    b"SQLite format 3\x00",
    b"MZ",
    b"%PDF",
    b"\x7fELF",
    b"$FL2",
    b"$FL3",
)

EXTENSIONS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".tab": "tsv",
    ".txt": "txt",
    ".xlsx": "xlsx",
    ".xlsm": "xlsm",
    ".xls": "xls",
    ".xlsb": "xlsb",
    ".ods": "ods",
    ".json": "json",
    ".jsonl": "ndjson",
    ".ndjson": "ndjson",
    ".parquet": "parquet",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".db": "sqlite",
    ".sav": "sav",
    ".zsav": "sav",
    ".dta": "dta",
    ".sas7bdat": "sas7bdat",
    ".xpt": "xpt",
    ".xml": "xml",
    ".zip": "zip",
    ".gz": "gz",
    ".bz2": "bz2",
    ".xz": "xz",
}
ARCHIVES = frozenset({"zip", "gz", "bz2", "xz"})
ZIP_CONTAINERS = frozenset({"xlsx", "xlsm", "xlsb", "ods", "zip"})
TEXT_FORMATS = frozenset({"csv", "tsv", "txt"})


def _stripped_text(head: bytes) -> bytes:
    for bom in TEXT_BOMS:
        if head.startswith(bom):
            return head[len(bom) :].lstrip()
    return head.lstrip()


def _matches(format: str, head: bytes) -> bool:
    if format in ZIP_CONTAINERS:
        return head.startswith(ZIP_MAGIC)
    if format == "xls":
        return head.startswith(OLE_MAGIC)
    if format == "gz":
        return head.startswith(b"\x1f\x8b")
    if format == "bz2":
        return head.startswith(b"BZh")
    if format == "xz":
        return head.startswith(b"\xfd7zXZ\x00")
    if format == "parquet":
        return head.startswith(b"PAR1")
    if format == "sqlite":
        return head.startswith(b"SQLite format 3\x00")
    if format == "sav":
        return head.startswith((b"$FL2", b"$FL3"))
    if format == "dta":
        return head.startswith(b"<stata_dta>") or (
            len(head) > 1 and 102 <= head[0] <= 115 and head[1] in (1, 2)
        )
    if format == "sas7bdat":
        return head[12:32] == SAS7BDAT_MAGIC
    if format == "xpt":
        return head.startswith(b"HEADER RECORD*******LIB")
    if head.startswith(BINARY_MAGIC):
        return False
    text = _stripped_text(head)
    if format == "xml":
        return text.startswith(b"<")
    if format in {"json", "ndjson"}:
        return text.startswith((b"{", b"["))
    utf16 = head.startswith((b"\xff\xfe", b"\xfe\xff"))
    lowered = text[:64].lower()
    return (utf16 or b"\x00" not in head) and not lowered.startswith(
        (b"<html", b"<!doctype", b"<?xml", b"<script")
    )


def detect_format(filename: str, first_bytes: bytes) -> str:
    """Return the canonical format for a filename and its first bytes, or raise 415."""
    extension = PurePosixPath(filename.strip()).suffix.lower()
    format = EXTENSIONS.get(extension)
    if format is None:
        raise IngestionError(
            "unsupported_format",
            "This file type is not supported. Upload CSV, TSV, TXT, Excel, ODS, JSON, "
            "Parquet, SQLite, SPSS, Stata, SAS, XML, or a ZIP/GZ/BZ2/XZ archive of one.",
            415,
        )
    if not first_bytes:
        raise IngestionError("empty_file", "The file is empty.", 422)
    if not _matches(format, first_bytes[:HEAD_BYTES]):
        raise IngestionError(
            "content_mismatch",
            f"The file content does not match its {extension} extension.",
            415,
        )
    return format
