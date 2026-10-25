"""Use case: Public entry point of the upload format readers used by the ingest job.

What it does: Re-exports format detection, the hardened DuckDB connection and open_source.
"""

from execplus.infrastructure.readers.connection import hardened_connection
from execplus.infrastructure.readers.detection import detect_format
from execplus.infrastructure.readers.source import ReaderOptions, ReadResult, TableInfo, open_source

__all__ = [
    "ReadResult",
    "ReaderOptions",
    "TableInfo",
    "detect_format",
    "hardened_connection",
    "open_source",
]
