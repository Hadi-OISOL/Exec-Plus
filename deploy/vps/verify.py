"""Use case: Runs backend acceptance beside the VPS database and object store.

What it does: Reuses private credentials for isolated test schemas and reports only test outcomes.
"""

import os
import subprocess

from execplus.config import Settings

settings = Settings()
for name in (
    "database_url",
    "object_store_endpoint",
    "object_store_access_key",
    "object_store_secret_key",
):
    os.environ["EXECPLUS_TEST_" + name.upper()] = getattr(settings, name)
for name in tuple(os.environ):
    if name.startswith("EXECPLUS_") and not name.startswith("EXECPLUS_TEST_"):
        del os.environ[name]
raise SystemExit(
    subprocess.call(["python", "-m", "pytest", "--tb=short", "-p", "no:cacheprovider"])
)
