# -*- coding: utf-8 -*-
"""Tests for tracing configuration."""

from swe.tracing.config import TracingConfig
from swe.database.config import DatabaseConfig


class TestDatabaseConfig:
    """Tests for DatabaseConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DatabaseConfig()

        assert config.host == "localhost"
        assert config.port == 3306
        assert config.user == "root"
        assert config.password == ""
        assert config.database == "swe"
        assert config.min_connections == 2
        assert config.max_connections == 10
        assert config.charset == "utf8mb4"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DatabaseConfig(
            host="tdsql.example.com",
            port=3307,
            user="swe_user",
            password="secret123",
            database="swe_prod",
            min_connections=5,
            max_connections=20,
        )

        assert config.host == "tdsql.example.com"
        assert config.port == 3307
        assert config.user == "swe_user"
        assert config.password == "secret123"
        assert config.database == "swe_prod"
        assert config.min_connections == 5
        assert config.max_connections == 20


class TestTracingConfig:
    """Tests for TracingConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TracingConfig()

        assert config.enabled is False
        assert config.batch_size == 100
        assert config.flush_interval == 5
        assert config.retention_days == 30
        assert config.sanitize_output is True
        assert config.max_output_length == 500
        assert config.database is None

    def test_custom_values(self):
        """Test custom configuration values."""
        db_config = DatabaseConfig(host="db.example.com")
        config = TracingConfig(
            enabled=True,
            batch_size=50,
            flush_interval=10,
            retention_days=60,
            sanitize_output=False,
            max_output_length=1000,
            database=db_config,
        )

        assert config.enabled is True
        assert config.batch_size == 50
        assert config.flush_interval == 10
        assert config.retention_days == 60
        assert config.sanitize_output is False
        assert config.max_output_length == 1000
        assert config.database.host == "db.example.com"

    def test_disabled_by_default(self):
        """Test that tracing is disabled by default."""
        config = TracingConfig()
        assert config.enabled is False

    def test_sanitization_enabled_by_default(self):
        """Test that sanitization is enabled by default."""
        config = TracingConfig()
        assert config.sanitize_output is True

    def test_retention_days_zero_means_no_cleanup(self):
        """Test that retention_days=0 means no cleanup."""
        config = TracingConfig(retention_days=0)
        assert config.retention_days == 0

    def test_database_optional(self):
        """Test that database configuration is optional."""
        config = TracingConfig()
        assert config.database is None

        # With database
        config_with_db = TracingConfig(database=DatabaseConfig())
        assert config_with_db.database is not None
