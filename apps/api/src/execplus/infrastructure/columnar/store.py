"""Use case: Keeps immutable typed-Parquet snapshots in object storage with a local cache.

What it does: Streams uploads/downloads without loading files into memory, scopes keys to
their upload, verifies SHA-256 before a cached copy is used and bounds the cache size.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

from execplus.domain.ingestion import IngestionError, Upload


def columnar_key(upload: Upload) -> str:
    return (
        f"workspaces/{upload.workspace_id}/datasets/{upload.dataset_id}"
        f"/uploads/{upload.id}/columnar-v1.parquet"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class S3ColumnarStore:
    def __init__(
        self, client: S3Client, bucket: str, cache_dir: Path, cache_limit_bytes: int
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.cache_dir = cache_dir
        self.cache_limit_bytes = cache_limit_bytes

    def put(self, upload: Upload, path: Path, sha256: str) -> str:
        key = columnar_key(upload)
        try:
            self.client.upload_file(
                str(path),
                self.bucket,
                key,
                ExtraArgs={
                    "ContentType": "application/octet-stream",
                    "Metadata": {"sha256": sha256},
                },
            )
        except (BotoCoreError, ClientError) as error:
            raise IngestionError(
                "storage_unavailable", "Upload storage is unavailable. Try again.", 503
            ) from error
        return key

    def delete(self, upload: Upload) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=columnar_key(upload))

    def local(self, upload: Upload, key: str, sha256: str, size: int) -> str:
        if key != columnar_key(upload):
            raise IngestionError(
                "invalid_storage_scope", "The upload storage scope is invalid.", 404
            )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / f"{sha256}.parquet"
        if cached.is_file() and cached.stat().st_size == size:
            os.utime(cached)
            return str(cached)
        handle, name = tempfile.mkstemp(dir=self.cache_dir, suffix=".part")
        os.close(handle)
        staged = Path(name)
        try:
            self.client.download_file(self.bucket, key, str(staged))
            if staged.stat().st_size != size or _sha256(staged) != sha256:
                raise IngestionError(
                    "storage_integrity", "The stored snapshot failed its integrity check.", 503
                )
            staged.replace(cached)
        except (BotoCoreError, ClientError) as error:
            raise IngestionError(
                "storage_unavailable", "Upload storage is unavailable.", 503
            ) from error
        finally:
            staged.unlink(missing_ok=True)
        self._prune(cached)
        return str(cached)

    def _prune(self, keep: Path) -> None:
        files = sorted(
            (item for item in self.cache_dir.glob("*.parquet") if item != keep),
            key=lambda item: item.stat().st_mtime,
        )
        total = sum(item.stat().st_size for item in files) + keep.stat().st_size
        recent = time.time() - 600
        for item in files:
            if total <= self.cache_limit_bytes or item.stat().st_mtime > recent:
                break
            total -= item.stat().st_size
            item.unlink(missing_ok=True)
