"""Use case: Protects architectural dependency boundaries.

What it does: Detects core coupling and premature vector-vendor selection.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
DOMAIN = ROOT / "apps" / "api" / "src" / "execplus" / "domain"
CORE = ROOT / "apps" / "api" / "src" / "execplus"
FORBIDDEN_DOMAIN_ROOTS = {
    "duckdb",
    "fastapi",
    "httpx",
    "pydantic",
    "sqlalchemy",
}
FORBIDDEN_VECTOR_VENDOR_ROOTS = {
    "chromadb",
    "milvus",
    "pinecone",
    "qdrant_client",
    "weaviate",
}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_has_no_framework_or_provider_dependencies() -> None:
    violations = {
        str(path.relative_to(ROOT)): imported_roots(path) & FORBIDDEN_DOMAIN_ROOTS
        for path in DOMAIN.rglob("*.py")
        if imported_roots(path) & FORBIDDEN_DOMAIN_ROOTS
    }

    assert violations == {}


def test_backend_has_no_vector_vendor_dependency() -> None:
    violations = {
        str(path.relative_to(ROOT)): imported_roots(path) & FORBIDDEN_VECTOR_VENDOR_ROOTS
        for path in CORE.rglob("*.py")
        if imported_roots(path) & FORBIDDEN_VECTOR_VENDOR_ROOTS
    }

    assert violations == {}


def test_domain_uses_only_standard_library_and_domain() -> None:
    import sys

    violations = {}
    for path in DOMAIN.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"Use absolute imports for boundary checks: {path}"
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.split(".")[0] not in sys.stdlib_module_names and not name.startswith(
                    "execplus.domain"
                ):
                    violations[str(path)] = name
    assert violations == {}


def test_application_depends_only_on_standard_library_and_core() -> None:
    import sys

    violations = {}
    for path in (CORE / "application").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"Use absolute imports for boundary checks: {path}"
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.split(".")[0] not in sys.stdlib_module_names and not name.startswith(
                    ("execplus.domain", "execplus.application")
                ):
                    violations[str(path)] = name
    assert violations == {}


def test_dependency_manifests_do_not_select_vector_vendors() -> None:
    import json
    import re

    paths = [ROOT / "pyproject.toml", ROOT / "package.json", ROOT / "apps/web/package.json"]
    manifests = " ".join(path.read_text().lower() for path in paths)
    assert json.loads(paths[1].read_text())["private"] is True
    for vendor in ("chromadb", "milvus", "pinecone", "qdrant", "weaviate"):
        assert not re.search(rf"\b{vendor}", manifests)
