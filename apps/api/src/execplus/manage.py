"""Use case: Runs operator provisioning, storage initialization and bounded workers.

What it does: Composes configured services for explicit maintenance and durable job execution.
"""

import argparse
import asyncio
import getpass
import json
import signal
import sys
import warnings
from uuid import UUID

from execplus.application.job_worker import work
from execplus.application.services.jobs import JobService
from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.infrastructure.object_storage import S3ObjectStorage


async def _run_jobs(jobs: JobService, args: argparse.Namespace) -> dict[str, int]:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed = []
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop.set)
            installed.append(signum)
        return await work(
            jobs,
            stop,
            watch=args.watch,
            concurrency=args.concurrency,
            poll_seconds=args.poll_seconds,
        )
    finally:
        for signum in installed:
            loop.remove_signal_handler(signum)


def _jobs_command(args: argparse.Namespace) -> None:
    try:
        settings = Settings()
        runtime = build_runtime(settings)
        try:
            result = asyncio.run(_run_jobs(runtime.jobs, args))
        finally:
            runtime.engine.dispose()
    except (Exception, asyncio.CancelledError):
        print("worker action=process-jobs outcome=failed code=worker_failure", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        print("worker action=process-jobs outcome=stopped code=worker_interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    print(json.dumps(result))


def _staff_command(args: argparse.Namespace) -> None:
    try:
        runtime = build_runtime(Settings())
        try:
            result = runtime.operations.change_staff(
                args.email,
                args.role if args.action == "grant-staff" else None,
                confirmed_user_id=args.account_id,
                identity_checked=args.identity_checked,
            )
        finally:
            runtime.engine.dispose()
    except IngestionError as error:
        if error.code == "native_identity_check_required":
            print(
                "Native account email is unverified. Check the exact account ID with its holder, "
                "then use --account-id and --identity-checked.",
                file=sys.stderr,
            )
        else:
            print(
                "operator action=staff-access outcome=failed code=staff_access_failure",
                file=sys.stderr,
            )
        raise SystemExit(1) from None
    except Exception:
        print(
            "operator action=staff-access outcome=failed code=staff_access_failure", file=sys.stderr
        )
        raise SystemExit(1) from None
    print(json.dumps(result))


def _recover_account(args: argparse.Namespace) -> None:
    if not args.identity_checked or args.account_id is None or not sys.stdin.isatty():
        print(
            "Recovery requires an interactive operator, an exact --account-id "
            "and --identity-checked after separately checking account control.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New local password: ")
            repeated = getpass.getpass("Repeat new local password: ")
        if password != repeated:
            raise ValueError("password mismatch")
        runtime = build_runtime(Settings())
        try:
            runtime.accounts.recover(
                args.account_id, password, identity_checked=True, reenable=args.reenable
            )
        finally:
            runtime.engine.dispose()
    except (Exception, KeyboardInterrupt):
        print(
            "operator action=account-recovery outcome=failed code=account_recovery_failure",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(
        json.dumps(
            {
                "action": "account-recovered",
                "account_id": str(args.account_id),
                "reenabled": args.reenable,
            }
        )
    )


def _issue_reset_code(args: argparse.Namespace) -> None:
    if not args.identity_checked or args.account_id is None:
        print(
            "A reset code requires an exact --account-id and --identity-checked after "
            "separately checking account control.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        runtime = build_runtime(Settings())
        try:
            code, expires_at = runtime.accounts.issue_reset_code(
                args.account_id, identity_checked=True
            )
        finally:
            runtime.engine.dispose()
    except Exception:
        print("operator action=reset-code outcome=failed code=reset_code_failure", file=sys.stderr)
        raise SystemExit(1) from None
    print(
        json.dumps(
            {
                "action": "reset-code-issued",
                "account_id": str(args.account_id),
                "code": code,
                "expires_at": expires_at.isoformat(),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "provision-user",
            "init-storage",
            "deliver-reports",
            "process-refreshes",
            "process-jobs",
            "grant-staff",
            "revoke-staff",
            "recover-local-account",
            "issue-reset-code",
        ],
    )
    parser.add_argument("--email")
    parser.add_argument("--role", choices=["admin", "support"])
    parser.add_argument("--account-id", type=UUID)
    parser.add_argument("--identity-checked", action="store_true")
    parser.add_argument("--reenable", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if args.action == "issue-reset-code":
        _issue_reset_code(args)
        return
    if args.action == "recover-local-account":
        _recover_account(args)
        return
    if args.action in {"grant-staff", "revoke-staff"}:
        if not args.email or (args.action == "grant-staff" and not args.role):
            parser.error("--email and a grant --role are required")
        _staff_command(args)
        return
    if args.action == "process-jobs":
        _jobs_command(args)
        return
    settings = Settings()
    runtime = build_runtime(settings)
    try:
        if args.action == "provision-user":
            if not args.email:
                parser.error("--email is required")
            if not isinstance(runtime.identity, LocalSessionIdentity):
                parser.error("local identity is required")
            print(runtime.identity.provision(args.email))
        elif args.action == "process-refreshes":
            refreshed = runtime.refresh.process_due()
            observed = asyncio.run(runtime.monitoring.process())
            print(json.dumps(dict(refresh=refreshed, observations=observed)))
        elif args.action == "deliver-reports":
            print(json.dumps(asyncio.run(runtime.reports.deliver_due())))
        else:
            storage = runtime.service.storage
            if not isinstance(storage, S3ObjectStorage):
                parser.error("S3 storage is required")
            try:
                storage.client.head_bucket(Bucket=settings.object_store_bucket)
            except storage.client.exceptions.ClientError as error:
                if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                    raise
                storage.client.create_bucket(Bucket=settings.object_store_bucket)
    finally:
        runtime.engine.dispose()


if __name__ == "__main__":
    main()
