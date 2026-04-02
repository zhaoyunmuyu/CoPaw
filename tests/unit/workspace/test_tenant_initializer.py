# -*- coding: utf-8 -*-
"""Unit tests for TenantInitializer.

Tests tenant directory initialization, idempotency, and runtime integration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from copaw.app.workspace.tenant_initializer import TenantInitializer
from copaw.app.workspace.tenant_pool import TenantWorkspacePool
from copaw.constant import BUILTIN_QA_AGENT_ID


class TestTenantInitializerBasics:
    """Basic TenantInitializer functionality tests."""

    def test_tenant_initializer_creates_expected_structure(self, tmp_path):
        """TenantInitializer creates tenant directory with workspaces and skill_pool."""
        initializer = TenantInitializer(tmp_path, "tenant-acme")
        initializer.initialize()

        tenant_dir = tmp_path / "tenant-acme"
        assert tenant_dir.is_dir()
        assert (tenant_dir / "workspaces" / "default").is_dir()
        assert (tenant_dir / "workspaces" / BUILTIN_QA_AGENT_ID).is_dir()
        assert (tenant_dir / "skill_pool").is_dir()

    def test_tenant_initializer_is_idempotent(self, tmp_path):
        """TenantInitializer can be called multiple times without errors."""
        initializer = TenantInitializer(tmp_path, "tenant-acme")

        initializer.initialize()
        initializer.initialize()

        tenant_dir = tmp_path / "tenant-acme"
        assert (tenant_dir / "workspaces" / "default" / "jobs.json").exists()


class TestTenantPoolIntegration:
    """Runtime integration tests for TenantWorkspacePool."""

    def test_tenant_pool_get_or_create_initializes_tenant_dir(self, tmp_path):
        """TenantWorkspacePool.get_or_create initializes tenant directory structure."""
        pool = TenantWorkspacePool(tmp_path)

        workspace = pool.get_or_create("tenant-runtime")

        assert workspace is not None
        assert (tmp_path / "tenant-runtime" / "workspaces" / "default").is_dir()
