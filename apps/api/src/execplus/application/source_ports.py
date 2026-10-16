"""Use case: Keeps external source extraction behind typed application ports.

What it does: Accepts only approved metadata and returns complete immutable snapshot
bytes; credentials and arbitrary SQL are never application or model inputs.
"""

from typing import Protocol

from execplus.domain.source_imports import (
    PostgresSource,
    SourceSnapshot,
    SourceTable,
)


class SourceExtractor(Protocol):
    def read(self, source: PostgresSource, selection: SourceTable) -> SourceSnapshot: ...
