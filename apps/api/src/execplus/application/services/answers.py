"""Use case: Builds user-visible metric answers from executed evidence.

What it does: Requires matching query results and lineage for numerical answers.
"""

import math
from decimal import Decimal

from execplus.domain.errors import UnverifiedAnswerError
from execplus.domain.models import CalculationLineage, QueryResult, VerifiedMetricAnswer


class AnswerAssembler:
    def assemble_metric(
        self,
        label: str,
        column: str,
        result: QueryResult,
        lineage: CalculationLineage,
        row_index: int = 0,
    ) -> VerifiedMetricAnswer:
        if result.query_id != lineage.query_id:
            raise UnverifiedAnswerError(
                "The execution result and lineage refer to different queries"
            )
        if result.records_analyzed != lineage.records_analyzed:
            raise UnverifiedAnswerError(
                "The execution result and lineage record counts do not match"
            )
        if row_index < 0:
            raise UnverifiedAnswerError("The requested row index must be nonnegative")
        try:
            column_index = result.columns.index(column)
            value = result.rows[row_index][column_index]
        except (ValueError, IndexError) as error:
            raise UnverifiedAnswerError(
                "The requested metric is absent from executed results"
            ) from error
        if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
            raise UnverifiedAnswerError("The executed metric is not numeric")
        if isinstance(value, float) and not math.isfinite(value):
            raise UnverifiedAnswerError("The executed metric must be finite")
        if isinstance(value, Decimal) and not value.is_finite():
            raise UnverifiedAnswerError("The executed metric must be finite")
        return VerifiedMetricAnswer(label=label, value=value, lineage=lineage)
