"""Use case: Publishes permitted provenance without original hidden-data fingerprints.

What it does: Copies public structures and withholds original source hashes only
for explicitly restricted policy evidence, leaving private receipts unchanged.
"""

from typing import Any


def public_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        restricted = value.get("access_restricted") == "true"
        result = {
            key: public_evidence(item)
            for key, item in value.items()
            if not (restricted and key in {"source_checksum", "output_checksum"})
        }
        if restricted and ("source_checksum" in value or "output_checksum" in value):
            result["fingerprints"] = "withheld_for_restricted_access"
        return result
    if isinstance(value, list):
        return [public_evidence(item) for item in value]
    if isinstance(value, tuple):
        return tuple(public_evidence(item) for item in value)
    return value
