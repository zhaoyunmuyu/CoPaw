# -*- coding: utf-8 -*-
"""Backup configuration models."""

from __future__ import annotations

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BackupEnvironmentConfig(BaseModel):
    """AWS S3 configuration for a single environment (dev/prd)."""

    aws_access_key_id: str
    aws_secret_access_key: str
    s3_bucket: str
    s3_prefix: str = "copaw"
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
        """Get active environment config based on COPAW_ENV."""
        env = os.environ.get("COPAW_ENV", "prd")
        return self.environments.get(env)


def _get_env_var(key: str, default: str = "") -> str:
    """Get environment variable value.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable value or default
    """
    return os.environ.get(key, default)


def load_backup_config_from_env(
    env: Optional[str] = None,
) -> Optional[BackupConfig]:
    """Load backup configuration from environment variables.

    Environment variables (per environment):
        COPAW_BACKUP_AWS_ACCESS_KEY_ID
        COPAW_BACKUP_AWS_SECRET_ACCESS_KEY
        COPAW_BACKUP_S3_BUCKET
        COPAW_BACKUP_S3_PREFIX (optional, default: "copaw")
        COPAW_BACKUP_S3_REGION (optional, default: "cn-north-1")
        COPAW_BACKUP_ENDPOINT_URL (optional)

    For multiple environments, use prefix:
        {ENV}_COPAW_BACKUP_AWS_ACCESS_KEY_ID (e.g., DEV_COPAW_BACKUP_AWS_ACCESS_KEY_ID)

    Args:
        env: Environment name ('dev' or 'prd'). If None, uses COPAW_ENV.

    Returns:
        BackupConfig if required environment variables are set, None otherwise.
    """
    if env is None:
        env = os.environ.get("COPAW_ENV", "prd")

    # Try environment-specific variables first, then fallback to generic
    env_prefix = f"{env.upper()}_"

    def get_var(key: str, default: str = "") -> str:
        """Get variable with environment prefix fallback."""
        # Try env-specific first (e.g., DEV_COPAW_BACKUP_S3_BUCKET)
        env_specific = _get_env_var(f"{env_prefix}{key}")
        if env_specific:
            return env_specific
        # Fallback to generic (e.g., COPAW_BACKUP_S3_BUCKET)
        return _get_env_var(key, default)

    # Check required variables
    aws_access_key_id = get_var("COPAW_BACKUP_AWS_ACCESS_KEY_ID")
    aws_secret_access_key = get_var("COPAW_BACKUP_AWS_SECRET_ACCESS_KEY")
    s3_bucket = get_var("COPAW_BACKUP_S3_BUCKET")

    if not all([aws_access_key_id, aws_secret_access_key, s3_bucket]):
        logger.debug(
            "Backup configuration not complete for environment '%s'. "
            "Required: COPAW_BACKUP_AWS_ACCESS_KEY_ID, "
            "COPAW_BACKUP_AWS_SECRET_ACCESS_KEY, COPAW_BACKUP_S3_BUCKET",
            env,
        )
        return None

    # Build environment config
    env_config = BackupEnvironmentConfig(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        s3_bucket=s3_bucket,
        s3_prefix=get_var("COPAW_BACKUP_S3_PREFIX", "copaw"),
        s3_region=get_var("COPAW_BACKUP_S3_REGION", "cn-north-1"),
        endpoint_url=get_var("COPAW_BACKUP_ENDPOINT_URL", ""),
    )

    return BackupConfig(
        environments={env: env_config},
    )


# Backward compatibility
def load_backup_config() -> Optional[BackupConfig]:
    """Load backup configuration from environment variables.

    This is the main entry point for loading backup configuration.

    Returns:
        BackupConfig if configuration is complete, None otherwise.
    """
    return load_backup_config_from_env()
