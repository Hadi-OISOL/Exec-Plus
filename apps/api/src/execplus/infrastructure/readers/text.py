"""Use case: Turns delimited text in any common encoding into UTF-8 that DuckDB can stream.

What it does: Detects BOMs, prefers strict UTF-8, falls back to charset-normalizer on a large
sample, transcodes other encodings to a UTF-8 file in bounded chunks and rejects NUL bytes.
"""

import codecs
from pathlib import Path

from charset_normalizer import from_bytes

from execplus.domain.ingestion import IngestionError

SAMPLE_BYTES = 4 * 1024 * 1024
CHUNK = 1024 * 1024
BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)
WESTERN = {"latin_1", "iso8859_1", "iso8859_15", "cp1250", "cp1252"}


def detect_encoding(sample: bytes) -> str:
    for bom, name in BOMS:
        if sample.startswith(bom):
            return name
    try:
        codecs.getincrementaldecoder("utf-8")("strict").decode(sample, final=False)
        return "utf-8"
    except UnicodeDecodeError:
        pass
    best = from_bytes(sample).best()
    if best is None:
        raise IngestionError(
            "unknown_encoding", "The text encoding could not be recognised. Choose one.", 422
        )
    return "cp1252" if best.encoding in WESTERN else best.encoding


def _unreadable(encoding: str) -> IngestionError:
    return IngestionError(
        "encoding_error",
        f"The file is not valid {encoding} text. Choose the file's encoding and try again.",
        422,
    )


def to_utf8(path: Path, target_dir: Path, encoding: str | None = None) -> tuple[Path, str]:
    """Return a UTF-8 path for ``path`` and the encoding that was used to read it."""
    with path.open("rb") as handle:
        sample = handle.read(SAMPLE_BYTES)
    try:
        chosen = codecs.lookup(encoding or detect_encoding(sample)).name
    except LookupError as error:
        raise IngestionError(
            "unknown_encoding", "Choose a supported text encoding.", 422
        ) from error
    if chosen == "utf-8":
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        with path.open("rb") as handle:
            try:
                while chunk := handle.read(CHUNK):
                    if b"\x00" in chunk:
                        raise IngestionError("unsafe_content", "Null bytes are unsupported.", 422)
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
            except UnicodeDecodeError as error:
                raise _unreadable(chosen) from error
        return path, chosen
    target_dir.mkdir(parents=True, exist_ok=True)
    output = target_dir / f"{path.name}.utf8"
    transcoder = codecs.getincrementaldecoder(chosen)("strict")
    first = True
    try:
        with path.open("rb") as source, output.open("w", encoding="utf-8", newline="") as sink:
            while True:
                chunk = source.read(CHUNK)
                text = transcoder.decode(chunk, final=not chunk)
                if first and text.startswith("﻿"):
                    text = text[1:]
                first = first and not text
                if "\x00" in text:
                    raise IngestionError("unsafe_content", "Null bytes are unsupported.", 422)
                sink.write(text)
                if not chunk:
                    break
    except UnicodeDecodeError as error:
        output.unlink(missing_ok=True)
        raise _unreadable(chosen) from error
    except IngestionError:
        output.unlink(missing_ok=True)
        raise
    return output, chosen
