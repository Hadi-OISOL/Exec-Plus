"""Use case: Resolves application dependencies for HTTP handlers.

What it does: Reads startup-composed services without selecting providers inside routes.
"""

from fastapi import Request

from execplus.application.services.health import HealthService


def get_health_service(request: Request) -> HealthService:
    service: HealthService = request.app.state.runtime.health
    return service
