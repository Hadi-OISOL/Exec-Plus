"""Use case: Opens the DuckDB connection that ingest readers use for untrusted files.

What it does: Disables extension downloads, loads only bundled extensions, limits file access
to the job directory and locks the configuration so later SQL cannot loosen it.
"""

from collections.abc import Sequence
from pathlib import Path

import duckdb

BUNDLED_EXTENSIONS = ("excel", "sqlite_scanner")


def _directory(path: Path) -> str:
    return str(path.resolve()).replace("'", "''").rstrip("/") + "/"


def hardened_connection(
    temp_dir: Path,
    extension_directory: Path,
    *,
    read_directories: Sequence[Path] = (),
    memory_limit_mb: int = 1024,
    threads: int = 2,
    max_temp_bytes: int = 8 * 1024**3,
) -> duckdb.DuckDBPyConnection:
    temp_dir.mkdir(parents=True, exist_ok=True)
    spill = temp_dir / "duckdb-spill"
    spill.mkdir(exist_ok=True)
    connection = duckdb.connect(
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "allow_community_extensions": False,
            "allow_unsigned_extensions": False,
            "extension_directory": str(extension_directory),
            "memory_limit": f"{memory_limit_mb}MB",
            "threads": threads,
            "temp_directory": str(spill),
            "max_temp_directory_size": f"{max_temp_bytes}B",
        }
    )
    try:
        version = duckdb.__version__
        for name in BUNDLED_EXTENSIONS:
            if any(extension_directory.glob(f"v{version}/*/{name}.duckdb_extension")):
                connection.execute(f"LOAD {name}")
                if name == "sqlite_scanner":
                    connection.execute("SET sqlite_all_varchar = true")
        allowed = ", ".join(f"'{_directory(path)}'" for path in (temp_dir, *read_directories))
        connection.execute(f"SET allowed_directories = [{allowed}]")
        connection.execute("SET enable_external_access = false")
        connection.execute("SET lock_configuration = true")
    except BaseException:
        connection.close()
        raise
    return connection
