"""Use case: Runs browser acceptance against disposable real infrastructure.

What it does: Migrates an isolated schema, provisions a private bucket, and cleans both afterward.
"""

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import boto3
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> None:
    url = os.environ["EXECPLUS_TEST_DATABASE_URL"]
    schema = "browser_" + uuid4().hex
    bucket = "browser-" + uuid4().hex
    engine = create_engine(url)
    env = dict(os.environ)
    env.update(
        {
            "EXECPLUS_DATABASE_URL": make_url(url)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False),
            "EXECPLUS_ENVIRONMENT": "test",
            "EXECPLUS_OBJECT_STORE_BUCKET": bucket,
            "EXECPLUS_OBJECT_STORE_ENDPOINT": os.getenv(
                "EXECPLUS_TEST_OBJECT_STORE_ENDPOINT", "http://localhost:9000"
            ),
            "EXECPLUS_OBJECT_STORE_ACCESS_KEY": "execplus",
            "EXECPLUS_OBJECT_STORE_SECRET_KEY": "change-me",
            "EXECPLUS_WEB_ORIGIN": "http://127.0.0.1:3001",
            "NEXT_PUBLIC_API_URL": "http://127.0.0.1:8001",
        }
    )
    client = boto3.client(
        "s3",
        endpoint_url=env["EXECPLUS_OBJECT_STORE_ENDPOINT"],
        aws_access_key_id="execplus",
        aws_secret_access_key="change-me",
    )
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    client.create_bucket(Bucket=bucket)
    try:
        root = Path(__file__).resolve().parents[1]
        subprocess.run(
            ["python3", "-m", "alembic", "upgrade", "head"], env=env, cwd=root, check=True
        )
        subprocess.run(
            ["npm", "run", "test:e2e", "--workspace", "@execplus/web"],
            env=env,
            cwd=root,
            check=True,
        )
    finally:
        for item in client.list_objects_v2(Bucket=bucket).get("Contents", []):
            client.delete_object(Bucket=bucket, Key=item["Key"])
        client.delete_bucket(Bucket=bucket)
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    main()
