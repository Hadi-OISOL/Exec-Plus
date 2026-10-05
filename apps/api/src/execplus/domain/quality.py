"""Use case: Explains immutable profile quality without silently imposing business rules.

What it does: Separates measured counts from versioned heuristics and binds findings to a revision.
"""

from decimal import Decimal
from typing import Any, cast

from execplus.domain.artifacts import ArtifactKind, ArtifactRef, content_checksum
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import ALGORITHM, CURRENT_ALGORITHM, Revision

QUALITY_VERSION = "quality-v1"
QUALITY_PARAMETERS: dict[str, int | str] = {
    "high_cardinality_min_present": 10,
    "high_cardinality_ratio": "0.90",
}


def quality_report(revision: Revision) -> dict[str, Any]:
    if revision.algorithm not in {ALGORITHM, CURRENT_ALGORITHM}:
        raise IngestionError("unsupported_version", "This quality source is unsupported.", 409)
    source = revision.profile
    if source.get("algorithm") != revision.algorithm:
        raise IngestionError("lineage_mismatch", "The profile version does not match.", 409)
    rows = int(cast(int, source["row_count"]))
    minimum_present = int(QUALITY_PARAMETERS["high_cardinality_min_present"])
    cardinality_ratio = Decimal(QUALITY_PARAMETERS["high_cardinality_ratio"])
    findings: list[dict[str, Any]] = []

    def add(
        code: str,
        category: str,
        count: int,
        denominator: int | None,
        text: str,
        column: str | None = None,
    ) -> None:
        findings.append(
            dict(
                code=code,
                category=category,
                count=count,
                denominator=denominator,
                column=column,
                message=text,
            )
        )

    for check in cast(list[dict[str, Any]], source["quality_checks"]):
        code = check["code"]
        if code == "unsupported_structures":
            continue
        observed = code in {"missing_values", "duplicate_rows"}
        add(
            code,
            "observed" if observed else "heuristic",
            int(check["count"]),
            int(check["denominator"]),
            str(check["explanation"])
            if observed
            else "This count uses the profile's inferred type; it is not a confirmed quality rule.",
        )
    for column in cast(list[dict[str, Any]], source["columns"]):
        name = str(column["name"])
        missing = int(column["missing"])
        distinct = int(column["distinct_count"])
        present = rows - missing
        add("column_missing", "observed", missing, rows, "Empty cells in this column.", name)
        add(
            "column_distinct",
            "observed",
            distinct,
            present,
            "Distinct nonempty values after the profile's whitespace normalization.",
            name,
        )
        if present and distinct == 1:
            add(
                "constant_column",
                "observed",
                1,
                present,
                "One distinct nonempty value; a constant is not inherently invalid.",
                name,
            )
        if present >= minimum_present and Decimal(distinct) >= cardinality_ratio * present:
            add(
                "high_cardinality",
                "heuristic",
                distinct,
                present,
                f"At least {cardinality_ratio * 100}% distinct among at least "
                f"{minimum_present} nonempty values; grouping may be noisy.",
                name,
            )
        if "identifier" in column.get("semantic_tags", []):
            add(
                "suspected_identifier",
                "heuristic",
                distinct,
                present,
                "The label suggests an identifier; uniqueness and business role need review.",
                name,
            )
    reference = ArtifactRef(
        revision.workspace_id,
        revision.dataset_id,
        ArtifactKind.DATASET_SNAPSHOT,
        revision.id,
        revision.upload_id,
    )
    result = {
        "version": QUALITY_VERSION,
        "source": reference.record(),
        "source_checksum": revision.source_checksum,
        "output_checksum": revision.output_checksum,
        "profile_version": revision.algorithm,
        "profile_checksum": content_checksum(source),
        "parameters": dict(QUALITY_PARAMETERS),
        "findings": findings,
        "confirmed_rules": [],
        "legacy_profile_score": source["quality_score"],
        "availability": "metadata_only",
        "limitations": [
            "This report describes the retained profile; it does not reread source bytes.",
            "The existing profile score is a heuristic, not a certification of source accuracy.",
            "No user-defined assertions, distribution drift or outlier checks run in this version.",
            "Heuristics do not confirm meanings, identify PII or authorize calculations.",
        ],
    }
    return {**result, "checksum": content_checksum(result)}
