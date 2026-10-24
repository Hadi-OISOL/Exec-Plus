"""Use case: Defines the rules for Google sign-in and for turning a chosen sheet into an upload.

What it does: Builds PKCE values, validates identity claims and converts sheet values to CSV bytes.
"""

import base64
import csv
import hashlib
import re
import secrets
import unicodedata
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any

from execplus.domain.ingestion import IngestionError

SIGN_IN_SCOPES = ("openid", "email", "profile")
SHEETS_SCOPES = ("openid", "email", "https://www.googleapis.com/auth/drive.file")
ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
SPREADSHEET_ID = re.compile(r"[A-Za-z0-9_-]{20,100}")
MAX_ROWS = 200_000
MAX_COLUMNS = 500
MAX_CELLS = 2_000_000
MAX_FILENAME = 100
MAX_IMPORT_BYTES = 20 * 1024 * 1024


def new_pkce(size: int = 64) -> tuple[str, str]:
    verifier = secrets.token_urlsafe(size)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _identity_error() -> IngestionError:
    return IngestionError("google_identity_invalid", "Google could not confirm your identity.", 401)


def verified_identity(
    claims: dict[str, Any], client_id: str, nonce: str, now: datetime
) -> tuple[str, str]:
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    expires = claims.get("exp")
    email = claims.get("email")
    verified = claims.get("email_verified")
    if (
        claims.get("iss") not in ISSUERS
        or client_id not in audiences
        or (len(audiences) > 1 and claims.get("azp") != client_id)
        or (claims.get("azp") is not None and claims.get("azp") != client_id)
        or not isinstance(claims.get("sub"), str)
        or not 1 <= len(claims["sub"]) <= 255
        or not isinstance(expires, int | float)
        or expires <= now.timestamp()
        or not secrets.compare_digest(str(claims.get("nonce", "")), nonce)
        or verified not in (True, "true")
        or not isinstance(email, str)
        or not email
    ):
        raise _identity_error()
    name = claims.get("name")
    return email, name if isinstance(name, str) else ""


def valid_spreadsheet_id(value: str) -> str:
    if not SPREADSHEET_ID.fullmatch(value):
        raise IngestionError("invalid_sheet", "Choose a Google spreadsheet again.", 422)
    return value


def import_filename(spreadsheet_title: str, tab_title: str) -> str:
    label = f"{spreadsheet_title} - {tab_title}" if tab_title else spreadsheet_title
    cleaned = unicodedata.normalize("NFKC", label)
    cleaned = re.sub(r"[\\/\x00-\x1f]", " ", cleaned).strip()
    cleaned = " ".join(cleaned.split())[: MAX_FILENAME - 4] or "Google Sheet"
    return f"{cleaned}.csv"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def sheet_to_csv(values: list[list[Any]]) -> bytes:
    def too_large() -> IngestionError:
        return IngestionError(
            "sheet_too_large",
            "The sheet exceeds the import size limits. Choose a smaller tab.",
            413,
        )

    if len(values) > MAX_ROWS or any(len(row) > MAX_COLUMNS for row in values):
        raise too_large()
    size = 0
    for row in values:
        for cell in row:
            value = _cell(cell)
            if len(value) > MAX_IMPORT_BYTES:
                raise too_large()
            size += len(value.encode("utf-8"))
            if size > MAX_IMPORT_BYTES:
                raise too_large()
    end = len(values)
    while end and not any(_cell(cell).strip() for cell in values[end - 1]):
        end -= 1
    rows = values[:end]
    if len(rows) < 2:
        raise IngestionError(
            "empty_sheet", "The sheet needs a header row and at least one data row.", 422
        )
    width = max(len(row) for row in rows)
    if len(rows) > MAX_ROWS or width > MAX_COLUMNS or len(rows) * width > MAX_CELLS:
        raise IngestionError(
            "sheet_too_large",
            "The sheet is larger than Syntelio can import. Choose a smaller tab or range.",
            413,
        )
    seen: dict[str, int] = {}
    header = []
    for position in range(width):
        base = _cell(rows[0][position]).strip() if position < len(rows[0]) else ""
        base = base or f"column_{position + 1}"
        seen[base.casefold()] = seen.get(base.casefold(), 0) + 1
        header.append(base if seen[base.casefold()] == 1 else f"{base}_{seen[base.casefold()]}")
    output = BytesIO()

    def write_row(row: list[str]) -> None:
        line = StringIO()
        csv.writer(line, lineterminator="\n").writerow(row)
        content = line.getvalue().encode("utf-8")
        if output.tell() + len(content) > MAX_IMPORT_BYTES:
            raise too_large()
        output.write(content)

    write_row(header)
    for row in rows[1:]:
        write_row(
            [_cell(row[position]) if position < len(row) else "" for position in range(width)]
        )
    return output.getvalue()
