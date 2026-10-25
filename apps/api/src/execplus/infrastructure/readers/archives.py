"""Use case: Guards compressed uploads and ZIP-based workbooks before any reader opens them.

What it does: Enforces member-count, expansion, ratio and path limits with real byte counting,
unpacks a single supported member from ZIP/GZ/BZ2/XZ archives, and scans workbook XML for
macros and stored formulas.
"""

import bz2
import gzip
import lzma
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Any
from zipfile import BadZipFile, ZipFile, ZipInfo

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.readers.detection import EXTENSIONS

CHUNK = 1024 * 1024
RATIO_FLOOR = 1024 * 1024
XLSX_FORMULA = re.compile(rb"<(?:\w+:)?f[\s>/]")
ODS_FORMULA = re.compile(rb"table:formula=")


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int
    max_expanded_bytes: int
    max_ratio: int


@dataclass(frozen=True)
class ContainerFacts:
    has_macros: bool
    has_formulas: bool


def _unsafe(message: str) -> IngestionError:
    return IngestionError("unsafe_archive", message, 422)


def _check_member(info: ZipInfo, limits: ArchiveLimits) -> None:
    path = PurePosixPath(info.filename)
    if (
        info.flag_bits & 1
        or info.filename.startswith("/")
        or "\\" in info.filename
        or ".." in path.parts
        or stat.S_ISLNK(info.external_attr >> 16)
    ):
        raise _unsafe("Encrypted members, absolute paths, '..' and links are not allowed.")
    if info.file_size > RATIO_FLOOR and info.file_size > (
        max(info.compress_size, 1) * limits.max_ratio
    ):
        raise _unsafe("The archive is compressed too aggressively to open safely.")


def _copy_counted(
    source: IO[bytes],
    target: IO[bytes] | None,
    limits: ArchiveLimits,
    compressed_size: int,
    scan: Callable[[bytes], None] | None = None,
) -> int:
    written = 0
    tail = b""
    while chunk := source.read(CHUNK):
        written += len(chunk)
        if written > limits.max_expanded_bytes:
            raise _unsafe("The archive expands beyond the allowed size.")
        if written > RATIO_FLOOR and written > max(compressed_size, 1) * limits.max_ratio:
            raise _unsafe("The archive is compressed too aggressively to open safely.")
        if scan is not None:
            scan(tail + chunk)
            tail = chunk[-32:]
        if target is not None:
            target.write(chunk)
    return written


def _open_zip(path: Path, limits: ArchiveLimits) -> ZipFile:
    try:
        archive = ZipFile(path)
    except (BadZipFile, OSError) as error:
        raise IngestionError(
            "malformed_archive", "The ZIP container is not readable.", 422
        ) from error
    members = archive.infolist()
    names = [member.filename for member in members]
    if len(members) > limits.max_members or len(set(names)) != len(names):
        archive.close()
        raise _unsafe("The archive has too many or duplicate members.")
    if sum(member.file_size for member in members) > limits.max_expanded_bytes:
        archive.close()
        raise _unsafe("The archive expands beyond the allowed size.")
    try:
        for member in members:
            _check_member(member, limits)
    except IngestionError:
        archive.close()
        raise
    return archive


def inspect_container(path: Path, format: str, limits: ArchiveLimits) -> ContainerFacts:
    """Decompress every member of an XLSX/XLSM/XLSB/ODS file once, counting real bytes."""
    found: list[bool] = []

    def scanner(pattern: re.Pattern[bytes]) -> Callable[[bytes], None]:
        def scan(chunk: bytes) -> None:
            if not found and pattern.search(chunk):
                found.append(True)

        return scan

    total = 0
    macros = False
    with _open_zip(path, limits) as archive:
        for member in archive.infolist():
            lower = member.filename.lower()
            macros = macros or "vbaproject" in lower or lower.startswith("basic/")
            scan = None
            if format in {"xlsx", "xlsm"} and lower.startswith("xl/worksheets/"):
                scan = scanner(XLSX_FORMULA)
            elif format == "ods" and lower == "content.xml":
                scan = scanner(ODS_FORMULA)
            try:
                with archive.open(member) as stream:
                    total += _copy_counted(stream, None, limits, member.compress_size, scan)
            except (BadZipFile, OSError, EOFError) as error:
                raise IngestionError(
                    "malformed_archive", "The workbook container is damaged.", 422
                ) from error
            if total > limits.max_expanded_bytes:
                raise _unsafe("The workbook expands beyond the allowed size.")
    return ContainerFacts(has_macros=macros, has_formulas=bool(found))


def _ignored(name: str) -> bool:
    path = PurePosixPath(name)
    return name.endswith("/") or path.parts[0] == "__MACOSX" or path.name.startswith(".")


def unpack(path: Path, format: str, filename: str, target: Path, limits: ArchiveLimits) -> Path:
    """Extract the single supported data file from an archive into ``target``."""
    target.mkdir(parents=True, exist_ok=True)
    if format == "zip":
        with _open_zip(path, limits) as archive:
            members = [
                member
                for member in archive.infolist()
                if not _ignored(member.filename)
                and PurePosixPath(member.filename).suffix.lower() in EXTENSIONS
            ]
            if len(members) != 1:
                raise IngestionError(
                    "archive_contents",
                    "Put exactly one supported data file in the archive.",
                    422,
                )
            member = members[0]
            output = target / PurePosixPath(member.filename).name
            try:
                with archive.open(member) as stream, output.open("wb") as handle:
                    _copy_counted(stream, handle, limits, member.compress_size)
            except (BadZipFile, OSError, EOFError) as error:
                raise IngestionError(
                    "malformed_archive", "The archive member is damaged.", 422
                ) from error
            return output
    inner = PurePosixPath(filename).stem
    if not PurePosixPath(inner).suffix:
        raise IngestionError(
            "archive_contents",
            "Name compressed files after their contents, for example data.csv.gz.",
            422,
        )
    openers: dict[str, Any] = {"gz": gzip.GzipFile, "bz2": bz2.BZ2File, "xz": lzma.LZMAFile}
    output = target / inner
    try:
        with openers[format](path, "rb") as stream, output.open("wb") as handle:
            _copy_counted(stream, handle, limits, path.stat().st_size)
    except (OSError, EOFError, lzma.LZMAError) as error:
        output.unlink(missing_ok=True)
        raise IngestionError("malformed_archive", "The compressed file is damaged.", 422) from error
    except IngestionError:
        output.unlink(missing_ok=True)
        raise
    return output
