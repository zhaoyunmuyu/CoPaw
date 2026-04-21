# -*- coding: utf-8 -*-
"""Elasticsearch client for storing and querying model output."""
import logging
from datetime import datetime
from typing import Optional

from .config import ElasticsearchConfig

logger = logging.getLogger(__name__)

# Global client singleton
_client: Optional["ESClient"] = None


class ESClient:
    """Async Elasticsearch client for model output storage.

    Follows the same dependency-injection and graceful-degradation
    pattern as the database module.
    """

    def __init__(self, config: ElasticsearchConfig):
        self._config = config
        self._es = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to Elasticsearch and ensure index exists."""
        try:
            from elasticsearch import AsyncElasticsearch
        except ImportError:
            logger.warning(
                "elasticsearch package not installed. "
                "Install with: pip install elasticsearch[async]",
            )
            return

        # Build URL with scheme (required by newer elasticsearch versions)
        scheme = "https" if self._config.port == 443 else "http"
        hosts = [f"{scheme}://{self._config.host}:{self._config.port}"]
        kwargs: dict = {"hosts": hosts}

        if self._config.user and self._config.password:
            kwargs["basic_auth"] = (self._config.user, self._config.password)

        try:
            self._es = AsyncElasticsearch(**kwargs)
            await self._es.ping()
            self._connected = True
            await self._ensure_index()
            logger.info(
                "Elasticsearch connected: %s:%s, index=%s",
                self._config.host,
                self._config.port,
                self._config.index,
            )
        except Exception as e:
            logger.warning("Failed to connect to Elasticsearch: %s", e)
            self._connected = False

    async def _ensure_index(self) -> None:
        """Create index with mapping if it does not exist."""
        if not self._es or not self._connected:
            return

        try:
            exists = await self._es.indices.exists(index=self._config.index)
            if not exists:
                mapping = {
                    "mappings": {
                        "properties": {
                            "trace_id": {"type": "keyword"},
                            "model_output": {"type": "text"},
                            "created_at": {"type": "date"},
                        },
                    },
                }
                await self._es.indices.create(
                    index=self._config.index,
                    body=mapping,
                )
                logger.info("Created ES index: %s", self._config.index)
        except Exception as e:
            logger.warning("Failed to ensure ES index: %s", e)

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def index_message(self, trace_id: str, model_output: str) -> None:
        """Index a model output document.

        Args:
            trace_id: The trace ID to associate with.
            model_output: The assistant/model response text.
        """
        if not self._connected or not self._es:
            return

        doc = {
            "trace_id": trace_id,
            "model_output": model_output,
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            await self._es.index(
                index=self._config.index,
                id=trace_id,
                body=doc,
            )
            logger.debug("Indexed model_output for trace_id=%s", trace_id)
        except Exception as e:
            logger.warning(
                "Failed to index model_output for trace_id=%s: %s",
                trace_id,
                e,
            )

    async def get_message(self, trace_id: str) -> Optional[str]:
        """Get model output by trace ID.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            The model_output text, or None if not found.
        """
        if not self._connected or not self._es:
            return None

        try:
            result = await self._es.get(
                index=self._config.index,
                id=trace_id,
            )
            if result and result.get("found"):
                return result["_source"].get("model_output")
        except Exception:
            # Document not found or other error
            pass
        return None

    async def close(self) -> None:
        """Close the Elasticsearch connection."""
        if self._es:
            try:
                await self._es.close()
            except Exception as e:
                logger.warning("Failed to close ES connection: %s", e)
            finally:
                self._connected = False
                self._es = None


def init_es_client(config: ElasticsearchConfig) -> Optional[ESClient]:
    """Initialize the global ES client (does not connect).

    Args:
        config: Elasticsearch configuration.

    Returns:
        ESClient instance, or None if host is empty.
    """
    global _client

    if not config.host:
        _client = None
        return None

    _client = ESClient(config)
    return _client


def get_es_client() -> Optional[ESClient]:
    """Get the global ES client instance.

    Returns:
        The ESClient instance, or None if not initialized.
    """
    return _client
