import asyncio

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from starlette.concurrency import run_in_threadpool


class S3Storage:
    """MinIO (S3 API) storage. Keeps no local state, safe to share across replicas."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    async def ensure_bucket(self, attempts: int = 30, delay_seconds: float = 2.0) -> None:
        """Create the bucket if needed; wait for MinIO to come up first."""
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                await run_in_threadpool(self._client.head_bucket, Bucket=self._bucket)
                return
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code not in ("404", "NoSuchBucket"):
                    raise
                try:
                    await run_in_threadpool(self._client.create_bucket, Bucket=self._bucket)
                except ClientError as create_exc:
                    if create_exc.response.get("Error", {}).get("Code") not in (
                        "BucketAlreadyOwnedByYou",
                        "BucketAlreadyExists",
                    ):
                        raise
                return
            except BotoCoreError as exc:  # connection refused, DNS, timeout — MinIO not up yet
                last_error = exc
                await asyncio.sleep(delay_seconds)
        raise RuntimeError(f"S3 bucket {self._bucket!r} is not ready") from last_error

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await run_in_threadpool(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> tuple[bytes, str] | None:
        def _read() -> tuple[bytes, str] | None:
            try:
                resp = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                    return None
                raise
            return resp["Body"].read(), resp.get("ContentType") or "application/octet-stream"

        return await run_in_threadpool(_read)
