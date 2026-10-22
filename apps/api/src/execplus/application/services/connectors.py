"""Use case: Lets a user connect an external data platform and import one source as an upload.

What it does: Runs each platform's connect step, keeps secrets sealed and copies a chosen source.
"""

import hashlib
import json
import logging
import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, TypeVar
from urllib.parse import unquote
from uuid import UUID, uuid4

from execplus.application.connector_ports import (
    Connector,
    ConnectorApiError,
    ConnectorConnection,
    ConnectorConnections,
    ConnectorSession,
    CredentialConnector,
    OAuthConnector,
)
from execplus.application.google_ports import TokenVault
from execplus.application.oauth_ports import OAuthState
from execplus.application.ports import WorkspaceRepository
from execplus.application.services.refresh import RefreshService, editor
from execplus.application.services.workspaces import WorkspaceService
from execplus.domain.connectors import connector_filename, records_to_csv, valid_provider
from execplus.domain.google_oauth import new_pkce
from execplus.domain.ingestion import AuditEvent, IngestionError, Upload, User
from execplus.domain.refresh import RefreshCandidate

logger = logging.getLogger("execplus.connectors")
UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]
Result = TypeVar("Result")
STATE_SECONDS = 600
PKCE_SIZE = 32


class ConnectorService:
    def __init__(
        self,
        connectors: dict[str, Connector],
        vault: TokenVault,
        connections: ConnectorConnections,
        uploads: WorkspaceService,
        unit_of_work: UnitOfWork,
        *,
        oauth: OAuthState,
        public_api_url: str,
        web_origin: str,
        max_rows: int,
    ) -> None:
        self.oauth = oauth
        self.connectors = connectors
        self.vault = vault
        self.connections = connections
        self.uploads = uploads
        self.uow = unit_of_work
        self.api_url = public_api_url.rstrip("/")
        self.web_origin = web_origin.rstrip("/")
        self.max_rows = max_rows

    def _connector(self, provider: str) -> Connector:
        connector = self.connectors.get(valid_provider(provider))
        if connector is None:
            raise IngestionError("unknown_connector", "That data platform is not available.", 404)
        return connector

    def _oauth(self, provider: str) -> OAuthConnector:
        connector = self._connector(provider)
        if connector.kind != "oauth":
            raise IngestionError("unknown_connector", "That platform does not use sign-in.", 404)
        return connector  # type: ignore[return-value]

    def _credential(self, provider: str) -> CredentialConnector:
        connector = self._connector(provider)
        if connector.kind != "credentials":
            raise IngestionError("unknown_connector", "That platform uses sign-in instead.", 404)
        return connector  # type: ignore[return-value]

    def catalog(self, actor: User) -> list[dict[str, Any]]:
        connected = {item.provider: item for item in self.connections.list(actor.id)}
        return [
            dict(
                id=connector.id,
                label=connector.label,
                kind=connector.kind,
                description=connector.description,
                fields=[
                    dict(
                        name=item.name,
                        label=item.label,
                        secret=item.secret,
                        placeholder=item.placeholder,
                    )
                    for item in connector.fields
                ],
                connected=connector.id in connected,
                account=connected[connector.id].display_name if connector.id in connected else "",
                configured=True,
            )
            for connector in self.connectors.values()
        ]

    def redirect_uri(self, provider: str) -> str:
        return f"{self.api_url}/connectors/{provider}/callback"

    def start_connect(
        self, actor: User, provider: str, browser: str, session_token: str, peer: str = ""
    ) -> str:
        connector = self._oauth(provider)
        verifier, challenge = new_pkce(PKCE_SIZE) if connector.uses_pkce else ("", "")
        state = self.oauth.begin(
            connector.id,
            "connect",
            browser,
            self.vault.seal(json.dumps(dict(verifier=verifier))),
            user_id=actor.id,
            session_token=session_token,
            peer=peer,
        )
        return connector.authorization_url(
            redirect_uri=self.redirect_uri(connector.id), state=state, challenge=challenge
        )

    def finish_connect(
        self,
        provider: str,
        code: str,
        state: str,
        callback: dict[str, str],
        browser: str,
        error: bool = False,
    ) -> str:
        connector = self._oauth(provider)
        attempt = self.oauth.claim(state, browser, connector.id, "connect")
        try:
            if error or not code:
                raise IngestionError("connector_denied", "The connection was not completed.", 400)
            payload = json.loads(self.vault.unseal(attempt.sealed_payload, STATE_SECONDS))
            tokens = connector.exchange_code(
                code, self.redirect_uri(connector.id), str(payload.get("verifier", "")), callback
            )
            if not tokens.refresh_token:
                raise IngestionError(
                    "connector_no_refresh", "The platform did not return a lasting connection.", 409
                )
            assert attempt.user_id is not None
            record = ConnectorConnection(
                attempt.user_id,
                connector.id,
                connector.account_name(tokens.context),
                self.vault.seal(
                    json.dumps(dict(refresh_token=tokens.refresh_token, context=tokens.context))
                ),
            )
            return self.oauth.complete_connection(attempt, record)
        except ConnectorApiError as error:
            return self.oauth.fail(attempt, self._failure(error).code)
        except ValueError:
            return self.oauth.fail(attempt, "oauth_state_invalid")
        except IngestionError as failure:
            return self.oauth.fail(attempt, failure.code)

    def save_credentials(
        self, actor: User, provider: str, values: dict[str, str], session_token: str, peer: str = ""
    ) -> str:
        connector = self._credential(provider)
        known = {item.name for item in connector.fields}
        secret_fields = {item.name for item in connector.fields if item.secret}
        credentials = {
            key: value if key in secret_fields else value.strip()
            for key, value in values.items()
            if key in known and isinstance(value, str)
        }
        if any(not credentials.get(name) for name in known if name != "port"):
            raise IngestionError("connector_missing_field", "Fill in every field.", 422)
        browser = secrets.token_urlsafe(32)
        state = self.oauth.begin(
            connector.id,
            "connect",
            browser,
            "",
            user_id=actor.id,
            session_token=session_token,
            peer=peer,
        )
        attempt = self.oauth.claim(state, browser, connector.id, "connect")
        try:
            display = connector.validate(credentials)
        except ConnectorApiError as error:
            raise self._failure(error) from None
        self.oauth.complete_connection(
            attempt,
            ConnectorConnection(
                actor.id,
                connector.id,
                display,
                self.vault.seal(json.dumps(dict(context=credentials))),
            ),
        )
        logger.info("connector_connect provider=%s outcome=success user_id=%s", provider, actor.id)
        return display

    def disconnect(self, actor: User, provider: str) -> None:
        connector = self._connector(provider)
        connection = self.connections.get(actor.id, connector.id)
        self.connections.delete(actor.id, connector.id)
        if connection is not None and connector.kind == "oauth":
            try:
                stored = json.loads(self.vault.unseal(connection.sealed_credentials))
                self._oauth(provider).revoke(str(stored.get("refresh_token", "")))
            except (ValueError, ConnectorApiError, IngestionError):
                pass
        logger.info("connector_disconnect provider=%s user_id=%s", provider, actor.id)

    @staticmethod
    def _failure(error: ConnectorApiError) -> IngestionError:
        rejected = IngestionError(
            "connector_credentials_rejected", "The platform did not accept the sign-in.", 422
        )
        mapping = {
            401: rejected,
            403: IngestionError(
                "connector_forbidden", "That account is not allowed to read this data.", 403
            ),
            404: IngestionError(
                "connector_source_unavailable", "That source is not available to this account.", 404
            ),
            422: IngestionError(
                "connector_invalid_request", "Check the details you entered and try again.", 422
            ),
            429: IngestionError(
                "connector_rate_limited",
                "The platform is limiting requests. Try again shortly.",
                429,
            ),
            502: IngestionError(
                "connector_unexpected_response", "The platform sent an unexpected reply.", 502
            ),
        }
        if error.code == "control_plane_database":
            return IngestionError(
                "connector_host_blocked", "ExecPlus's own database cannot be used as a source.", 422
            )
        if error.status == 400:
            return (
                rejected
                if error.code == "invalid_grant"
                else IngestionError(
                    "connector_invalid_request", "The platform could not complete the request.", 422
                )
            )
        return mapping.get(
            error.status,
            IngestionError(
                "connector_unavailable", "The platform is unavailable. Try again shortly.", 503
            ),
        )

    def _session(
        self, actor: User, provider: str
    ) -> tuple[Connector, ConnectorSession, ConnectorConnection]:
        connector = self._connector(provider)
        connection = self.connections.get(actor.id, connector.id)
        if connection is None:
            raise IngestionError(
                "connector_not_connected", f"Connect {connector.label} first.", 409
            )
        try:
            stored = json.loads(self.vault.unseal(connection.sealed_credentials))
        except ValueError:
            self.connections.delete(actor.id, connector.id, expected_version=connection.version)
            raise self._reconnect(connector) from None
        context = {str(key): str(value) for key, value in stored.get("context", {}).items()}
        if connector.kind == "credentials":
            return connector, ConnectorSession("", context), connection
        refresh_token = str(stored.get("refresh_token", ""))
        try:
            tokens = self._oauth(provider).refresh(refresh_token, context)
        except ConnectorApiError as error:
            if error.status in {400, 401}:
                self.connections.delete(actor.id, connector.id, expected_version=connection.version)
                raise self._reconnect(connector) from None
            raise self._failure(error) from None
        if not self.connections.current(connection):
            raise self._reconnect(connector)
        if tokens.refresh_token and tokens.refresh_token != refresh_token:
            updated = ConnectorConnection(
                actor.id,
                connector.id,
                connection.display_name,
                self.vault.seal(
                    json.dumps(dict(refresh_token=tokens.refresh_token, context=context))
                ),
            )
            self.connections.save(updated, expected_version=connection.version)
            connection = updated
        return connector, ConnectorSession(tokens.access_token, context), connection

    @staticmethod
    def _reconnect(connector: Connector) -> IngestionError:
        return IngestionError(
            "connector_reconnect",
            f"Your {connector.label} connection expired. Connect it again.",
            409,
        )

    def _call(self, action: Callable[[], Result]) -> Result:
        try:
            return action()
        except ConnectorApiError as error:
            raise self._failure(error) from None
        except (AttributeError, TypeError, KeyError, IndexError):
            logger.warning("connector_reply_malformed outcome=refused")
            raise self._failure(ConnectorApiError(502)) from None

    def status(self, actor: User, provider: str) -> dict[str, Any]:
        connector = self._connector(provider)
        connection = self.connections.get(actor.id, connector.id)
        return dict(
            connected=connection is not None, account=connection.display_name if connection else ""
        )

    def browse(
        self, actor: User, provider: str, parent: str | None, session_token: str
    ) -> list[dict[str, Any]]:
        connector, session, connection = self._session(actor, provider)
        items = self._call(lambda: connector.sources(session, parent))
        self.oauth.assert_connection(actor.id, session_token, connector.id, connection.version)
        return [dict(id=item.id, label=item.label, container=item.container) for item in items]

    def _label(self, connector: Connector, session: ConnectorSession, source_id: str) -> str:
        if "/" in source_id:
            return unquote(source_id.rsplit("/", 1)[1])
        known = {item.id: item.label for item in connector.sources(session, None)}
        return known.get(source_id, source_id)

    def _snapshot(
        self, actor: User, provider: str, source_id: str, session_token: str
    ) -> tuple[str, bytes, Callable[[WorkspaceRepository, str, UUID, UUID], None]]:
        connector, session, connection = self._session(actor, provider)
        records = self._call(lambda: connector.fetch(session, source_id, self.max_rows + 1))
        if len(records) > self.max_rows:
            raise IngestionError(
                "source_too_large",
                "That source exceeds the import row limit. Choose a smaller source.",
                413,
            )
        content = records_to_csv(records)
        filename = connector_filename(
            connector.label, connection.display_name, self._label(connector, session, source_id)
        )
        self.oauth.assert_connection(actor.id, session_token, connector.id, connection.version)

        def publish(
            repo: WorkspaceRepository, action: str, workspace_id: UUID, target: UUID
        ) -> None:
            repo.require_provider_connection(
                actor.id,
                hashlib.sha256(session_token.encode()).hexdigest(),
                connector.id,
                connection.version,
            )
            kind = "upload" if action == "connector.imported" else "refresh_candidate"
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    action,
                    kind,
                    target,
                    datetime.now(timezone.utc),
                )
            )

        return filename, content, publish

    def import_source(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        provider: str,
        source_id: str,
        session_token: str,
    ) -> Upload:
        self.uploads.get_dataset(actor, workspace_id, dataset_id)
        filename, content, publish = self._snapshot(actor, provider, source_id, session_token)
        upload = self.uploads.upload(
            actor,
            workspace_id,
            dataset_id,
            filename,
            "text/csv",
            BytesIO(content),
            _publication_guard=lambda repo, upload, _revision: publish(
                repo, "connector.imported", upload.workspace_id, upload.id
            ),
        )
        logger.info(
            "connector_import provider=%s outcome=success upload_id=%s", provider, upload.id
        )
        return upload

    def stage_refresh(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        provider: str,
        source_id: str,
        session_token: str,
        refresh: RefreshService,
        options: dict[str, Any],
    ) -> RefreshCandidate:
        with refresh.uow() as repo:
            editor(repo, actor, workspace_id, dataset_id)
        filename, content, publish = self._snapshot(actor, provider, source_id, session_token)
        candidate = refresh.stage(
            actor,
            workspace_id,
            dataset_id,
            filename=filename,
            content_type="text/csv",
            content=content,
            _publication_guard=lambda repo, staged: publish(
                repo, "connector.refresh_staged", workspace_id, staged.id
            ),
            **options,
        )
        logger.info(
            "connector_refresh provider=%s outcome=%s candidate_id=%s",
            provider,
            candidate.status,
            candidate.id,
        )
        return candidate
