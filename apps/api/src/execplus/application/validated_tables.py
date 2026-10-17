"""Use case: Reads validated source tables without redundant supported-parser work.

What it does: Uses a request-local combined parser capability while retaining the
original parser port fallback, source format checks and all caller authorization.
"""

from typing import BinaryIO, Protocol, runtime_checkable

from execplus.application.ports import FileParser
from execplus.domain.ingestion import FileStructure, IngestionError
from execplus.domain.profiling import TableData


@runtime_checkable
class CombinedTableParser(Protocol):
    def parse_table(
        self,
        content: BinaryIO,
        filename: str,
        content_type: str,
        *,
        stored_format: str | None = None,
    ) -> tuple[FileStructure, TableData]: ...


def read_validated_table(
    parser: FileParser,
    content: BinaryIO,
    filename: str,
    content_type: str,
    stored_format: str,
) -> TableData:
    if isinstance(parser, CombinedTableParser):
        structure, table = parser.parse_table(
            content, filename, content_type, stored_format=stored_format
        )
        if structure.format != stored_format:
            raise IngestionError(
                "unsupported_format", "The retained source format does not match its bytes.", 409
            )
        return table
    parser.parse(content, filename, content_type, stored_format=stored_format)
    return parser.read_table(content, stored_format)
