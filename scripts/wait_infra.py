"""Use case: Verifies that local infrastructure accepts configured credentials.

What it does: Waits briefly for PostgreSQL and MinIO startup without printing secrets.
"""

import time

import boto3
from botocore.config import Config
from sqlalchemy import create_engine, text

from execplus.config import Settings


def main() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 2})
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
        config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
    )
    try:
        for attempt in range(10):
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                client.list_buckets()
                print("PostgreSQL and MinIO are accepting configured development credentials.")
                return
            except Exception:
                if attempt == 9:
                    raise SystemExit(
                        "Infrastructure unavailable: check startup, ports, and credentials."
                    ) from None
                time.sleep(1)
    finally:
        engine.dispose()
        client.close()


if __name__ == "__main__":
    main()
