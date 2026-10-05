"""Use case: Prevents dependency exceptions from leaking private values through worker logs.

What it does: Checks real CLI exit behavior, resource cleanup and unchanged operator token output.
"""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from execplus import manage
from execplus.infrastructure.identity import LocalSessionIdentity


@pytest.mark.parametrize("stage", ["settings", "build", "work", "dispose"])
def test_worker_fatal_boundary_hides_exception_chains_and_bound_parameters(stage):
    script = """
import sys
from types import SimpleNamespace
from sqlalchemy.exc import StatementError
from execplus import manage
secret = "synthetic-private-question-and-credential"
stage = sys.argv[1]
def failing():
    raise StatementError(
        "dependency failed", "INSERT INTO thread_turns VALUES (:question)",
        {"question": secret}, RuntimeError(secret),
    )
def settings():
    if stage == "settings":
        raise ValueError(secret)
    return object()
def dispose():
    if stage == "dispose":
        failing()
def build(settings):
    if stage == "build":
        failing()
    return SimpleNamespace(jobs=object(), engine=SimpleNamespace(dispose=dispose))
async def work(*args, **kwargs):
    if stage == "work":
        failing()
    return {"processed": 0}
manage.Settings = settings
manage.build_runtime = build
manage.work = work
sys.argv = ["execplus.manage", "process-jobs", "--watch"]
manage.main()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, stage],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "worker action=process-jobs outcome=failed code=worker_failure\n"
    assert "synthetic-private" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "INSERT" not in result.stderr


def test_worker_failure_disposes_runtime_without_printing_exception(monkeypatch, capsys):
    disposed = []
    runtime = SimpleNamespace(
        jobs=object(), engine=SimpleNamespace(dispose=lambda: disposed.append(True))
    )
    monkeypatch.setattr(manage, "Settings", lambda: object())
    monkeypatch.setattr(manage, "build_runtime", lambda settings: runtime)
    monkeypatch.setattr(sys, "argv", ["execplus.manage", "process-jobs"])

    async def broken(*args, **kwargs):
        raise RuntimeError("synthetic-private-query")

    monkeypatch.setattr(manage, "work", broken)
    with pytest.raises(SystemExit) as error:
        manage.main()
    assert error.value.code == 1
    assert disposed == [True]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "worker action=process-jobs outcome=failed code=worker_failure\n"


def test_operator_provisioning_still_prints_its_requested_session_token(monkeypatch, capsys):
    identity = object.__new__(LocalSessionIdentity)
    disposed = []
    monkeypatch.setattr(
        LocalSessionIdentity, "provision", lambda self, email: "synthetic-session-token"
    )
    monkeypatch.setattr(manage, "Settings", lambda: object())
    monkeypatch.setattr(
        manage,
        "build_runtime",
        lambda settings: SimpleNamespace(
            identity=identity, engine=SimpleNamespace(dispose=lambda: disposed.append(True))
        ),
    )
    monkeypatch.setattr(
        sys, "argv", ["execplus.manage", "provision-user", "--email", "operator@example.test"]
    )
    manage.main()
    captured = capsys.readouterr()
    assert captured.out == "synthetic-session-token\n" and captured.err == ""
    assert disposed == [True]


def test_sigterm_waits_for_worker_children_before_disposing_runtime():
    import selectors
    import signal

    script = """
import asyncio
import sys
from types import SimpleNamespace
from execplus import manage
cleaned = []
class Jobs:
    async def process(self, **kwargs):
        print("worker-started", flush=True)
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.append(True)
def dispose():
    if cleaned != [True]:
        raise RuntimeError("child cleanup was not awaited")
manage.Settings = lambda: object()
manage.build_runtime = lambda settings: SimpleNamespace(
    jobs=Jobs(), engine=SimpleNamespace(dispose=dispose),
)
sys.argv = ["execplus.manage", "process-jobs", "--watch"]
manage.main()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=10), "The worker did not start within its test budget"
            assert child.stdout.readline() == "worker-started\n"
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0
        assert stdout == '{"processed": 0}\n'
        assert stderr == ""
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
