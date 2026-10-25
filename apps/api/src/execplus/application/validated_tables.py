"""Use case: Reads validated source tables without redundant supported-parser work.

What it does: Uses a request-local combined parser capability while retaining the
original parser port fallback, source format checks and all caller authorization.
Profile-v5 roots with a columnar manifest are served from typed Parquet instead.
"""

from io import BytesIO
from typing import Any, BinaryIO, Protocol, cast, runtime_checkable

from execplus.application.ports import ColumnarStore, FileParser, ObjectStorage
from execplus.domain.columnar import ColumnarManifest, ColumnarTable
from execplus.domain.ingestion import FileStructure, IngestionError, Upload
from execplus.domain.profiling import Revision, TableData, reconstruct

MATERIALIZE_LIMIT = 100_000


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


def revision_table(
    storage: ObjectStorage,
    parser: FileParser,
    columnar: ColumnarStore | None,
    upload: Upload,
    revision: Revision,
    *,
    materialize_limit: int = MATERIALIZE_LIMIT,
) -> TableData:
    """Return the revision's snapshot; profile-v5 roots query Parquet and read rows lazily."""

    def original() -> TableData:
        return read_validated_table(
            parser,
            BytesIO(storage.read(upload)),
            upload.filename,
            upload.content_type,
            upload.format,
        )

    manifest = ColumnarManifest.of(revision.profile)
    if manifest is None or revision.recipe:
        return reconstruct(original(), revision)
    if (
        columnar is None
        or revision.output_checksum != manifest.sha256
        or revision.source_checksum != upload.checksum
    ):
        raise IngestionError("lineage_mismatch", "The retained source failed verification.", 409)
    store = columnar

    def rows() -> TableData:
        if manifest.rows > materialize_limit:
            raise IngestionError(
                "large_dataset_step",
                "This step reads every row and is not yet available for files over "
                f"{materialize_limit:,} rows. Ask a calculation question instead.",
                422,
            )
        return original()

    columns = cast(list[dict[str, Any]], revision.profile["columns"])
    return ColumnarTable(
        tuple(str(column["name"]) for column in columns),
        manifest,
        lambda: store.local(upload, manifest.key, manifest.sha256, manifest.size),
        rows,
    )
