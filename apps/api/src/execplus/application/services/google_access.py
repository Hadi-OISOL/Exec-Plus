"""Use case: Lets people sign in with Google and import a sheet they chose as a normal upload.

What it does: Runs OAuth exchanges, keeps refresh tokens sealed and turns a sheet into an upload.
"""

import json
import logging
import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager, suppress
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, TypeVar
from uuid import UUID, uuid4

from execplus.application.google_ports import (
    GoogleApiError,
    GoogleConnection,
    GoogleConnections,
    GoogleGateway,
    SessionIssuer,
    SpreadsheetInfo,
    TokenSet,
    TokenVault,
)
from execplus.application.ports import WorkspaceRepository
from execplus.application.services.workspaces import WorkspaceService, normalized_email
from execplus.domain.google_oauth import (
    SHEETS_SCOPES,
    SIGN_IN_SCOPES,
    import_filename,
    new_pkce,
    sheet_to_csv,
    valid_spreadsheet_id,
    verified_identity,
)
from execplus.domain.ingestion import AuditEvent, IngestionError, Upload, User

logger = logging.getLogger("execplus.google")
UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]
Result = TypeVar("Result")

SIGN_IN_PATH = "/auth/google/callback"
CONNECT_PATH = "/integrations/google/callback"
STATE_SECONDS = 600
DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"


class GoogleAccessService:
    def __init__(
        self,
        gateway: GoogleGateway,
        vault: TokenVault,
        connections: GoogleConnections,
        issuer: SessionIssuer,
        uploads: WorkspaceService,
        unit_of_work: UnitOfWork,
        *,
        client_id: str,
        public_api_url: str,
        web_origin: str,
        picker_api_key: str = "",
        app_id: str = "",
        max_import_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.gateway = gateway
        self.vault = vault
        self.connections = connections
        self.issuer = issuer
        self.uploads = uploads
        self.uow = unit_of_work
        self.client_id = client_id
        self.api_url = public_api_url.rstrip("/")
        self.web_origin = web_origin.rstrip("/")
        self.picker_api_key = picker_api_key
        self.app_id = app_id
        self.max_import_bytes = max_import_bytes

    def config(self) -> dict[str, Any]:
        picker = (
            dict(api_key=self.picker_api_key, app_id=self.app_id)
            if self.picker_api_key and self.app_id
            else None
        )
        return dict(enabled=True, picker=picker)

    def _begin(self, purpose: str, extra: dict[str, str]) -> tuple[str, str, str, str]:
        verifier, challenge = new_pkce()
        state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        sealed = self.vault.seal(
            json.dumps(dict(purpose=purpose, state=state, verifier=verifier, nonce=nonce, **extra))
        )
        return state, challenge, nonce, sealed

    def _open(self, sealed: str, purpose: str, state: str | None = None) -> dict[str, str]:
        expired = IngestionError(
            "google_state_invalid", "The Google sign-in expired. Please try again.", 400
        )
        try:
            payload = json.loads(self.vault.unseal(sealed, STATE_SECONDS))
        except ValueError:
            raise expired from None
        if not isinstance(payload, dict) or payload.get("purpose") != purpose:
            raise expired
        if state is not None and not secrets.compare_digest(str(payload.get("state", "")), state):
            raise expired
        return {key: str(value) for key, value in payload.items()}

    def start_sign_in(self) -> tuple[str, str]:
        state, challenge, nonce, sealed = self._begin("signin", {})
        url = self.gateway.authorization_url(
            scopes=SIGN_IN_SCOPES,
            redirect_uri=self.api_url + SIGN_IN_PATH,
            state=state,
            challenge=challenge,
            nonce=nonce,
        )
        return url, sealed

    def _exchange(self, code: str, verifier: str, path: str) -> TokenSet:
        try:
            return self.gateway.exchange_code(code, verifier, self.api_url + path)
        except GoogleApiError:
            raise IngestionError(
                "google_exchange_failed", "Google could not complete the request.", 502
            ) from None

    def _identity(self, tokens: TokenSet, nonce: str) -> tuple[str, str]:
        if not tokens.id_token:
            raise IngestionError(
                "google_identity_invalid", "Google could not confirm your identity.", 401
            )
        try:
            claims = self.gateway.id_token_claims(tokens.id_token)
        except GoogleApiError:
            raise IngestionError(
                "google_identity_invalid", "Google could not confirm your identity.", 401
            ) from None
        email, name = verified_identity(claims, self.client_id, nonce, datetime.now(timezone.utc))
        return normalized_email(email), name

    def finish_sign_in(self, code: str, state: str, sealed: str) -> str:
        payload = self._open(sealed, "signin", state)
        tokens = self._exchange(code, payload["verifier"], SIGN_IN_PATH)
        email, name = self._identity(tokens, payload["nonce"])
        logger.info("google_signin outcome=success")
        return self.issuer.provision(email, name)

    def start_connect(self, actor: User) -> str:
        _, challenge, nonce, sealed = self._begin(
            "sheets", dict(user_id=str(actor.id), email=actor.email)
        )
        return self.gateway.authorization_url(
            scopes=SHEETS_SCOPES,
            redirect_uri=self.api_url + CONNECT_PATH,
            state=sealed,
            challenge=challenge,
            nonce=nonce,
            login_hint=actor.email,
            offline=True,
        )

    def finish_connect(self, code: str, state: str) -> None:
        payload = self._open(state, "sheets")
        tokens = self._exchange(code, payload["verifier"], CONNECT_PATH)
        email, _ = self._identity(tokens, payload["nonce"])
        if email != normalized_email(payload["email"]):
            raise IngestionError(
                "google_wrong_account",
                "Choose the Google account that matches your ExecPlus email.",
                409,
            )
        if DRIVE_FILE not in tokens.scope.split():
            raise IngestionError(
                "google_scope_missing", "Allow ExecPlus to open the sheets you choose.", 409
            )
        user_id = UUID(payload["user_id"])
        existing = self.connections.get(user_id)
        refresh = tokens.refresh_token or (
            self.vault.unseal(existing.refresh_token_sealed) if existing else None
        )
        if not refresh:
            raise IngestionError(
                "google_scope_missing",
                "Google did not return a lasting connection. Try again.",
                409,
            )
        self.connections.save(
            GoogleConnection(user_id, email, tokens.scope, self.vault.seal(refresh))
        )
        logger.info("google_connect outcome=success user_id=%s", user_id)

    def status(self, actor: User) -> dict[str, Any]:
        connection = self.connections.get(actor.id)
        return dict(
            connected=connection is not None, email=connection.google_email if connection else ""
        )

    def disconnect(self, actor: User) -> None:
        connection = self.connections.get(actor.id)
        if connection is None:
            return
        with suppress(ValueError):
            self.gateway.revoke(self.vault.unseal(connection.refresh_token_sealed))
        self.connections.delete(actor.id)
        logger.info("google_disconnect outcome=success user_id=%s", actor.id)

    def _reconnect(self) -> IngestionError:
        return IngestionError(
            "google_reconnect", "Your Google connection expired. Connect it again.", 409
        )

    def _access_token(self, actor: User) -> TokenSet:
        connection = self.connections.get(actor.id)
        if connection is None:
            raise IngestionError("google_not_connected", "Connect your Google account first.", 409)
        try:
            return self.gateway.refresh(self.vault.unseal(connection.refresh_token_sealed))
        except ValueError:
            self.connections.delete(actor.id)
            raise self._reconnect() from None
        except GoogleApiError as error:
            if error.code == "invalid_grant" or error.status in {400, 401}:
                self.connections.delete(actor.id)
                raise self._reconnect() from None
            raise IngestionError(
                "google_unavailable", "Google is unavailable. Try again shortly.", 503
            ) from None

    def picker_token(self, actor: User) -> dict[str, Any]:
        tokens = self._access_token(actor)
        return dict(access_token=tokens.access_token, expires_in=tokens.expires_in)

    def _call(self, action: Callable[[], Result], actor: User) -> Result:
        try:
            return action()
        except GoogleApiError as error:
            if error.status == 401:
                self.connections.delete(actor.id)
                raise self._reconnect() from None
            if error.status in {403, 404}:
                raise IngestionError(
                    "google_sheet_unavailable",
                    "ExecPlus cannot read that sheet. Choose it again with Google's picker.",
                    404,
                ) from None
            if error.status == 413:
                raise IngestionError(
                    "sheet_too_large", "The sheet is larger than ExecPlus can import.", 413
                ) from None
            if error.status == 429:
                raise IngestionError(
                    "google_rate_limited", "Google is limiting requests. Try again shortly.", 429
                ) from None
            raise IngestionError(
                "google_unavailable", "Google is unavailable. Try again shortly.", 503
            ) from None

    def spreadsheet(self, actor: User, spreadsheet_id: str) -> dict[str, Any]:
        identifier = valid_spreadsheet_id(spreadsheet_id)
        token = self._access_token(actor).access_token
        info: SpreadsheetInfo = self._call(
            lambda: self.gateway.spreadsheet(token, identifier), actor
        )
        return dict(
            title=info.title,
            tabs=[
                dict(id=tab.id, title=tab.title, rows=tab.rows, columns=tab.columns)
                for tab in info.tabs
            ],
        )

    def import_sheet(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        spreadsheet_id: str,
        sheet_id: int | None,
    ) -> Upload:
        identifier = valid_spreadsheet_id(spreadsheet_id)
        self.uploads.get_dataset(actor, workspace_id, dataset_id)
        token = self._access_token(actor).access_token
        info: SpreadsheetInfo = self._call(
            lambda: self.gateway.spreadsheet(token, identifier), actor
        )
        tab = next((item for item in info.tabs if sheet_id in {None, item.id}), None)
        if tab is None:
            raise IngestionError("empty_sheet", "Choose a tab that exists in this sheet.", 422)
        values = self._call(
            lambda: self.gateway.sheet_values(token, identifier, tab.title, self.max_import_bytes),
            actor,
        )
        content = sheet_to_csv(values)
        filename = import_filename(info.title, tab.title if len(info.tabs) > 1 else "")
        upload = self.uploads.upload(
            actor, workspace_id, dataset_id, filename, "text/csv", BytesIO(content)
        )
        with self.uow() as repo:
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "google_sheets.imported",
                    "upload",
                    upload.id,
                    datetime.now(timezone.utc),
                )
            )
        logger.info("google_sheets_import outcome=success upload_id=%s", upload.id)
        return upload
