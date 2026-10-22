"""Use case: Provides password accounts and resumable private workspace setup.

What it does: Applies local identity, credential revocation, invitation proof and guide policies.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from execplus.application.account_ports import AccountRepository, AccountStore, PasswordHasher
from execplus.application.services.workspaces import checked_name, normalized_email
from execplus.domain.accounts import (
    GUIDE_ACTIONS,
    GUIDE_LABELS,
    GUIDE_STEPS,
    AccountSession,
    GuideProgress,
    LocalAccount,
    account_text,
    authentication_failed,
    guide_choices,
    password_input,
)
from execplus.domain.ingestion import (
    AuditEvent,
    IngestionError,
    Membership,
    User,
    Workspace,
    require_manager,
)
from execplus.domain.profiling import UsageEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AccountService:
    def __init__(
        self,
        store: AccountStore,
        passwords: PasswordHasher,
        *,
        registration_enabled: bool = True,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.store, self.passwords, self.registration_enabled, self.clock = (
            store,
            passwords,
            registration_enabled,
            clock,
        )

    def _rate(self, operation: str, identifier: str, peer: str) -> None:
        if not self.store.consume_auth_attempt(operation, identifier, peer, self.clock()):
            raise IngestionError(
                "authentication_rate_limit", "Too many attempts. Please try again later.", 429
            )

    def register(
        self, email: str, password: str, display_name: str, workspace_name: str, peer: str
    ) -> None:
        if not self.registration_enabled:
            raise IngestionError("registration_unavailable", "Local registration is disabled.", 403)
        email, display_name, workspace_name = (
            normalized_email(account_text(email)),
            checked_name(account_text(display_name)),
            checked_name(account_text(workspace_name)),
        )
        password_input(password, new=True)
        self._rate("register", email, peer)
        password_hash = self.passwords.hash(password)
        now = self.clock()
        actor = User(uuid4(), email, display_name, now)
        workspace = Workspace(uuid4(), workspace_name, 3, now, now)
        with self.store.transaction() as repo:
            if not repo.new_user(actor):
                repo.account_event(None, "registration.unavailable", now)
                return
            repo.add_local_account(LocalAccount(actor, password_hash, now, None))
            repo.add(workspace)
            repo.add(Membership(workspace.id, actor.id, "owner", now))
            repo.initialize_native_workspace_plan(workspace.id, actor.id, now)
            for action, kind, rid in (
                ("workspace.created", "workspace", workspace.id),
                ("membership.created", "user", actor.id),
            ):
                repo.add(AuditEvent(uuid4(), workspace.id, actor.id, action, kind, rid, now))
            for kind, quantity, rid in (
                ("seat_added", 1, actor.id),
                ("seat_limit", 3, workspace.id),
            ):
                repo.add(UsageEvent(uuid4(), workspace.id, actor.id, kind, quantity, rid, now))
            repo.account_event(actor.id, "registration.completed", now)

    def _session(self, repo: AccountRepository, actor: User, now: datetime) -> AccountSession:
        token, expires_at = secrets.token_urlsafe(32), now + timedelta(hours=8)
        repo.add_account_session(actor.id, hashlib.sha256(token.encode()).hexdigest(), expires_at)
        repo.account_event(actor.id, "session.created", now)
        return AccountSession(token, expires_at, actor)

    def login(self, email: str, password: str, peer: str) -> AccountSession:
        email = normalized_email(account_text(email))
        password_input(password)
        self._rate("login", email, peer)
        with self.store.transaction() as repo:
            account = repo.account_by_email(email)
        valid = self.passwords.verify(password, account.password_hash if account else None)
        if not valid or account is None or account.disabled_at is not None:
            with self.store.transaction() as repo:
                repo.account_event(
                    account.user.id if account else None, "session.rejected", self.clock()
                )
            raise authentication_failed()
        with self.store.transaction() as repo:
            self._current(repo, account)
            return self._session(repo, account.user, self.clock())

    @staticmethod
    def _current(repo: AccountRepository, previous: LocalAccount) -> LocalAccount:
        current = repo.local_account(previous.user.id, lock=True)
        if (
            current is None
            or current.disabled_at is not None
            or not hmac.compare_digest(current.password_hash, previous.password_hash)
        ):
            raise authentication_failed()
        return current

    def _password_proof(
        self, actor: User, password: str, operation: str, peer: str
    ) -> LocalAccount:
        password_input(password)
        self._rate(operation, str(actor.id), peer)
        with self.store.transaction() as repo:
            account = repo.local_account(actor.id)
        valid = self.passwords.verify(password, account.password_hash if account else None)
        if not valid or account is None or account.disabled_at is not None:
            with self.store.transaction() as repo:
                repo.account_event(actor.id, "credential.rejected", self.clock())
            raise authentication_failed()
        return account

    def change_password(
        self, actor: User, current_password: str, new_password: str, peer: str
    ) -> AccountSession:
        password_input(new_password, new=True)
        account = self._password_proof(actor, current_password, "password", peer)
        digest, now = self.passwords.hash(new_password), self.clock()
        with self.store.transaction() as repo:
            repo.lock_account_workspaces(actor.id)
            self._current(repo, account)
            repo.update_local_account(
                replace(account, password_hash=digest, password_changed_at=now)
            )
            repo.revoke_account_credentials(actor.id, now)
            repo.set_reset_code(actor.id, None, now)
            repo.account_event(actor.id, "password.changed", now)
            return self._session(repo, actor, now)

    def disable(self, actor: User, password: str, confirmed: bool, peer: str) -> None:
        if confirmed is not True:
            raise IngestionError(
                "confirmation_required", "Confirm that you want to disable your account.", 422
            )
        account = self._password_proof(actor, password, "disable", peer)
        now = self.clock()
        with self.store.transaction() as repo:
            repo.lock_account_workspaces(actor.id)
            self._current(repo, account)
            repo.update_local_account(replace(account, disabled_at=now))
            repo.revoke_account_credentials(actor.id, now)
            repo.account_event(actor.id, "account.disabled", now)

    def recover(
        self, user_id: UUID, password: str, *, identity_checked: bool, reenable: bool = False
    ) -> None:
        if identity_checked is not True:
            raise IngestionError(
                "identity_check_required",
                "An authorized operator must first verify account control.",
                403,
            )
        password_input(password, new=True)
        digest, now = self.passwords.hash(password), self.clock()
        with self.store.transaction() as repo:
            repo.lock_account_workspaces(user_id)
            account = repo.local_account(user_id, lock=True)
            if account is None:
                raise IngestionError(
                    "account_unavailable", "This local password account is unavailable.", 404
                )
            repo.update_local_account(
                replace(
                    account,
                    password_hash=digest,
                    password_changed_at=now,
                    disabled_at=None if reenable else account.disabled_at,
                )
            )
            repo.revoke_account_credentials(user_id, now)
            repo.set_reset_code(user_id, None, now)
            repo.account_event(
                user_id, "account.recovered", now, "operator_checked_account_control"
            )
            if reenable and account.disabled_at is not None:
                repo.account_event(
                    user_id, "account.enabled", now, "operator_checked_account_control"
                )

    def issue_reset_code(self, user_id: UUID, *, identity_checked: bool) -> tuple[str, datetime]:
        if identity_checked is not True:
            raise IngestionError(
                "identity_check_required",
                "An authorized operator must first verify account control.",
                403,
            )
        code, now = secrets.token_urlsafe(16), self.clock()
        expires_at = now + timedelta(minutes=30)
        with self.store.transaction() as repo:
            account = repo.local_account(user_id, lock=True)
            if account is None or account.disabled_at is not None:
                raise IngestionError(
                    "account_unavailable", "This local password account is unavailable.", 404
                )
            repo.set_reset_code(user_id, hashlib.sha256(code.encode()).hexdigest(), expires_at)
            repo.account_event(
                user_id, "reset_code.issued", now, "operator_checked_account_control"
            )
        return code, expires_at

    def reset_password(self, email: str, code: str, new_password: str, peer: str) -> None:
        email = normalized_email(account_text(email))
        password_input(new_password, new=True)
        self._rate("reset", email, peer)
        invalid = IngestionError(
            "reset_code_invalid", "This reset code is incorrect, used or expired.", 401
        )
        digest, now = self.passwords.hash(new_password), self.clock()
        with self.store.transaction() as repo:
            account = repo.account_by_email(email)
            if account is None:
                raise invalid
            repo.lock_account_workspaces(account.user.id)
            account = repo.local_account(account.user.id, lock=True)
            stored = repo.reset_code(account.user.id) if account else None
            if (
                account is None
                or stored is None
                or account.disabled_at is not None
                or stored[1] <= now
                or not hmac.compare_digest(
                    stored[0], hashlib.sha256(account_text(code).encode()).hexdigest()
                )
            ):
                raise invalid
            repo.update_local_account(
                replace(account, password_hash=digest, password_changed_at=now)
            )
            repo.set_reset_code(account.user.id, None, now)
            repo.revoke_account_credentials(account.user.id, now)
            repo.account_event(account.user.id, "password.reset", now, "operator_reset_code")

    def profile(self, actor: User) -> dict[str, Any]:
        with self.store.transaction() as repo:
            repo.require_active_actor(actor.id)
            account = repo.local_account(actor.id)
            return {
                "user_id": str(actor.id),
                "kind": "local_password"
                if account
                else ("external_google" if repo.is_self_service_account(actor.id) else "operator"),
                "email_verified": False,
                "password_changed_at": account.password_changed_at if account else None,
            }

    def events(self, actor: User) -> tuple[dict[str, Any], ...]:
        with self.store.transaction() as repo:
            repo.require_active_actor(actor.id)
            return repo.account_events(actor.id)

    def approve_invitation(
        self, actor: User, wid: UUID, invitation_id: UUID, user_id: UUID, identity_checked: bool
    ) -> None:
        if identity_checked is not True:
            raise IngestionError(
                "identity_check_required",
                "Check the intended account with your teammate before approving it.",
                422,
            )
        now = self.clock()
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            manager = repo.membership(wid, actor.id)
            require_manager(manager.role)
            invitation = repo.invitation(wid, invitation_id)
            if invitation.role == "admin" and manager.role != "owner":
                raise IngestionError(
                    "forbidden", "Only the owner can approve an admin invitation.", 403
                )
            if invitation.status != "pending" or invitation.expires_at <= now:
                raise IngestionError(
                    "invitation_unavailable", "This invitation is no longer pending.", 409
                )
            target = repo.user(user_id)
            if not repo.is_self_service_account(user_id) or target.email != invitation.email:
                raise IngestionError(
                    "account_unavailable",
                    "The intended account is unavailable for this invitation.",
                    404,
                )
            repo.require_active_actor(user_id)
            repo.approve_invitation_identity(invitation_id, user_id, actor.id, now)
            repo.add(
                AuditEvent(
                    uuid4(),
                    wid,
                    actor.id,
                    "invitation.identity_approved",
                    "invitation",
                    invitation_id,
                    now,
                )
            )

    def _guide(self, repo: AccountRepository, actor: User, wid: UUID) -> dict[str, Any]:
        repo.membership(wid, actor.id)
        progress = repo.onboarding_progress(wid, actor.id)
        actions = repo.onboarding_actions(wid, actor.id)
        value: dict[str, Any] = (
            asdict(progress)
            if progress
            else {
                "workspace_id": wid,
                "user_id": actor.id,
                "version": 0,
                "active_step": "data",
                "skipped_steps": (),
                "paused": False,
                "finished": False,
                "updated_at": None,
            }
        )
        value["steps"] = [
            {
                "id": step,
                "label": GUIDE_LABELS[step],
                "observed": step == "setup" or bool(GUIDE_ACTIONS.get(step, set()) & actions),
                "skipped": bool(progress and step in progress.skipped_steps),
            }
            for step in GUIDE_STEPS
        ]
        value["notice"] = (
            "This private guide records your place. Skipping or finishing does not "
            "perform an analysis or confirm data meanings."
        )
        return value

    def guide(self, actor: User, wid: UUID) -> dict[str, Any]:
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            return self._guide(repo, actor, wid)

    def save_guide(
        self,
        actor: User,
        wid: UUID,
        expected_version: int,
        active_step: str,
        skipped_steps: list[str],
        paused: bool,
        finished: bool,
    ) -> dict[str, Any]:
        skipped = guide_choices(active_step, skipped_steps)
        if (
            type(expected_version) is not int
            or not 0 <= expected_version < 2147483647
            or type(paused) is not bool
            or type(finished) is not bool
        ):
            raise IngestionError(
                "invalid_guide", "Use the current guide version and available choices.", 422
            )
        with self.store.transaction() as repo:
            repo.workspace(wid, lock=True)
            current = self._guide(repo, actor, wid)
            if current["version"] != expected_version:
                raise IngestionError(
                    "guide_conflict", "Your guide changed. Reload before saving.", 409
                )
            if finished and any(
                not step["observed"] and step["id"] not in skipped for step in current["steps"]
            ):
                raise IngestionError(
                    "guide_unfinished",
                    "Complete or explicitly skip the remaining guide steps.",
                    422,
                )
            now = self.clock()
            progress = GuideProgress(
                wid, actor.id, expected_version + 1, active_step, skipped, paused, finished, now
            )
            repo.save_onboarding_progress(progress)
            repo.add(
                AuditEvent(uuid4(), wid, actor.id, "onboarding.updated", "user", actor.id, now)
            )
            return self._guide(repo, actor, wid)
