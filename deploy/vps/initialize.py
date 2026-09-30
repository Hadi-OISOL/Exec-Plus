"""Use case: Initializes private demo storage and credentials on the mounted data disk.

What it does: Creates separate secret files without printing or replacing existing credentials.
"""

import os
import secrets
from pathlib import Path


def initialize(root: Path) -> None:
    root.mkdir(mode=0o750, parents=True, exist_ok=True)
    private = root / "secrets"
    private.mkdir(mode=0o700, exist_ok=True)
    os.chmod(private, 0o700)
    names = ("database.env", "storage.env", "app.env")
    present = [(private / name).exists() for name in names]
    if any(present) and not all(present):
        raise RuntimeError("Incomplete secret set; recover it before continuing")
    for name in ("postgres", "objects", "backups", "ops"):
        (root / name).mkdir(mode=0o750, exist_ok=True)
    if all(present):
        print("Existing credentials preserved")
        return
    if any(any((root / name).iterdir()) for name in ("postgres", "objects")):
        raise RuntimeError("Existing data requires its original credentials")
    database_password = secrets.token_hex(32)
    storage_password = secrets.token_hex(32)
    contents = {
        "database.env": (
            f"POSTGRES_DB=execplus\nPOSTGRES_USER=execplus\nPOSTGRES_PASSWORD={database_password}\n"
        ),
        "storage.env": (f"MINIO_ROOT_USER=execplus-demo\nMINIO_ROOT_PASSWORD={storage_password}\n"),
        "app.env": (
            "EXECPLUS_ENVIRONMENT=local\n"
            f"EXECPLUS_DATABASE_URL=postgresql+psycopg://execplus:{database_password}"
            "@127.0.0.1:18432/execplus\n"
            "EXECPLUS_OBJECT_STORE_ENDPOINT=http://127.0.0.1:18490\n"
            "EXECPLUS_OBJECT_STORE_BUCKET=execplus-demo\n"
            "EXECPLUS_OBJECT_STORE_ACCESS_KEY=execplus-demo\n"
            f"EXECPLUS_OBJECT_STORE_SECRET_KEY={storage_password}\n"
            "EXECPLUS_WEB_ORIGIN=http://localhost:18400\n"
            "EXECPLUS_LLM_MODE=local\n"
            "EXECPLUS_LLM_BASE_URL=http://127.0.0.1:11450/v1\n"
            "EXECPLUS_LLM_SMALL_MODEL=qwen3:4b\n"
            "EXECPLUS_LLM_LARGE_MODEL=qwen3:4b\n"
            "EXECPLUS_LLM_JSON_MODE=true\n"
            "EXECPLUS_LLM_REASONING_EFFORT=none\n"
            "EXECPLUS_LLM_MAX_OUTPUT_TOKENS=1024\n"
            "EXECPLUS_EMAIL_MODE=disabled\n"
        ),
    }
    for name, content in contents.items():
        descriptor = os.open(private / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write("# Use case: Private VPS demo credentials. Keep out of Git and logs.\n")
            output.write(content)
    print("Private demo directories and credentials initialized")


if __name__ == "__main__":
    if not Path("/sdb-disk").is_mount():
        raise SystemExit("The /sdb-disk data disk must be mounted")
    initialize(Path("/sdb-disk/OISOL_ExecPLUS"))
