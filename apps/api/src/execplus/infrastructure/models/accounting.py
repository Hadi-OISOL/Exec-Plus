"""Use case: Fences provider dispatch with durable usage admission.

What it does: Attributes each actual retry, retains terminal accounting before
return, and reports storage failures with fixed codes and no request content.
"""

import logging
from uuid import uuid4

from execplus.application.services.usage_metering import UsageMeteringService
from execplus.application.usage_context import current_usage
from execplus.domain.errors import ProviderUnavailableError
from execplus.domain.ingestion import IngestionError
from execplus.domain.usage_metering import TokenUsage

logger = logging.getLogger(__name__)


class AttemptAccounting:
    def __init__(self, service: UsageMeteringService | None, provider: str, model: str) -> None:
        self.service = service
        self.attribution = current_usage() if service is not None else None
        self.id = uuid4()
        if service is None or self.attribution is None:
            return
        try:
            service.reserve(self.attribution, self.id, provider, model)
            service.start(self.attribution, self.id)
        except IngestionError:
            raise
        except Exception:
            logger.warning("model_usage_admission_unavailable")
            raise ProviderUnavailableError(
                "Model usage admission is unavailable. Try again later."
            ) from None

    def finish(self, outcome: str, usage: TokenUsage, *, preserve_failure: bool = False) -> None:
        if self.service is None or self.attribution is None:
            return
        try:
            self.service.finish(self.attribution, self.id, outcome, usage)
        except Exception:
            logger.warning("model_usage_reconciliation_unavailable")
            if not preserve_failure:
                raise ProviderUnavailableError(
                    "Model usage evidence could not be retained. Try again later."
                ) from None
