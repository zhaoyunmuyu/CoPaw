# -*- coding: utf-8 -*-
"""Tests for Elasticsearch client."""
# pylint: disable=protected-access  # Tests need to access internal state
from unittest.mock import AsyncMock, patch

import pytest

from swe.elasticsearch.config import ElasticsearchConfig
from swe.elasticsearch.client import ESClient, init_es_client, get_es_client


class TestElasticsearchConfig:
    """Tests for ElasticsearchConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ElasticsearchConfig()
        assert config.host == ""
        assert config.port == 9200
        assert config.user == ""
        assert config.password == ""
        assert config.index == "swe_model_outputs"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ElasticsearchConfig(
            host="localhost",
            port=9201,
            user="admin",
            password="secret",
            index="custom_index",
        )
        assert config.host == "localhost"
        assert config.port == 9201
        assert config.user == "admin"
        assert config.password == "secret"
        assert config.index == "custom_index"


class TestESClient:
    """Tests for ESClient."""

    def test_init(self):
        """Test ESClient initialization."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        assert client._config == config
        assert client._es is None
        assert client._connected is False

    def test_is_connected_property(self):
        """Test is_connected property."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        assert client.is_connected is False
        client._connected = True
        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_without_package(self):
        """Test connect when elasticsearch package is not installed."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)

        with patch.dict("sys.modules", {"elasticsearch": None}):
            await client.connect()
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_index_message_when_not_connected(self):
        """Test index_message does nothing when not connected."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        # Should not raise, just return
        await client.index_message("trace-123", "output text")

    @pytest.mark.asyncio
    async def test_get_message_when_not_connected(self):
        """Test get_message returns None when not connected."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        result = await client.get_message("trace-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_message_not_found(self):
        """Test get_message returns None when document not found."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        client._connected = True

        mock_es = AsyncMock()
        mock_es.get.return_value = {"found": False}
        client._es = mock_es

        result = await client.get_message("trace-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_message_found(self):
        """Test get_message returns model_output when document found."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        client._connected = True

        mock_es = AsyncMock()
        mock_es.get.return_value = {
            "found": True,
            "_source": {
                "trace_id": "trace-123",
                "model_output": "This is the model response",
            },
        }
        client._es = mock_es

        result = await client.get_message("trace-123")
        assert result == "This is the model response"

    @pytest.mark.asyncio
    async def test_close(self):
        """Test close method."""
        config = ElasticsearchConfig(host="localhost")
        client = ESClient(config)
        mock_es = AsyncMock()
        client._es = mock_es
        client._connected = True

        await client.close()
        mock_es.close.assert_called_once()
        assert client._connected is False
        assert client._es is None


class TestGlobalClient:
    """Tests for global client functions."""

    def test_init_es_client_no_host(self):
        """Test init_es_client returns None when host is empty."""
        config = ElasticsearchConfig(host="")
        result = init_es_client(config)
        assert result is None

    def test_init_es_client_with_host(self):
        """Test init_es_client creates client when host is set."""
        config = ElasticsearchConfig(host="localhost")
        client = init_es_client(config)
        assert client is not None
        assert isinstance(client, ESClient)

    def test_get_es_client(self):
        """Test get_es_client returns the global client."""
        config = ElasticsearchConfig(host="localhost")
        init_es_client(config)
        client = get_es_client()
        assert client is not None


class TestTraceModelOutput:
    """Tests for Trace model with model_output field."""

    def test_trace_model_output_field(self):
        """Test Trace has model_output field with default None."""
        from datetime import datetime

        from swe.tracing.models import Trace

        trace = Trace(
            trace_id="trace-123",
            source_id="source-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )
        assert trace.model_output is None

    def test_trace_with_model_output(self):
        """Test Trace can have model_output set."""
        from datetime import datetime

        from swe.tracing.models import Trace

        trace = Trace(
            trace_id="trace-123",
            source_id="source-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
            model_output="This is the assistant response.",
        )
        assert trace.model_output == "This is the assistant response."
