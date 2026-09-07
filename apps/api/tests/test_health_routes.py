"""Use case: Verifies operational HTTP endpoints.

What it does: Protects deployment liveness and readiness contracts.
"""

from fastapi.testclient import TestClient

from execplus.application.services.health import HealthService
from execplus.main import create_app
from execplus.presentation.dependencies import get_health_service


def test_liveness_reports_ok() -> None:
    response = TestClient(create_app()).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "components": []}


def test_readiness_reports_ready_without_required_external_probes() -> None:
    app = create_app()
    app.dependency_overrides[get_health_service] = lambda: HealthService()
    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "components": []}
