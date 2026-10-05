"""Use case: Prevents background conversation writes during a private-demo backup.

What it does: Rehearses the real shell workflow with isolated commands and forced failures.
"""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("failure", ["", "dump", "inventory"])
@pytest.mark.parametrize("worker_running", [True, False])
def test_backup_pauses_all_writers_and_restores_only_previously_running_services(
    tmp_path, failure, worker_running
):
    root = tmp_path / "deployment"
    (root / "objects").mkdir(parents=True)
    (root / "backups").mkdir()
    (root / "objects/retained").write_text("fixture")
    binary = tmp_path / "bin"
    binary.mkdir()
    for name, body in {
        "id": "echo 0",
        "mountpoint": "exit 0",
        "docker": """printf '%s\\n' "$*" >> "$TRACE_PATH"
case "$*" in
  *" ps --services --status running")
    if [[ "$FORCE_FAILURE" == inventory ]]; then exit 7; fi
    printf '%s\\n' postgres storage api web
    if [[ "$WORKER_RUNNING" == 1 ]]; then echo jobs; fi ;;
  *" pg_dump "*)
    if [[ "$FORCE_FAILURE" == dump ]]; then exit 9; fi
    printf 'database fixture' ;;
esac
""",
    }.items():
        path = binary / name
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o700)
    original = Path("deploy/vps/backup.sh").read_text()
    script = tmp_path / "backup.sh"
    script.write_text(
        original.replace("root=/sdb-disk/OISOL_ExecPLUS", f"root='{root}'").replace(
            "/run/lock/execplus-maintenance.lock", str(tmp_path / "maintenance.lock")
        )
    )
    trace = tmp_path / "commands.log"
    result = subprocess.run(
        ["bash", str(script)],
        env={
            **os.environ,
            "PATH": f"{binary}:{os.environ['PATH']}",
            "TRACE_PATH": str(trace),
            "FORCE_FAILURE": failure,
            "WORKER_RUNNING": "1" if worker_running else "0",
        },
        text=True,
        capture_output=True,
    )
    commands = trace.read_text().splitlines()
    if failure == "inventory":
        assert result.returncode == 7
        assert len(commands) == 1
        return
    stop = next(
        index for index, command in enumerate(commands) if command.endswith("stop api jobs")
    )
    storage = next(
        index for index, command in enumerate(commands) if command.endswith("stop storage")
    )
    dump = next(index for index, command in enumerate(commands) if " pg_dump " in command)
    assert stop < storage < dump < len(commands) - 1
    assert commands[-1].endswith(
        "start storage api jobs" if worker_running else "start storage api"
    )
    assert result.returncode == (9 if failure else 0)
    manifests = list((root / "backups").glob("*/SHA256SUMS"))
    assert bool(manifests) == (not failure)
