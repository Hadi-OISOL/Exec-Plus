"""Use case: Bounds external connector response bodies before parsing them.

What it does: Requests identity encoding and stops reading at a fixed decoded-byte budget.
"""

from typing import Any

import httpx

from execplus.domain.connectors import MAX_IMPORT_BYTES
from execplus.domain.ingestion import IngestionError


def limited_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_bytes: int = MAX_IMPORT_BYTES,
    **kwargs: Any,
) -> httpx.Response:
    headers = httpx.Headers(kwargs.pop("headers", {}))
    headers["Accept-Encoding"] = "identity"
    with client.stream(method, url, headers=headers, **kwargs) as response:
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise IngestionError(
                "connector_encoding_unsupported",
                "The source must return an uncompressed response for a bounded import.",
                413,
            )
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            if len(body) + len(chunk) > max_bytes:
                raise IngestionError("source_too_large", "The source response is too large.", 413)
            body.extend(chunk)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=bytes(body),
            request=response.request,
        )
