"""Use case: Guards the owner scripts that switch the VPS between public and tunnel-only access.

What it does: Rehearses go-public.sh and go-private.sh against stub commands in a temporary root.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ORIGINAL_APP_ENV = """# private settings
EXECPLUS_ENVIRONMENT=local
EXECPLUS_WEB_ORIGIN=http://localhost:18400
EXECPLUS_LLM_API_KEY=old-secret
EXECPLUS_PUBLIC_API_URL=http://localhost:18401
"""

STUBS = {
    "id": "echo 0",
    "getent": 'echo "$RESOLVED_ADDRESS STREAM $3"',
    "ip": "echo '2: eno1    inet 173.208.151.137/25 brd 173.208.151.255 scope global eno1'",
    "ss": "exit 0",
    "curl": 'printf "%s\\n" "curl $*" >> "$TRACE_PATH"',
    "ufw": 'printf "%s\\n" "ufw $*" >> "$TRACE_PATH"; echo "Status: inactive"',
    "docker": """printf '%s\\n' "docker $*" >> "$TRACE_PATH"
case "$*" in
  "image inspect"*) echo "sha256:${API_IMAGE_ID:-aaa}" ;;
esac
""",
}


def install(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    root = tmp_path / "deployment"
    secrets = root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "app.env").write_text(ORIGINAL_APP_ENV)
    (secrets / "public.env").write_text(
        "SYNTELIO_PUBLIC_HOST=syntelio.173-208-151-137.sslip.io\n"
        "SYNTELIO_ACME_EMAIL=owner@oisol.test\n"
        "SYNTELIO_LOCAL_REGISTRATION_ENABLED=false\n"
    )
    scripts = tmp_path / "vps"
    scripts.mkdir()
    for name in ("go-public.sh", "go-private.sh"):
        text = Path("deploy/vps", name).read_text()
        text = text.replace("root=/sdb-disk/OISOL_ExecPLUS", f"root='{root}'").replace(
            "/run/lock/execplus-maintenance.lock", str(tmp_path / "maintenance.lock")
        )
        (scripts / name).write_text(text)
    for name in ("compose.yaml", "compose.public.yaml", "Caddyfile"):
        shutil.copy(Path("deploy/vps", name), scripts / name)
    (scripts / "backup.sh").write_text('printf "%s\\n" "backup" >> "$TRACE_PATH"\n')
    binary = tmp_path / "bin"
    binary.mkdir()
    for name, body in STUBS.items():
        path = binary / name
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o700)
    env = {
        **os.environ,
        "PATH": f"{binary}:{os.environ['PATH']}",
        "TRACE_PATH": str(tmp_path / "commands.log"),
        "RESOLVED_ADDRESS": "173.208.151.137",
    }
    return root, scripts, env


def run(scripts: Path, name: str, env: dict[str, str], *args: str):
    return subprocess.run(
        ["bash", str(scripts / name), *args], env=env, text=True, capture_output=True
    )


def trace(tmp_path: Path) -> list[str]:
    path = tmp_path / "commands.log"
    return path.read_text().splitlines() if path.exists() else []


def lines(path: Path) -> list[str]:
    return path.read_text().splitlines()


def test_dry_run_changes_nothing(tmp_path):
    root, scripts, env = install(tmp_path)
    result = run(scripts, "go-public.sh", env, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "+ set EXECPLUS_WEB_ORIGIN" in result.stdout
    assert "build web" in result.stdout
    assert (root / "secrets/app.env").read_text() == ORIGINAL_APP_ENV
    assert not (root / "secrets/public-state").exists()
    assert not any(" build " in c or " up " in c or " tag " in c for c in trace(tmp_path))
    assert "backup" not in trace(tmp_path)


def test_go_public_then_private_round_trip(tmp_path):
    root, scripts, env = install(tmp_path)
    result = run(scripts, "go-public.sh", env)
    assert result.returncode == 0, result.stderr
    assert "https://syntelio.173-208-151-137.sslip.io/workspace" in result.stdout
    app_env = lines(root / "secrets/app.env")
    assert app_env[:2] == ["# private settings", "EXECPLUS_ENVIRONMENT=local"]
    assert "EXECPLUS_LLM_API_KEY=old-secret" in app_env
    for line in (
        "EXECPLUS_WEB_ORIGIN=https://syntelio.173-208-151-137.sslip.io",
        "EXECPLUS_PUBLIC_API_URL=https://syntelio.173-208-151-137.sslip.io/api",
        "EXECPLUS_SESSION_COOKIE_SECURE=true",
        'EXECPLUS_TRUSTED_PROXIES=["127.0.0.1"]',
        "EXECPLUS_CONNECTOR_ALLOW_PRIVATE_HOSTS=false",
        "EXECPLUS_LOCAL_REGISTRATION_ENABLED=false",
    ):
        assert app_env.count(line) == 1
    assert len([x for x in app_env if x.startswith("EXECPLUS_WEB_ORIGIN=")]) == 1
    assert (root / "caddy/Caddyfile").read_text() == Path("deploy/vps/Caddyfile").read_text()
    commands = trace(tmp_path)
    order = [
        next(i for i, c in enumerate(commands) if c == "backup"),
        next(i for i, c in enumerate(commands) if c.startswith("docker tag")),
        next(i for i, c in enumerate(commands) if c.endswith("build web")),
        next(i for i, c in enumerate(commands) if "recreate api jobs web" in c),
        next(i for i, c in enumerate(commands) if c.endswith("recreate caddy")),
        next(i for i, c in enumerate(commands) if c.startswith("curl")),
    ]
    assert order == sorted(order)
    assert not any(c.startswith("ufw allow") for c in commands)
    saved = list((root / "secrets").glob("app.env.pre-public-*"))
    assert len(saved) == 1 and saved[0].read_text() == ORIGINAL_APP_ENV

    rotated = (root / "secrets/app.env").read_text().replace("old-secret", "new-secret")
    (root / "secrets/app.env").write_text(rotated)
    (tmp_path / "commands.log").unlink()
    result = run(scripts, "go-private.sh", env)
    assert result.returncode == 0, result.stderr
    assert lines(root / "secrets/app.env") == [
        "# private settings",
        "EXECPLUS_ENVIRONMENT=local",
        "EXECPLUS_WEB_ORIGIN=http://localhost:18400",
        "EXECPLUS_LLM_API_KEY=new-secret",
        "EXECPLUS_PUBLIC_API_URL=http://localhost:18401",
    ]
    commands = trace(tmp_path)
    assert any("rm --force --stop caddy" in c for c in commands)
    assert any(c.startswith("docker tag oisol-execplus/web:pre-public-") for c in commands)
    assert not any(c.endswith("build web") for c in commands)
    assert any("recreate api jobs web" in c for c in commands)
    assert not (root / "secrets/public-state").exists()


def test_go_private_rebuilds_web_when_a_newer_release_is_active(tmp_path):
    _, scripts, env = install(tmp_path)
    assert run(scripts, "go-public.sh", env).returncode == 0
    (tmp_path / "commands.log").unlink()
    result = run(scripts, "go-private.sh", env | {"API_IMAGE_ID": "bbb"})
    assert result.returncode == 0, result.stderr
    commands = trace(tmp_path)
    assert any(c.endswith("compose.yaml build web") for c in commands)
    assert not any(c.startswith("docker tag") for c in commands)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"RESOLVED_ADDRESS": "198.51.100.7"}, "does not resolve to this server"),
        ({"EMAIL": "owner@example.com"}, "real mailbox"),
        ({"HOST": "https://Syntelio.example.com/"}, "lowercase hostname"),
    ],
)
def test_go_public_refuses_bad_settings_before_any_change(tmp_path, change, message):
    root, scripts, env = install(tmp_path)
    public = root / "secrets/public.env"
    text = public.read_text()
    if "EMAIL" in change:
        text = text.replace("owner@oisol.test", change["EMAIL"])
    if "HOST" in change:
        text = text.replace("syntelio.173-208-151-137.sslip.io", change["HOST"])
    public.write_text(text)
    result = run(scripts, "go-public.sh", env | {k: v for k, v in change.items() if k.isupper()})
    assert result.returncode == 1
    assert message in result.stderr
    assert (root / "secrets/app.env").read_text() == ORIGINAL_APP_ENV
    assert "backup" not in trace(tmp_path)


def test_go_private_refuses_without_public_state(tmp_path):
    _, scripts, env = install(tmp_path)
    result = run(scripts, "go-private.sh", env)
    assert result.returncode == 1
    assert "was not made public" in result.stderr
