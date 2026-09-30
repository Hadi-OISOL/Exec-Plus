"""Use case: Provisions local development identity and object storage.

What it does: Creates a private bucket or prints a short-lived session token for an operator.
"""

import argparse
import asyncio
import json

from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.infrastructure.identity import LocalSessionIdentity
from execplus.infrastructure.object_storage import S3ObjectStorage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["provision-user", "init-storage", "deliver-reports", "process-refreshes"]
    )
    parser.add_argument("--email")
    args = parser.parse_args()
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
