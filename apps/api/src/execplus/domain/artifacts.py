"""Use case: Describes governed artifacts without replacing their owning aggregates.

What it does: Defines immutable scoped references, supported capabilities and metadata checksums.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from execplus.domain.ingestion import IngestionError


class AssetKind(str, Enum):
    TABULAR = "tabular"
    DOCUMENT = "document"
    METADATA = "metadata"


class ArtifactKind(str, Enum):
    RAW_ASSET = "raw_asset"
    DATASET_SNAPSHOT = "dataset_snapshot"
    PROFILE = "profile"
    QUALITY_REPORT = "quality_report"
    DOCUMENT = "document"
    DEFINITION = "definition"
    QUERY_RESULT = "query_result"
    STUDY_VERSION = "study_version"


class Capability(str, Enum):
    INSPECT = "inspect"
    PROFILE = "profile"
    QUERY = "query"
    TRANSFORM = "transform"
    VISUALIZE = "visualize"
    TEXT_SEARCH = "text_search"
    JOIN = "join"
    REPLAY = "replay"


TABULAR_CAPABILITIES = (
    Capability.INSPECT,
    Capability.PROFILE,
    Capability.QUERY,
    Capability.TRANSFORM,
    Capability.VISUALIZE,
    Capability.JOIN,
)


@dataclass(frozen=True)
class ArtifactRef:
    workspace_id: UUID
    dataset_id: UUID
    kind: ArtifactKind
    id: UUID
    upload_id: UUID | None = None

    def record(self) -> dict[str, str | None]:
        return {
            "workspace_id": str(self.workspace_id),
            "dataset_id": str(self.dataset_id),
            "kind": self.kind.value,
            "id": str(self.id),
            "upload_id": str(self.upload_id) if self.upload_id else None,
        }

    def key(self) -> str:
        return f"{self.workspace_id}:{self.dataset_id}:{self.kind.value}:{self.id}"


@dataclass(frozen=True)
class ArtifactDescriptor:
    reference: ArtifactRef
    asset_kind: AssetKind
    name: str
    checksum: str | None
    checksum_scope: str
    method_version: str
    created_by: UUID
    created_at: datetime
    authorization_scope: str
    capabilities: tuple[Capability, ...]
    sources: tuple[ArtifactRef, ...]
    metadata: dict[str, Any]

    def record(self) -> dict[str, Any]:
        return {
            "version": "artifact-v1",
            "key": self.reference.key(),
            "reference": self.reference.record(),
            "asset_kind": self.asset_kind.value,
            "name": self.name,
            "checksum": self.checksum,
            "checksum_scope": self.checksum_scope,
            "method_version": self.method_version,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat(),
            "authorization_scope": self.authorization_scope,
            "capabilities": [item.value for item in self.capabilities],
            "sources": [item.record() for item in self.sources],
            "metadata": self.metadata,
            "availability": "metadata_only",
            "limitations": [
                "Metadata does not verify retained source bytes or replay the result.",
                "Capabilities remain subject to source availability, permissions and meanings.",
            ],
        }


def content_checksum(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def require_acyclic(edges: tuple[tuple[str, str], ...]) -> None:
    remaining = {node for edge in edges for node in edge}
    while remaining:
        dependent = {target for source, target in edges if source in remaining}
        ready = remaining - dependent
        if not ready:
            raise IngestionError("lineage_mismatch", "Lineage contains a cycle.", 409)
        remaining -= ready
