"""Use case: Carries combined conversation evidence without model-authored claims.

What it does: Separates executed data, quoted passages and explicit limitations.
"""

from dataclasses import dataclass
from typing import Any

from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer

NumericalAnswer = VerifiedMetricAnswer | tuple[QueryResult, CalculationLineage]


@dataclass(frozen=True)
class EvidenceAnswer:
    kind: str
    data: NumericalAnswer | None
    citations: tuple[dict[str, Any], ...]
    document_query: str
    coverage: str
    limitations: tuple[str, ...]
    model_route: str
    sources: tuple[dict[str, str], ...]


def answer_lineage(answer: NumericalAnswer) -> CalculationLineage:
    return answer.lineage if isinstance(answer, VerifiedMetricAnswer) else answer[1]
