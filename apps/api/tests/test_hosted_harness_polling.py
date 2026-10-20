"""The release verifier must wait through the real worker lease lifecycle."""
import importlib.util
from pathlib import Path

import pytest


def verifier():
    path = Path(__file__).resolve().parents[3] / "scripts/check_agent_harness_hosted.py"
    spec = importlib.util.spec_from_file_location("hosted_harness_polling", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("terminal", ["succeeded", "failed", "cancelled", "expired"])
def test_waits_through_claim_and_cancellation(monkeypatch, terminal):
    module = verifier()
    states = iter(["queued", "claimed", "running", "cancelling", terminal])
    observed = []
    monkeypatch.setattr(module, "sleep", lambda _: None)

    def read():
        value = next(states)
        observed.append(value)
        return {"status": value}

    assert module.wait_for_job(read)["status"] == terminal
    assert observed == ["queued", "claimed", "running", "cancelling", terminal]


def test_timeout_never_returns_an_active_job(monkeypatch):
    module = verifier()
    times = iter([0, 0, 101])
    monkeypatch.setattr(module, "monotonic", lambda: next(times))
    monkeypatch.setattr(module, "sleep", lambda _: None)
    with pytest.raises(TimeoutError):
        module.wait_for_job(lambda: {"status": "claimed"})


def test_unknown_state_is_not_success():
    with pytest.raises(ValueError):
        verifier().wait_for_job(lambda: {"status": "unknown"})
