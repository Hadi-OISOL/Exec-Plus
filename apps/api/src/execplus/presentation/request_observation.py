"""Use case: Categorizes real requests without inspecting private request content.

What it does: Uses only registered route templates and tags for five fixed metric
categories; health probes, operational polling and preflight traffic are excluded.
"""

import logging

from fastapi import Request


def configure_observation_logging() -> None:
    """Enable only the fixed-metadata request logger, never library request bodies."""
    logger = logging.getLogger("execplus.requests")
    logger.setLevel(logging.INFO)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def category_for(request: Request) -> str | None:
    if request.method == "OPTIONS":
        return None
    route = request.scope.get("route")
    template = getattr(route, "path", "")
    tags = set(getattr(route, "tags", ()))
    if template.startswith(("/health", "/admin/")):
        return None
    if "export" in template:
        return "exports"
    if request.method == "POST" and (
        template.endswith("/uploads") or "/samples/" in template or "source-imports" in tags
    ):
        return "ingestion"
    if request.method == "POST" and template.endswith("/jobs"):
        return "queue"
    if tags.intersection({"analytics", "forecasts", "decision analysis", "studies", "joins"}):
        return "analysis"
    return "other"
