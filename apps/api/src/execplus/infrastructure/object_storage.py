"""Use case: Stores original validated uploads in S3-compatible object storage.

What it does: Derives and verifies immutable tenant keys and bounds reads.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, BinaryIO

from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

from execplus.domain.ingestion import IngestionError, ObjectMetadata, Upload


def storage_key(upload: Upload) -> str:
    key = (
        f"workspaces/{upload.workspace_id}/datasets/{upload.dataset_id}"
        f"/uploads/{upload.id}/original"
    )
    if upload.storage_key != key:
        raise IngestionError("invalid_storage_scope", "The upload storage scope is invalid.", 404)
    return key


class S3ObjectStorage:
    def __init__(self, client: S3Client, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def put(self, upload: Upload, content: BinaryIO) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=storage_key(upload),
                Body=content,
                ContentLength=upload.size,
                ContentType="application/octet-stream",
                Metadata={"sha256": upload.checksum},
            )
        except (BotoCoreError, ClientError) as error:
            raise IngestionError(
                "storage_unavailable", "Upload storage is unavailable. Try again.", 503
            ) from error

    def metadata(self, upload: Upload) -> ObjectMetadata:
        try:
            result = self.client.head_object(Bucket=self.bucket, Key=storage_key(upload))
            return ObjectMetadata(result["ContentLength"])
        except (BotoCoreError, ClientError) as error:
            raise IngestionError(
                "storage_unavailable", "Upload storage is unavailable.", 503
            ) from error

    def read(self, upload: Upload) -> bytes:
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=storage_key(upload))
            body = result["Body"]
            try:
                content = body.read(20 * 1024 * 1024 + 1)
            finally:
                body.close()
            if (
                len(content) != upload.size
                or hashlib.sha256(content).hexdigest() != upload.checksum
            ):
                raise IngestionError(
                    "storage_integrity", "The stored upload failed its integrity check.", 503
                )
            return content
        except (BotoCoreError, ClientError) as error:
            raise IngestionError(
                "storage_unavailable", "Upload storage is unavailable.", 503
            ) from error

    def delete(self, upload: Upload) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_key(upload))

    def ready(self) -> bool:
        self.client.head_bucket(Bucket=self.bucket)
        return True
