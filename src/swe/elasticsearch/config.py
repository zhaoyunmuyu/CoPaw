# -*- coding: utf-8 -*-
"""Elasticsearch configuration module."""
import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ElasticsearchConfig(BaseModel):
    """Elasticsearch connection configuration."""

    host: str = Field(default="", description="ES host (empty=disabled)")
    port: int = Field(default=9200, description="ES port")
    user: str = Field(default="", description="ES username for auth")
    password: str = Field(default="", description="ES password for auth")
    index: str = Field(
        default="swe_model_outputs",
        description="ES index name",
    )


def get_elasticsearch_config(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    index: Optional[str] = None,
) -> ElasticsearchConfig:
    """Get Elasticsearch configuration.

    Configuration priority (highest to lowest):
    1. Explicitly passed parameters
    2. SWE_ES_* environment variables
    3. ElasticsearchConfig model defaults

    Args:
        host: ES host
        port: ES port
        user: ES username
        password: ES password
        index: ES index name

    Returns:
        ElasticsearchConfig instance
    """

    def _get_str(name: str, default: str) -> str:
        val = os.environ.get(name)
        return val if val else default

    def _get_password(name: str, default: str) -> str:
        val = os.environ.get(name)
        if not val:
            return default
        # Strip first 4 characters (e.g., "BEE_" prefix)
        return val[4:] if len(val) > 4 else val

    def _get_int(name: str, default: int) -> int:
        try:
            val = os.environ.get(name)
            if val is not None:
                return int(val)
        except (TypeError, ValueError):
            pass
        return default

    config = ElasticsearchConfig(
        host=host if host is not None else _get_str("SWE_ES_HOST", ""),
        port=port if port is not None else _get_int("SWE_ES_PORT", 9200),
        user=user if user is not None else _get_str("SWE_ES_USER", ""),
        password=password
        if password is not None
        else _get_password("SWE_ES_ACCESS", ""),
        index=index
        if index is not None
        else _get_str("SWE_ES_INDEX", "swe_model_outputs"),
    )

    if config.host:
        logger.info(
            "Elasticsearch config: host=%s, port=%s, index=%s",
            config.host,
            config.port,
            config.index,
        )
    else:
        logger.info("Elasticsearch is disabled (no host configured)")

    return config
