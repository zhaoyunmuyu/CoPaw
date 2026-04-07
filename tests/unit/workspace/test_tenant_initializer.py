# -*- coding: utf-8 -*-
"""Unit tests for TenantInitializer.

Tests tenant directory initialization, idempotency, and runtime integration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from swe.app.workspace.tenant_initializer import TenantInitializer
from swe.app.workspace.tenant_pool import TenantWorkspacePool
from swe.constant import BUILTIN_QA_AGENT_ID


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


class TestEnsureSeededBootstrap:
    """Tests for ensure_seeded_bootstrap - runtime-safe skill seeding."""

    def test_ensure_seeded_bootstrap_seeds_skills_without_qa_agent(self, tmp_path):
        """Runtime bootstrap seeds skills but does not create QA agent."""
        from swe.agents.skills_manager import (
            get_skill_pool_dir,
            get_pool_skill_manifest_path,
            get_workspace_skills_dir,
            _write_json_atomic,
        )

        # Setup default tenant with skills
        default_init = TenantInitializer(tmp_path, "default")
        default_init.ensure_directory_structure()

        # Create default pool skill
        default_pool = get_skill_pool_dir(working_dir=default_init.tenant_dir)
        default_pool.mkdir(parents=True, exist_ok=True)

        pool_skill = default_pool / "pool-skill"
        pool_skill.mkdir()
        (pool_skill / "SKILL.md").write_text(
            "---\nname: pool-skill\ndescription: Pool Skill\n---\n",
            encoding="utf-8",
        )

        manifest_path = get_pool_skill_manifest_path(
            working_dir=default_init.tenant_dir,
        )
        _write_json_atomic(
            manifest_path,
            {"skills": {"pool-skill": {"name": "pool-skill"}}},
        )

        # Create default workspace skill
        default_workspace = default_init.tenant_dir / "workspaces" / "default"
        default_skills = get_workspace_skills_dir(default_workspace)
        default_skills.mkdir(parents=True, exist_ok=True)

        ws_skill = default_skills / "ws-skill"
        ws_skill.mkdir()
        (ws_skill / "SKILL.md").write_text(
            "---\nname: ws-skill\ndescription: WS Skill\n---\n",
            encoding="utf-8",
        )

        # Run ensure_seeded_bootstrap (runtime bootstrap path)
        new_init = TenantInitializer(tmp_path, "new-tenant")
        result = new_init.ensure_seeded_bootstrap()

        # Verify minimal bootstrap completed
        assert result["minimal"] is True

        # Verify skills were seeded
        assert result["pool_seed"]["seeded"] is True
        assert result["pool_seed"]["source"] == "default"
        assert "pool-skill" in result["pool_seed"]["skills"]

        assert result["workspace_seed"]["seeded"] is True
        assert "ws-skill" in result["workspace_seed"]["skills"]

        # Verify QA agent was NOT created (runtime bootstrap boundary)
        assert not (new_init.tenant_dir / "workspaces" / BUILTIN_QA_AGENT_ID).exists()

    def test_ensure_seeded_bootstrap_is_idempotent(self, tmp_path):
        """Runtime bootstrap is idempotent - second call does not re-seed."""
        from swe.agents.skills_manager import (
            get_skill_pool_dir,
            get_pool_skill_manifest_path,
            _write_json_atomic,
        )

        # Setup default tenant
        default_init = TenantInitializer(tmp_path, "default")
        default_init.ensure_directory_structure()

        default_pool = get_skill_pool_dir(working_dir=default_init.tenant_dir)
        default_pool.mkdir(parents=True, exist_ok=True)

        skill_dir = default_pool / "default-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: default-skill\ndescription: Default\n---\n",
            encoding="utf-8",
        )

        manifest_path = get_pool_skill_manifest_path(
            working_dir=default_init.tenant_dir,
        )
        _write_json_atomic(
            manifest_path,
            {"skills": {"default-skill": {"name": "default-skill"}}},
        )

        # First bootstrap
        new_init = TenantInitializer(tmp_path, "new-tenant")
        result1 = new_init.ensure_seeded_bootstrap()
        assert result1["pool_seed"]["seeded"] is True

        # Second bootstrap should be skipped
        result2 = new_init.ensure_seeded_bootstrap()
        assert result2["pool_seed"]["seeded"] is False
        assert result2["pool_seed"]["source"] is None

    def test_ensure_seeded_bootstrap_falls_back_to_builtin(self, tmp_path):
        """Runtime bootstrap falls back to builtin when no default template."""
        # Create default tenant without skills
        default_init = TenantInitializer(tmp_path, "default")
        default_init.ensure_directory_structure()

        # Run ensure_seeded_bootstrap for new tenant
        new_init = TenantInitializer(tmp_path, "new-tenant")
        result = new_init.ensure_seeded_bootstrap()

        assert result["minimal"] is True
        # Should fall back to builtin
        assert result["pool_seed"]["seeded"] is True
        assert result["pool_seed"]["source"] == "builtin"
        assert len(result["pool_seed"]["skills"]) > 0


class TestTenantPoolIntegration:
    """Runtime integration tests for TenantWorkspacePool."""

    def test_tenant_pool_get_or_create_initializes_tenant_dir(self, tmp_path):
        """TenantWorkspacePool.get_or_create initializes tenant directory structure."""
        pool = TenantWorkspacePool(tmp_path)

        workspace = pool.get_or_create("tenant-runtime")

        assert workspace is not None
        assert (tmp_path / "tenant-runtime" / "workspaces" / "default").is_dir()
