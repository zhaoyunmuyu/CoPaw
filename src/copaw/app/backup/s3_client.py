# -*- coding: utf-8 -*-
"""AWS S3 client for backup operations."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .config import BackupEnvironmentConfig


class S3BackupClient:
    """S3 client wrapper for backup operations."""

    def __init__(self, config: BackupEnvironmentConfig):
        self.config = config
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.s3_region,
        )
        self.bucket = config.s3_bucket
        self.prefix = config.s3_prefix

    def upload(self, local_path: Path, date: str, user_id: str) -> str:
        """Upload a file to S3.

        Args:
            local_path: Local file path to upload
            date: Date folder (YYYY-MM-DD)
            user_id: User identifier

        Returns:
            Full S3 key
        """
        s3_key = f"{self.prefix}/{date}/{user_id}.zip"
        self._s3.upload_file(str(local_path), self.bucket, s3_key)
        return s3_key

    def download(self, s3_key: str, local_path: Path) -> None:
        """Download a file from S3.

        Args:
            s3_key: Full S3 key (including prefix)
            local_path: Local destination path
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._s3.download_file(self.bucket, s3_key, str(local_path))

    def list_backups(
        self,
        user_id: Optional[str] = None,
        date: Optional[str] = None,
    ) -> dict:
        """List available backups in S3.

        Args:
            user_id: Filter by user ID
            date: Filter by date (YYYY-MM-DD)

        Returns:
            Dict with dates list and backups grouped by date
        """
        prefix = f"{self.prefix}/"
        if date:
            prefix = f"{self.prefix}/{date}/"

        backups = {}
        continuation_token = None

        while True:
            params = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = self._s3.list_objects_v2(**params)

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]
                    # Parse key: cmbswe/{date}/{user_id}.zip
                    parts = key.replace(f"{self.prefix}/", "").split("/")
                    if len(parts) != 2 or not parts[1].endswith(".zip"):
                        continue

                    backup_date = parts[0]
                    backup_user_id = parts[1].replace(".zip", "")

                    if user_id and backup_user_id != user_id:
                        continue

                    if backup_date not in backups:
                        backups[backup_date] = {}

                    backups[backup_date][backup_user_id] = {
                        "s3_key": key,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    }

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

        dates = sorted(backups.keys(), reverse=True)
        return {"dates": dates, "backups": backups}

    def get_backup_key(self, date: str, user_id: str) -> str:
        """Get full S3 key for a backup.

        Args:
            date: Date folder (YYYY-MM-DD)
            user_id: User identifier

        Returns:
            Full S3 key including prefix
        """
        return f"{self.prefix}/{date}/{user_id}.zip"

    def backup_exists(self, date: str, user_id: str) -> bool:
        """Check if a backup exists in S3.

        Args:
            date: Date folder (YYYY-MM-DD)
            user_id: User identifier

        Returns:
            True if backup exists, False otherwise
        """
        key = self.get_backup_key(date, user_id)
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
