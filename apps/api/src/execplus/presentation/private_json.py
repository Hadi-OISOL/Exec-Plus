"""Use case: Applies the public provenance boundary to every ordinary API result.

What it does: Serializes already-authorized JSON after removing original hidden-data
fingerprints from restricted sources, without mutating replay evidence.
"""

from typing import Any

from fastapi.responses import JSONResponse

from execplus.domain.public_evidence import public_evidence


class EvidenceJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(public_evidence(content))
