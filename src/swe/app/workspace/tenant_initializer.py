# -*- coding: utf-8 -*-
"""Tenant directory bootstrapper.

Creates the directory structure and seeds default agents for a single tenant.
Used by both ``copaw init --tenant-id`` (CLI) and ``TenantWorkspacePool`` (runtime)
so the bootstrap logic lives in one place.
"""
import json
from pathlib import Path
from typing import Any

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

    def initialize(self) -> dict[str, Any]:
        """Run full tenant initialization (backward compatibility alias).

        This is an alias for initialize_full() for backward compatibility
        with existing code and tests.

        Returns:
            Dict with initialization results (see initialize_full()).
        """
        return self.initialize_full()

    def _has_skill_pool_state(self) -> bool:
        """Check if tenant already has skill pool state.

        Returns:
            True if skill pool exists and has content, False otherwise.
        """
        from ...agents.skills_manager import (
            get_skill_pool_dir,
            get_pool_skill_manifest_path,
        )

        pool_dir = get_skill_pool_dir(working_dir=self.tenant_dir)
        manifest_path = get_pool_skill_manifest_path(
            working_dir=self.tenant_dir,
        )

        # Check if manifest exists and has skills
        if manifest_path.exists():
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"),
                )
                if manifest.get("skills"):
                    return True
            except (json.JSONDecodeError, OSError):
                pass

        # Check if pool directory has skill subdirectories
        if pool_dir.exists():
            for item in pool_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    return True

        return False

    def _has_default_workspace_skills(self) -> bool:
        """Check if default workspace already has skill state.

        Returns:
            True if default workspace has skills, False otherwise.
        """
        from ...agents.skills_manager import (
            get_workspace_skills_dir,
            get_workspace_skill_manifest_path,
        )

        default_workspace = self.tenant_dir / "workspaces" / "default"
        skills_dir = get_workspace_skills_dir(default_workspace)
        manifest_path = get_workspace_skill_manifest_path(default_workspace)

        # Check if manifest exists and has skills
        if manifest_path.exists():
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"),
                )
                if manifest.get("skills"):
                    return True
            except (json.JSONDecodeError, OSError):
                pass

        # Check if skills directory has skill subdirectories
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    return True

        return False

    def _copy_skill_directories(
        self,
        source_dir: Path,
        target_dir: Path,
    ) -> list[str]:
        """Copy skill directories from source to target.

        Args:
            source_dir: Source directory containing skill subdirectories.
            target_dir: Target directory to copy skills into.

        Returns:
            List of copied skill names.
        """
        import shutil

        copied: list[str] = []

        if not source_dir.exists():
            return copied

        target_dir.mkdir(parents=True, exist_ok=True)

        for item in source_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                target_skill_dir = target_dir / item.name
                if target_skill_dir.exists():
                    shutil.rmtree(target_skill_dir)
                shutil.copytree(item, target_skill_dir)
                copied.append(item.name)

        return copied

    def seed_skill_pool_from_default(self) -> dict[str, Any]:
        """Seed skill pool from default tenant (idempotent).

        Copies skill_pool content from default tenant when target tenant
        has no skill pool state yet. Falls back to builtin initialization
        when no template exists.

        Returns:
            Dict with result status:
            - "seeded": True if seeded from default, False otherwise
            - "source": "default", "builtin", or None
            - "skills": list of skill names copied (if any)
        """
        from ...agents.skills_manager import (
            get_skill_pool_dir,
            get_pool_skill_manifest_path,
            import_builtin_skills,
            reconcile_pool_manifest,
            _read_json_unlocked,
            _default_pool_manifest,
        )

        result: dict[str, Any] = {
            "seeded": False,
            "source": None,
            "skills": [],
        }

        # Skip if tenant already has skill pool state
        if self._has_skill_pool_state():
            return result

        default_pool_dir = get_skill_pool_dir(
            working_dir=self.base_working_dir / "default",
        )
        default_manifest_path = get_pool_skill_manifest_path(
            working_dir=self.base_working_dir / "default",
        )

        # Try to seed from default tenant if template exists
        if default_pool_dir.exists() and default_manifest_path.exists():
            try:
                default_manifest = _read_json_unlocked(
                    default_manifest_path,
                    _default_pool_manifest(),
                )
                default_skills = list(
                    default_manifest.get("skills", {}).keys(),
                )

                if default_skills:
                    # Copy skill directories
                    target_pool_dir = get_skill_pool_dir(
                        working_dir=self.tenant_dir,
                    )
                    copied = self._copy_skill_directories(
                        default_pool_dir,
                        target_pool_dir,
                    )

                    if copied:
                        # Reconcile to build proper manifest
                        reconcile_pool_manifest(working_dir=self.tenant_dir)
                        result["seeded"] = True
                        result["source"] = "default"
                        result["skills"] = copied
                        return result
            except (OSError, Exception):
                # Fall back to builtin initialization on any error
                pass

        # Fall back to builtin initialization
        import_builtin_skills(working_dir=self.tenant_dir)
        result["seeded"] = True
        result["source"] = "builtin"
        result["skills"] = list(
            _read_json_unlocked(
                get_pool_skill_manifest_path(working_dir=self.tenant_dir),
                _default_pool_manifest(),
            )
            .get("skills", {})
            .keys(),
        )
        return result

    def seed_default_workspace_skills_from_default(self) -> dict[str, Any]:
        """Seed default workspace skills from default tenant (idempotent).

        Copies skills from default tenant's default workspace when target
        workspace has no skill state yet. Preserves enabled, channels,
        config, and source fields from source manifest.

        Returns:
            Dict with result status:
            - "seeded": True if seeded, False otherwise
            - "skills": list of skill names copied (if any)
        """
        from ...agents.skills_manager import (
            get_workspace_skills_dir,
            get_workspace_skill_manifest_path,
            reconcile_workspace_manifest,
            _read_json_unlocked,
            _default_workspace_manifest,
        )

        result: dict[str, Any] = {"seeded": False, "skills": []}

        # Skip if default workspace already has skills
        if self._has_default_workspace_skills():
            return result

        default_workspace = (
            self.base_working_dir / "default" / "workspaces" / "default"
        )
        default_skills_dir = get_workspace_skills_dir(default_workspace)
        default_manifest_path = get_workspace_skill_manifest_path(
            default_workspace,
        )

        # Check if source has skills to copy
        if (
            not default_skills_dir.exists()
            or not default_manifest_path.exists()
        ):
            return result

        try:
            default_manifest = _read_json_unlocked(
                default_manifest_path,
                _default_workspace_manifest(),
            )
            default_skills = default_manifest.get("skills", {})

            if not default_skills:
                return result

            # Copy skill directories
            target_workspace = self.tenant_dir / "workspaces" / "default"
            target_skills_dir = get_workspace_skills_dir(target_workspace)
            copied = self._copy_skill_directories(
                default_skills_dir,
                target_skills_dir,
            )

            if not copied:
                return result

            # Reconcile to discover copied skills (side-effect: creates manifest)
            reconcile_workspace_manifest(target_workspace)

            # Preserve user-state fields from source manifest
            self._merge_workspace_manifest_state(
                target_workspace,
                default_skills,
            )

            result["seeded"] = True
            result["skills"] = copied
            return result

        except (OSError, Exception):
            return result

    def _merge_workspace_manifest_state(
        self,
        target_workspace: Path,
        source_skills: dict[str, Any],
    ) -> None:
        """Merge user-state fields from source manifest into target.

        Preserves enabled, channels, config, and source fields for skills
        that exist in both manifests.

        Args:
            target_workspace: Target workspace directory.
            source_skills: Source manifest skills dict with user-state.
        """
        from ...agents.skills_manager import (
            get_workspace_skill_manifest_path,
            _read_json_unlocked,
            _write_json_atomic,
            _default_workspace_manifest,
            _timestamp,
        )

        manifest_path = get_workspace_skill_manifest_path(target_workspace)
        target_manifest = _read_json_unlocked(
            manifest_path,
            _default_workspace_manifest(),
        )
        target_skills = target_manifest.get("skills", {})

        # Merge user-state fields for matching skills
        for skill_name in target_skills:
            if skill_name in source_skills:
                source_entry = source_skills[skill_name]
                target_entry = target_skills[skill_name]

                # Preserve user-state fields
                for field in ("enabled", "channels", "config", "source"):
                    if field in source_entry:
                        target_entry[field] = source_entry[field]

                target_entry["updated_at"] = _timestamp()

        target_manifest["skills"] = target_skills
        _write_json_atomic(manifest_path, target_manifest)

    def ensure_qa_agent(self) -> None:
        """Ensure the builtin QA agent workspace exists.

        This creates the QA agent declaration and seeds its skills
        from the tenant's skill pool.
        """
        from ..migration import ensure_qa_agent_exists

        ensure_qa_agent_exists(working_dir=self.tenant_dir)

    def ensure_skill_pool(self) -> None:
        """Ensure the tenant skill pool is initialized.

        This initializes the skill pool using the builtin skills.
        For full initialization with seeding from default tenant,
        use initialize_full() instead.
        """
        from ...agents.skills_manager import ensure_skill_pool_initialized

        ensure_skill_pool_initialized(working_dir=self.tenant_dir)

    def initialize_full(self) -> dict[str, Any]:
        """Run full tenant initialization with skill seeding.

        This performs the same steps as initialize_minimal(), plus:
        - Seeds skill pool from default tenant (or builtin fallback)
        - Seeds default workspace skills from default tenant
        - Creates QA agent workspace with skills

        Returns:
            Dict with initialization results:
            - "minimal": True if minimal initialization completed
            - "pool_seed": result from seed_skill_pool_from_default()
            - "workspace_seed": result from seed_default_workspace_skills_from_default()
            - "qa_agent": True if QA agent created
        """
        result: dict[str, Any] = {
            "minimal": False,
            "pool_seed": {},
            "workspace_seed": {},
            "qa_agent": False,
        }

        # Step 1: Minimal initialization
        self.initialize_minimal()
        result["minimal"] = True

        # Step 2: Seed skill pool from default (or builtin fallback)
        result["pool_seed"] = self.seed_skill_pool_from_default()

        # Step 3: Seed default workspace skills from default tenant
        result[
            "workspace_seed"
        ] = self.seed_default_workspace_skills_from_default()

        # Step 4: Create QA agent (kept for backward compatibility)
        self.ensure_qa_agent()
        result["qa_agent"] = True

        return result
