"""Use case: Runs an isolated browser-test API beside remote development infrastructure.

What it does: Transfers temporary test settings privately and removes only its own container/tunnel.
"""

import http.client
import os
import shlex
import subprocess
import tempfile
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def browser_transport(env: dict[str, str], identifier: str) -> Iterator[dict[str, str]]:
    target = os.getenv("EXECPLUS_BROWSER_SSH_TARGET")
    if not target:
        yield env
        return
    socket = os.environ["EXECPLUS_BROWSER_SSH_SOCKET"]
    source = "/sdb-disk/OISOL_ExecPLUS/source"
    remote_env = f"/sdb-disk/OISOL_ExecPLUS/ops/{identifier}.env"
    name = f"oisol-execplus-{identifier}"
    ssh = ["ssh", "-S", socket, target]
    forward = ["ssh", "-S", socket, "-O", "forward", "-L", "8001:127.0.0.1:18501", target]
    keys = (
        "EXECPLUS_DATABASE_URL",
        "EXECPLUS_ENVIRONMENT",
        "EXECPLUS_OBJECT_STORE_BUCKET",
        "EXECPLUS_OBJECT_STORE_ENDPOINT",
        "EXECPLUS_OBJECT_STORE_ACCESS_KEY",
        "EXECPLUS_OBJECT_STORE_SECRET_KEY",
        "EXECPLUS_WEB_ORIGIN",
    )
    settings = {key: env[key] for key in keys}
    settings.update(EXECPLUS_LLM_MODE="disabled", PYTHONPATH="/verification/apps/api/src")
    command = [
        "sudo",
        "-n",
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "--network",
        "host",
        "--env-file",
        remote_env,
        "-v",
        f"{source}:/verification:ro",
        "oisol-execplus/api:demo",
        "python",
        "-m",
        "uvicorn",
        "execplus.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18501",
        "--no-access-log",
    ]
    forwarded = False
    try:
        with tempfile.TemporaryDirectory(prefix="execplus-browser-") as directory:
            path = Path(directory) / "api.env"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as output:
                for key, value in settings.items():
                    if "\n" in value or "\r" in value:
                        raise ValueError("Test settings cannot contain line breaks")
                    output.write(f"{key}={value}\n")
            subprocess.run(
                ["scp", "-o", f"ControlPath={socket}", str(path), f"{target}:{remote_env}"],
                check=True,
            )
        subprocess.run(forward, check=True)
        forwarded = True
        subprocess.run([*ssh, shlex.join(command)], check=True, stdout=subprocess.DEVNULL)
        for attempt in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8001/health/ready", timeout=3):
                    break
            except (OSError, http.client.HTTPException):
                if attempt == 39:
                    raise RuntimeError("The isolated browser API did not become ready") from None
                time.sleep(0.5)
        yield {**env, "EXECPLUS_BROWSER_EXTERNAL_API": "1"}
    finally:
        subprocess.run(
            [*ssh, shlex.join(["sudo", "-n", "docker", "stop", name])],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run([*ssh, shlex.join(["rm", "-f", remote_env])], check=False)
        if forwarded:
            cancel = ["cancel" if value == "forward" else value for value in forward]
            subprocess.run(cancel, check=False)
