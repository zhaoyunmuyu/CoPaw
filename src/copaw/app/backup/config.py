# -*- coding: utf-8 -*-
"""Backup configuration models."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def get_backup_config_path() -> Path:
    """Get the path to the backup configuration file.

    Returns ~/.copaw/backup.json
    """
    # 1. 环境变量优先
    if env_path := os.environ.get("COPAW_BACKUP_CONFIG"):
        return Path(env_path).expanduser().resolve()

    # 2. 从当前文件往上找项目根目录（假设在 src/copaw/app/backup/config.py）
    # 往上 4 级到仓库根目录
    current_file = Path(__file__).resolve()
    repo_root = current_file.parent.parent.parent.parent.parent

    repo_config = repo_root / "backup.json"
    if repo_config.exists():
        return repo_config

    # 3. 默认路径
    return Path.home() / ".copaw" / "backup.json"


def load_backup_config() -> Optional[BackupConfig]:
    """Load backup configuration from file.

    Returns None if file doesn't exist or is invalid.
    """
    config_path = get_backup_config_path()
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BackupConfig(**data)
    except (json.JSONDecodeError, ValueError):
        return None


def save_backup_config(config: BackupConfig) -> None:
    """Save backup configuration to file.

    Creates parent directory if it doesn't exist.
    """
    config_path = get_backup_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(
            config.model_dump(mode="json"), f, indent=2, ensure_ascii=False
        )


class BackupEnvironmentConfig(BaseModel):
    """AWS S3 configuration for a single environment (dev/prd)."""

    aws_access_key_id: str
    aws_secret_access_key: str
    s3_bucket: str
    s3_prefix: str = "cmbswe"
    s3_region: str = "cn-north-1"
    endpoint_url: str = ""  # 可选，用于阿里云 ECS 等自定义 S3 端点


class BackupCompressionConfig(BaseModel):
    """Compression settings for backup archives."""

    level: int = Field(default=6, ge=0, le=9)


class BackupTimeoutConfig(BaseModel):
    """Timeout settings for backup operations (minutes)."""

    compress: int = 30
    upload: int = 30
    download: int = 30


class BackupConfig(BaseModel):
    """Root backup configuration."""

    environments: dict[str, BackupEnvironmentConfig] = Field(
        default_factory=dict,
    )
    compression: BackupCompressionConfig = Field(
        default_factory=BackupCompressionConfig,
    )
    timeout: BackupTimeoutConfig = Field(default_factory=BackupTimeoutConfig)

    def get_active_config(self) -> BackupEnvironmentConfig | None:
        """Get active environment config based on COPAW_BACKUP_ENV."""
        import os

        env = os.environ.get("COPAW_BACKUP_ENV", "dev")
        return self.environments.get(env)
