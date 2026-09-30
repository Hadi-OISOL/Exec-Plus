"""Use case: Verifies an isolated restore of the private demo's database and source objects.

What it does: Checks restored tenant records against object checksums without modifying live data.
"""

import argparse
import hashlib
import json
import re

import boto3
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from execplus.config import Settings
from execplus.infrastructure.persistence.schema import documents, uploads, workspaces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"execplus_restore_[a-z0-9]+", args.database):
        parser.exit(2, "Use an isolated execplus_restore_ database.\n")
    settings = Settings()
    if settings.environment != "local" or settings.object_store_bucket != "execplus-demo":
        parser.exit(2, "Only the private fictional demo is supported.\n")
    engine = create_engine(make_url(settings.database_url).set(database=args.database))
    client = boto3.client(
        "s3",
        endpoint_url="http://127.0.0.1:19490",
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
    )
    checked = 0
    try:
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            for wid in connection.execute(select(workspaces.c.id)).scalars():
                records = [
                    (item["storage_key"], item["checksum"])
                    for item in connection.execute(
                        select(uploads).where(uploads.c.workspace_id == wid)
                    ).mappings()
                ]
                records.extend(
                    (f"workspaces/{wid}/documents/{item['id']}/original", item["checksum"])
                    for item in connection.execute(
                        select(documents).where(documents.c.workspace_id == wid)
                    ).mappings()
                )
                for key, checksum in records:
                    if not key.startswith(f"workspaces/{wid}/"):
                        raise ValueError("Restored object violates workspace prefix")
                    body = client.get_object(Bucket=settings.object_store_bucket, Key=key)["Body"]
                    try:
                        actual = hashlib.sha256(body.read()).hexdigest()
                    finally:
                        body.close()
                    if actual != checksum:
                        raise ValueError("Restored source checksum mismatch")
                    checked += 1
        if checked < 9:
            raise ValueError("Expected at least three demo uploads and six documents")
        print(
            json.dumps(
                {
                    "scope": "private-demo-restore",
                    "migration": version,
                    "verified_objects": checked,
                    "passed": True,
                }
            )
        )
    finally:
        engine.dispose()
        client.close()


if __name__ == "__main__":
    main()
