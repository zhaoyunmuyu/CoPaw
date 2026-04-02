# -*- coding: utf-8 -*-
"""Tenant directory bootstrapper.

Creates the directory structure and seeds default agents / skill pool
for a single tenant.  Used by both ``copaw init --tenant-id`` (CLI) and
``TenantWorkspacePool.get_or_create`` (runtime) so the bootstrap logic
lives in one place.
"""
from pathlib import Path

from ..migration import (
    ensure_default_agent_exists,
    ensure_qa_agent_exists,
    migrate_legacy_skills_to_skill_pool,
)
from ...agents.skills_manager import ensure_skill_pool_initialized


class TenantInitializer:
    """Bootstrap a tenant directory with required structure and agents."""

    def __init__(self, base_working_dir: Path, tenant_id: str):
        self.base_working_dir = Path(base_working_dir).expanduser().resolve()
        self.tenant_id = tenant_id
        self.tenant_dir = self.base_working_dir / tenant_id

    def ensure_directory_structure(self) -> None:
        """Create the tenant directory skeleton."""
        for path in (
            self.tenant_dir,
            self.tenant_dir / "workspaces",
            self.tenant_dir / "media",
            self.tenant_dir / "secrets",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_default_agent(self) -> None:
        """Ensure the default agent workspace exists."""
        ensure_default_agent_exists(working_dir=self.tenant_dir)

    def ensure_qa_agent(self) -> None:
        """Ensure the builtin QA agent workspace exists."""
        ensure_qa_agent_exists(working_dir=self.tenant_dir)

    def ensure_skill_pool(self) -> None:
        """Ensure the skill pool is initialized and legacy skills migrated."""
        ensure_skill_pool_initialized(working_dir=self.tenant_dir)
        migrate_legacy_skills_to_skill_pool(working_dir=self.tenant_dir)

    def initialize(self) -> None:
        """Run the full bootstrap sequence (idempotent)."""
        self.ensure_directory_structure()
        self.ensure_default_agent()
        self.ensure_qa_agent()
        self.ensure_skill_pool()
