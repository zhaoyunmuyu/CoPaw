# -*- coding: utf-8 -*-
"""Tenant directory bootstrapper.

Creates the directory structure and seeds default agents for a single tenant.
Used by both ``copaw init --tenant-id`` (CLI) and ``TenantWorkspacePool`` (runtime)
so the bootstrap logic lives in one place.
"""
from pathlib import Path

from ..migration import (
    ensure_default_agent_exists,
)


class TenantInitializer:
    """Bootstrap a tenant directory with required structure and agents."""

    def __init__(self, base_working_dir: Path, tenant_id: str):
        self.base_working_dir = Path(base_working_dir).expanduser().resolve()
        self.tenant_id = tenant_id
        self.tenant_dir = self.base_working_dir / tenant_id

    def ensure_directory_structure(self) -> None:
        """Create the tenant directory skeleton (minimal bootstrap)."""
        for path in (
            self.tenant_dir,
            self.tenant_dir / "workspaces",
            self.tenant_dir / "media",
            self.tenant_dir / "secrets",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_default_agent(self) -> None:
        """Ensure the default agent workspace exists (minimal bootstrap).

        This only creates the agent declaration and directory structure,
        not the runtime.
        """
        ensure_default_agent_exists(working_dir=self.tenant_dir)

    def initialize_minimal(self) -> None:
        """Run minimal bootstrap sequence (idempotent).

        This is called on first tenant access and only ensures:
        - Directory structure exists
        - Default agent declaration exists

        No runtime components are started.
        """
        self.ensure_directory_structure()
        self.ensure_default_agent()
