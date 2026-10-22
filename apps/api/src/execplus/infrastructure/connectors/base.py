"""Use case: Gives every connector the same safe HTTP behavior and network policy.

What it does: Maps failures to stable errors, parses JSON and refuses private network hosts.
"""

import ipaddress
import socket
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx

from execplus.application.connector_ports import ConnectorApiError, ProviderTokens
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.bounded_http import limited_request

DEFAULT_TIMEOUT = 30.0


class HostPolicy:
    def __init__(self, allow_private: bool) -> None:
        self.allow_private = allow_private

    def check_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise IngestionError("connector_host_invalid", "Enter a full http(s) address.", 422)
        if parsed.scheme != "https" and not self.allow_private:
            raise IngestionError("connector_host_invalid", "Use an https address.", 422)
        if parsed.username or parsed.password:
            raise IngestionError(
                "connector_host_invalid", "Do not put credentials in the address.", 422
            )
        self.check_host(parsed.hostname)
        return url.strip().rstrip("/")

    def check_host(self, host: str) -> None:
        if self.allow_private:
            return
        try:
            addresses = {str(item[4][0]) for item in socket.getaddrinfo(host, None)}
        except OSError:
            raise IngestionError(
                "connector_host_invalid", "That host could not be found.", 422
            ) from None
        for text in addresses:
            address = ipaddress.ip_address(str(text).split("%")[0])
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_reserved
                or address.is_multicast
                or address.is_unspecified
            ):
                raise IngestionError(
                    "connector_host_blocked",
                    "That address is on a private network and cannot be used from here.",
                    422,
                )


def send(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
    try:
        response = limited_request(client, method, url, **kwargs)
    except httpx.HTTPError:
        raise ConnectorApiError(503) from None
    if response.status_code >= 400:
        code = ""
        try:
            body = response.json()
            value = body.get("error") if isinstance(body, dict) else ""
            code = value if isinstance(value, str) else ""
        except ValueError:
            code = ""
        raise ConnectorApiError(response.status_code, code)
    return response


def json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json(parse_float=Decimal)
    except (ValueError, RecursionError):
        raise ConnectorApiError(502) from None
    if not isinstance(body, dict):
        raise ConnectorApiError(502)
    return body


def tokens_from(body: dict[str, Any], context: dict[str, str] | None = None) -> ProviderTokens:
    access = body.get("access_token")
    if not isinstance(access, str) or not access:
        raise ConnectorApiError(502, str(body.get("error", "")))
    refresh = body.get("refresh_token")
    expires = body.get("expires_in")
    return ProviderTokens(
        access,
        refresh if isinstance(refresh, str) and refresh else None,
        int(expires) if isinstance(expires, int | float | str) and str(expires).isdigit() else 0,
        dict(context or {}),
    )
