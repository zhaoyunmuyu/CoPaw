# -*- coding: utf-8 -*-
"""Tenant directory bootstrapper.

Creates the directory structure and seeds default agents for a single tenant.
Used by both ``swe init --tenant-id`` (CLI) and ``TenantWorkspacePool`` (runtime)
so the bootstrap logic lives in one place.
"""
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from ..migration import (
    ensure_default_agent_exists,
)

logger = logging.getLogger(__name__)


class TenantInitializer:
    """Bootstrap a tenant directory with required structure and agents."""

    _WORKSPACE_TEMPLATE_FILES = (
        "AGENTS.md",
        "BOOTSTRAP.md",
        "HEARTBEAT.md",
        "MEMORY.md",
        "PROFILE.md",
        "SOUL.md",
    )
    _WORKSPACE_REQUIRED_FILES = tuple(
        filename
        for filename in _WORKSPACE_TEMPLATE_FILES
        if filename != "BOOTSTRAP.md"
    )

    def __init__(
        self,
        base_working_dir: Path,
        tenant_id: str,
        source_id: str | None = None,
    ):
        """Initialize tenant bootstrapper.

        Args:
            base_working_dir: Base working directory (~/.swe).
            tenant_id: The tenant identifier.
            source_id: Optional source identifier from X-Source-Id header.
                Used to select the appropriate default_{source} template.
                When tenant_id is "default" and source_id is set, the
                effective working directory becomes default_{source_id}.
        """
        from ...config.context import resolve_effective_tenant_id

        self.base_working_dir = Path(base_working_dir).expanduser().resolve()
        self.tenant_id = tenant_id
        self.source_id = source_id
        self.template_name = self._resolve_template_name()
        self.effective_tenant_id = resolve_effective_tenant_id(
            tenant_id,
            source_id,
        )
        self.tenant_dir = self.base_working_dir / self.effective_tenant_id

    def _resolve_template_name(self) -> str:
        """Determine which default_xxx template directory to use.

        If source_id is provided and default_{source_id} doesn't exist,
        automatically creates it from the default template.

        Default tenant without source_id uses "default" directory directly.
        Non-default tenants without source_id use the "default" template for initialization.

        Returns:
            Template directory name (e.g., "default_ruice" or "default").
        """
        if not self.source_id:
            # No source_id: use default template/directory
            return "default"
        template_name = f"default_{self.source_id}"
        template_dir = self.base_working_dir / template_name
        if template_dir.exists():
            logger.info(
                f"Using template {template_name} for tenant {self.tenant_id} "
                f"(source_id={self.source_id})",
            )
            return template_name

        # Dynamic template creation: copy from default if not exists
        default_dir = self.base_working_dir / "default"
        if default_dir.exists():
            logger.info(
                f"Template dir {template_name} not found, "
                f"creating from default for source_id={self.source_id}",
            )
            try:
                self._create_source_template_from_default(template_dir)
                logger.info(
                    f"Created template {template_name} from default, "
                    f"using for tenant {self.tenant_id}",
                )
                return template_name
            except Exception as e:
                logger.warning(
                    f"Failed to create template {template_name}: {e}, "
                    f"falling back to default",
                )
                return "default"

        logger.info(
            f"Template dir {template_name} not found and no default template, "
            f"falling back to default for tenant {self.tenant_id}",
        )
        return "default"

    def _create_source_template_from_default(self, target_dir: Path) -> None:
        """Create a source-specific template directory from default.

        Also fixes workspace paths in config.json to reference the new
        template directory instead of the original default directory.

        Args:
            target_dir: Path to the new template directory (e.g., default_ruice).
        """
        default_dir = self.base_working_dir / "default"
        if not default_dir.exists():
            return

        if target_dir.exists():
            return

        try:
            shutil.copytree(default_dir, target_dir)
            self._fix_template_config_paths(target_dir)
            logger.info(
                f"Created source template directory: {target_dir}",
            )
        except OSError:
            if not target_dir.exists():
                raise
            logger.debug(
                f"Template {target_dir} created by concurrent request",
            )

    def _fix_template_config_paths(self, template_dir: Path) -> None:
        """Fix workspace paths in template config.json after copying from default.

        Updates workspace_dir paths from default/... to template_dir/...

        Args:
            template_dir: The newly created template directory.
        """
        config_path = template_dir / "config.json"
        if not config_path.exists():
            return

        try:
            source_content = config_path.read_text(encoding="utf-8")
            config = json.loads(source_content)

            old_prefix = str(self.base_working_dir / "default" / "workspaces")
            new_prefix = str(template_dir / "workspaces")

            if "agents" in config and "profiles" in config["agents"]:
                for profile in config["agents"]["profiles"].values():
                    if "workspace_dir" in profile:
                        old_path = profile["workspace_dir"]
                        if old_path.startswith(old_prefix):
                            profile["workspace_dir"] = old_path.replace(
                                old_prefix,
                                new_prefix,
                            )

            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to fix template config paths: {e}")

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

    def has_seeded_bootstrap(self) -> bool:
        """Return True when the tenant bootstrap scaffold is present."""
        default_workspace = self.tenant_dir / "workspaces" / "default"
        required_paths = [
            self.tenant_dir / "config.json",
            default_workspace,
            default_workspace / "agent.json",
            default_workspace / "chats.json",
            default_workspace / "jobs.json",
            default_workspace / "token_usage.json",
            default_workspace / "sessions",
            default_workspace / "memory",
        ]
        required_paths.extend(
            default_workspace / filename
            for filename in self._WORKSPACE_REQUIRED_FILES
        )

        return (
            all(path.exists() for path in required_paths)
            and self._has_skill_pool_state()
        )

    def initialize_minimal(self) -> None:
        """Run minimal bootstrap sequence (idempotent).

        This is called on first tenant access and only ensures:
        - Directory structure exists
        - Default agent declaration exists

        No runtime components are started.
        """
        self.ensure_directory_structure()
        self.ensure_default_agent()

    def ensure_seeded_bootstrap(self) -> dict[str, Any]:
        """Run seeded bootstrap sequence (idempotent, runtime-safe).

        This is called on first tenant access and ensures:
        - Directory structure exists
        - Default agent declaration exists
        - Skill pool is seeded from default tenant (or builtin fallback)
        - Default workspace skills are seeded from default tenant

        Does NOT create the QA agent or start workspace runtime.

        Raises:
            RuntimeError: If skill pool seeding fails (including builtin fallback).

        Returns:
            Dict with bootstrap results:
            - "minimal": True if minimal init completed
            - "pool_seed": result from seed_skill_pool_from_default()
            - "workspace_seed": result from seed_default_workspace_skills_from_default()
        """
        result: dict[str, Any] = {
            "minimal": False,
            "config_seed": {},
            "providers_seed": {},
            "pool_seed": {},
            "workspace_seed": {},
            "workspace_scaffold": {},
        }
        is_default_tenant = self.tenant_id == "default"
        config_existed = (self.tenant_dir / "config.json").exists()

        # Step 1: Minimal initialization
        self.initialize_minimal()
        result["minimal"] = True

        # Step 1.5: Seed tenant root config from default template
        # For default tenant: only seed if config doesn't exist
        # For non-default tenant: skip (config already copied from md_files)
        if is_default_tenant:
            result["config_seed"] = self.seed_tenant_config_from_default(
                overwrite=not config_existed,
            )

        # Step 1.6: Seed providers directory from default tenant
        result["providers_seed"] = self.seed_providers_from_default(
            overwrite=False,
        )

        # Step 2: Seed skill pool from default (or builtin fallback)
        # Note: This raises RuntimeError on complete failure (including builtin fallback)
        result["pool_seed"] = self.seed_skill_pool_from_default()

        # Step 3: Seed default workspace skills from default tenant
        # Note: This raises RuntimeError on failure
        result[
            "workspace_seed"
        ] = self.seed_default_workspace_skills_from_default()

        # Step 4: Ensure the default workspace scaffold is complete.
        result["workspace_scaffold"] = self.ensure_default_workspace_scaffold()

        return result

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

        Uses manifest as primary source of truth. Only falls back to
        directory checking if manifest exists but is empty/corrupt.

        Returns:
            True if skill pool manifest exists with skills, False otherwise.
        """
        from ...agents.skills_manager import (
            get_skill_pool_dir,
            get_pool_skill_manifest_path,
        )

        pool_dir = get_skill_pool_dir(working_dir=self.tenant_dir)
        manifest_path = get_pool_skill_manifest_path(
            working_dir=self.tenant_dir,
        )

        # Primary check: manifest exists and has skills
        # If manifest doesn't exist, we need seeding (even if directories exist)
        if manifest_path.exists():
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"),
                )
                if manifest.get("skills"):
                    return True
                # Manifest exists but is empty - check if skills were partially copied
                # This handles the case where manifest was deleted but skills remain
            except (json.JSONDecodeError, OSError):
                pass

            # Manifest exists (even if empty/corrupt), check for partial state
            if pool_dir.exists():
                for item in pool_dir.iterdir():
                    if item.is_dir() and (item / "SKILL.md").exists():
                        return True
        else:
            # No manifest - need seeding regardless of directory state
            # This prevents partial copy from being considered "initialized"
            pass

        return False

    def _has_default_workspace_skills(self) -> bool:
        """Check if default workspace already has skill state.

        Uses manifest as primary source of truth. Only falls back to
        directory checking if manifest exists but is empty/corrupt.

        Returns:
            True if default workspace has skill manifest with skills, False otherwise.
        """
        from ...agents.skills_manager import (
            get_workspace_skills_dir,
            get_workspace_skill_manifest_path,
        )

        default_workspace = self.tenant_dir / "workspaces" / "default"
        skills_dir = get_workspace_skills_dir(default_workspace)
        manifest_path = get_workspace_skill_manifest_path(default_workspace)

        # Primary check: manifest exists and has skills
        # If manifest doesn't exist, we need seeding (even if directories exist)
        if manifest_path.exists():
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"),
                )
                if manifest.get("skills"):
                    return True
                # Manifest exists but is empty - check if skills were partially copied
            except (json.JSONDecodeError, OSError):
                pass

            # Manifest exists (even if empty/corrupt), check for partial state
            if skills_dir.exists():
                for item in skills_dir.iterdir():
                    if item.is_dir() and (item / "SKILL.md").exists():
                        return True
        else:
            # No manifest - need seeding regardless of directory state
            pass

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

    def _list_skill_directories(self, skills_dir: Path) -> list[str]:
        """List skill directory names in a given directory.

        Args:
            skills_dir: Directory containing skill subdirectories.

        Returns:
            List of skill directory names that contain SKILL.md.
        """
        if not skills_dir.exists():
            return []
        return [
            item.name
            for item in skills_dir.iterdir()
            if item.is_dir() and (item / "SKILL.md").exists()
        ]

    def seed_tenant_config_from_default(
        self,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Seed tenant config.json from default tenant.

        Copies the config file directly and updates workspace paths
        to point to the new tenant's directories.
        """

        target_config_path = self.tenant_dir / "config.json"
        source_config_path = (
            self.base_working_dir / self.template_name / "config.json"
        )
        result: dict[str, Any] = {"seeded": False, "source": None}

        if not source_config_path.exists():
            return result
        if target_config_path.exists() and not overwrite:
            return result

        try:
            # Read source config as raw JSON to preserve exact content
            source_content = source_config_path.read_text(encoding="utf-8")
            source_config = json.loads(source_content)

            # Update workspace_dir paths to point to new tenant
            template_workspace_prefix = str(
                self.base_working_dir / self.template_name / "workspaces",
            )
            tenant_workspace_prefix = str(self.tenant_dir / "workspaces")

            # Update profiles workspace_dir
            if (
                "agents" in source_config
                and "profiles" in source_config["agents"]
            ):
                for profile in source_config["agents"]["profiles"].values():
                    if "workspace_dir" in profile:
                        old_path = profile["workspace_dir"]
                        # Replace template tenant path with new tenant path
                        if old_path.startswith(template_workspace_prefix):
                            profile["workspace_dir"] = old_path.replace(
                                template_workspace_prefix,
                                tenant_workspace_prefix,
                            )

            # Write the modified config
            target_config_path.parent.mkdir(parents=True, exist_ok=True)
            target_config_path.write_text(
                json.dumps(source_config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["seeded"] = True
            result["source"] = self.template_name
        except Exception as e:
            logger.warning(
                f"Failed to seed config from {self.template_name} for tenant "
                f"{self.tenant_id}: {e}",
            )

        return result

    def seed_providers_from_default(
        self,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Seed tenant providers directory from default tenant.

        Copies the entire providers directory structure from the default tenant,
        including builtin/, custom/, and active_model.json.

        If the source-specific template providers directory doesn't exist,
        automatically creates it from the default providers directory.

        Args:
            overwrite: If True, overwrite existing providers directory.

        Returns:
            Dict with result status:
            - "seeded": True if seeded, False otherwise
            - "source": template name or None
        """
        from ...constant import SECRET_DIR

        target_providers_dir = (
            SECRET_DIR / self.effective_tenant_id / "providers"
        )
        source_providers_dir = SECRET_DIR / self.template_name / "providers"
        result: dict[str, Any] = {"seeded": False, "source": None}

        # Special case: when template_name == effective_tenant_id (default user via source),
        # the template IS the target - no copying needed, just ensure it exists
        if self.template_name == self.effective_tenant_id:
            if not source_providers_dir.exists():
                self._ensure_source_template_providers(
                    SECRET_DIR,
                    self.template_name,
                )
            if source_providers_dir.exists():
                result["seeded"] = True
                result["source"] = self.template_name
            return result

        # Dynamic creation: if source-specific providers template doesn't exist,
        # create it from default
        if (
            not source_providers_dir.exists()
            or not any(source_providers_dir.iterdir())
        ) and self.template_name != "default":
            self._ensure_source_template_providers(
                SECRET_DIR,
                self.template_name,
            )

        # Re-check after potential creation
        if not source_providers_dir.exists():
            return result
        if not any(source_providers_dir.iterdir()):
            return result

        # Check if target already exists
        if target_providers_dir.exists() and not overwrite:
            return result

        try:
            # Remove existing target if overwrite is True
            if target_providers_dir.exists():
                shutil.rmtree(target_providers_dir)

            # Copy entire providers directory
            shutil.copytree(source_providers_dir, target_providers_dir)
            result["seeded"] = True
            result["source"] = self.template_name
            logger.info(
                f"Seeded providers directory from {self.template_name} "
                f"for tenant {self.effective_tenant_id}",
            )
        except Exception as e:
            logger.warning(
                f"Failed to seed providers from {self.template_name} "
                f"for tenant {self.effective_tenant_id}: {e}",
            )

        return result

    def _ensure_source_template_providers(
        self,
        secret_dir: Path,
        template_name: str,
    ) -> None:
        """Ensure source-specific providers template exists, creating from default if needed.

        Args:
            secret_dir: Base secret directory (e.g., ~/.swe.secret).
            template_name: Template directory name (e.g., "default_ruice").
        """
        default_providers = secret_dir / "default" / "providers"
        target_providers = secret_dir / template_name / "providers"

        if not default_providers.exists():
            return

        target_parent = target_providers.parent
        try:
            # Use exist_ok for concurrency safety
            if not target_parent.exists():
                shutil.copytree(
                    secret_dir / "default",
                    target_parent,
                )
                logger.info(
                    f"Created source template providers: {target_parent}",
                )
            elif not target_providers.exists():
                shutil.copytree(default_providers, target_providers)
                logger.info(
                    f"Created source template providers: {target_providers}",
                )
        except OSError:
            if not target_providers.exists():
                raise
            logger.debug(
                f"Source template providers {target_providers} "
                f"created by concurrent request",
            )

    def ensure_default_workspace_scaffold(self) -> dict[str, Any]:
        """Ensure runtime-required workspace files exist for default agent."""
        from ...agents.utils.setup_utils import copy_md_files
        from ...config.config import AgentProfileConfig, load_agent_config

        default_workspace = self.tenant_dir / "workspaces" / "default"
        default_workspace.mkdir(parents=True, exist_ok=True)

        for dirname in ("sessions", "memory", "skills"):
            (default_workspace / dirname).mkdir(parents=True, exist_ok=True)

        tenant_config_path = self.tenant_dir / "config.json"
        target_agent_config_path = default_workspace / "agent.json"
        template_workspace = (
            self.base_working_dir
            / self.template_name
            / "workspaces"
            / "default"
        )
        source_agent_config_path = template_workspace / "agent.json"
        if (
            not target_agent_config_path.exists()
            and source_agent_config_path.exists()
        ):
            agent_payload = json.loads(
                source_agent_config_path.read_text(encoding="utf-8"),
            )
            agent_payload["workspace_dir"] = str(default_workspace)
            agent_config_model = AgentProfileConfig(**agent_payload)
            target_agent_config_path.write_text(
                json.dumps(
                    agent_config_model.model_dump(exclude_none=True),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        agent_config = load_agent_config(
            "default",
            config_path=tenant_config_path,
        )

        copied_files: list[str] = []
        for filename in self._WORKSPACE_TEMPLATE_FILES:
            source_file = template_workspace / filename
            target_file = default_workspace / filename
            if target_file.exists():
                continue
            if source_file.exists():
                shutil.copy2(source_file, target_file)
                copied_files.append(filename)

        copied_files.extend(
            copy_md_files(
                agent_config.language or "zh",
                skip_existing=True,
                workspace_dir=default_workspace,
            ),
        )

        token_usage_path = default_workspace / "token_usage.json"
        if not token_usage_path.exists():
            token_usage_path.write_text("{}", encoding="utf-8")

        return {
            "agent_json": (default_workspace / "agent.json").exists(),
            "copied_files": sorted(set(copied_files)),
            "token_usage": token_usage_path.exists(),
        }

    def _prepare_source_pool_state(
        self,
        default_pool_dir: Path,
        default_manifest_path: Path,
    ) -> tuple[list[str], dict[str, Any]]:
        """Prepare source pool state for seeding.

        Reconciles source from disk and extracts config preservation data.

        Returns:
            Tuple of (source_skill_names, source_skills_with_config).
        """
        from ...agents.skills_manager import (
            reconcile_pool_manifest,
            _read_json_unlocked,
            _default_pool_manifest,
        )

        source_skills_with_config: dict[str, Any] = {}

        # Read source manifest for durable state (config) before reconcile
        if default_manifest_path.exists():
            try:
                source_manifest = _read_json_unlocked(
                    default_manifest_path,
                    _default_pool_manifest(),
                )
                # Capture config for each skill to preserve after copy
                for skill_name, skill_entry in source_manifest.get(
                    "skills",
                    {},
                ).items():
                    if "config" in skill_entry:
                        source_skills_with_config[skill_name] = skill_entry[
                            "config"
                        ]
            except Exception as e:
                logger.warning(f"Failed to read source manifest: {e}")

        # Reconcile source to discover skills from disk
        try:
            reconcile_pool_manifest(working_dir=default_pool_dir.parent.parent)
        except Exception as e:
            logger.warning(f"Failed to reconcile source pool: {e}")

        # Collect source skill names from disk
        source_skill_names: list[str] = []
        if default_pool_dir.exists():
            for item in default_pool_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    source_skill_names.append(item.name)

        return source_skill_names, source_skills_with_config

    def seed_skill_pool_from_default(self) -> dict[str, Any]:
        """Seed skill pool from default tenant (idempotent).

        Copies skill_pool content from default tenant when target tenant
        has no skill pool state yet. Falls back to builtin initialization
        when no template exists.

        Uses filesystem skill directories as source of truth, reconciling
        source from disk before checking template availability.

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

        template_working_dir = self.base_working_dir / self.template_name
        template_pool_dir = get_skill_pool_dir(
            working_dir=template_working_dir,
        )
        template_manifest_path = get_pool_skill_manifest_path(
            working_dir=template_working_dir,
        )

        # Prepare source state (reconcile + collect config)
        (
            source_skill_names,
            source_skills_with_config,
        ) = self._prepare_source_pool_state(
            template_pool_dir,
            template_manifest_path,
        )

        # Try to seed from template if template exists
        if source_skill_names:
            try:
                target_pool_dir = get_skill_pool_dir(
                    working_dir=self.tenant_dir,
                )
                copied = self._copy_skill_directories(
                    template_pool_dir,
                    target_pool_dir,
                )

                if copied:
                    # Reconcile target to build proper manifest
                    reconcile_pool_manifest(working_dir=self.tenant_dir)

                    # Preserve durable config from source manifest
                    self._merge_pool_manifest_config(source_skills_with_config)

                    result["seeded"] = True
                    result["source"] = self.template_name
                    result["skills"] = copied
                    return result
            except Exception as e:
                logger.warning(
                    f"Failed to seed pool from {self.template_name} for tenant "
                    f"{self.tenant_id}: {e}. "
                    "Falling back to builtin initialization.",
                )

        # Fall back to builtin initialization
        # First, check if target already has skill directories (partial copy scenario)
        # and reconcile them to preserve existing skills
        target_pool_dir = get_skill_pool_dir(working_dir=self.tenant_dir)
        if target_pool_dir.exists():
            existing_skills = [
                item.name
                for item in target_pool_dir.iterdir()
                if item.is_dir() and (item / "SKILL.md").exists()
            ]
            if existing_skills:
                logger.info(
                    f"Found {len(existing_skills)} existing skills in pool for tenant "
                    f"{self.tenant_id}, reconciling before builtin fallback: "
                    f"{existing_skills}",
                )
                try:
                    reconcile_pool_manifest(working_dir=self.tenant_dir)
                    # If reconcile succeeds, consider seeding successful with existing skills
                    result["seeded"] = True
                    result["source"] = "existing"
                    result["skills"] = existing_skills
                    return result
                except Exception as reconcile_error:
                    logger.warning(
                        f"Failed to reconcile existing pool skills for tenant "
                        f"{self.tenant_id}: {reconcile_error}. "
                        f"Continuing with builtin fallback.",
                    )

        try:
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
        except Exception as e:
            logger.error(
                f"Failed to initialize builtin skills for tenant {self.tenant_id}: {e}",
            )
            raise RuntimeError(
                f"Skill pool initialization failed for tenant {self.tenant_id}: "
                f"both default tenant seeding and builtin fallback failed: {e}",
            ) from e

        return result

    def _merge_pool_manifest_config(
        self,
        source_skills_config: dict[str, Any],
    ) -> None:
        """Merge durable config from source manifest into target pool manifest.

        Args:
            source_skills_config: Dict mapping skill name to config value.
        """
        from ...agents.skills_manager import (
            get_pool_skill_manifest_path,
            _read_json_unlocked,
            _write_json_atomic,
            _default_pool_manifest,
        )

        if not source_skills_config:
            return

        try:
            manifest_path = get_pool_skill_manifest_path(
                working_dir=self.tenant_dir,
            )
            manifest = _read_json_unlocked(
                manifest_path,
                _default_pool_manifest(),
            )
            skills = manifest.get("skills", {})

            # Merge config for matching skills
            for skill_name, config in source_skills_config.items():
                if skill_name in skills:
                    skills[skill_name]["config"] = config

            _write_json_atomic(manifest_path, manifest)
        except Exception as e:
            logger.warning(
                f"Failed to merge pool config for tenant {self.tenant_id}: {e}",
            )

    def _reconcile_existing_workspace_skills(
        self,
        target_workspace: Path,
        existing_skills: list[str],
    ) -> dict[str, Any]:
        """Reconcile existing workspace skills and return result.

        Args:
            target_workspace: Target workspace directory.
            existing_skills: List of existing skill names.

        Returns:
            Result dict with seeded=True and skills list.
        """
        from ...agents.skills_manager import reconcile_workspace_manifest

        logger.info(
            f"Found {len(existing_skills)} existing workspace skills for "
            f"tenant {self.tenant_id}, reconciling: {existing_skills}",
        )
        try:
            reconcile_workspace_manifest(target_workspace)
            return {"seeded": True, "skills": existing_skills}
        except Exception as e:
            logger.warning(
                f"Failed to reconcile existing workspace skills for "
                f"tenant {self.tenant_id}: {e}",
            )
            return {"seeded": False, "skills": []}

    def _prepare_source_workspace_state(
        self,
        default_workspace: Path,
    ) -> dict[str, Any]:
        """Prepare source workspace state for seeding.

        Reconciles source workspace and captures durable skill state.

        Args:
            default_workspace: Default tenant's workspace directory.

        Returns:
            Dict with skill states (enabled, channels, config, source).
        """
        from ...agents.skills_manager import (
            get_workspace_skills_dir,
            get_workspace_skill_manifest_path,
            reconcile_workspace_manifest,
            _read_json_unlocked,
            _default_workspace_manifest,
        )

        source_skills_state: dict[str, Any] = {}
        default_skills_dir = get_workspace_skills_dir(default_workspace)
        default_manifest_path = get_workspace_skill_manifest_path(
            default_workspace,
        )

        if not default_skills_dir.exists():
            return source_skills_state

        try:
            if default_manifest_path.exists():
                source_manifest = _read_json_unlocked(
                    default_manifest_path,
                    _default_workspace_manifest(),
                )
                for skill_name, skill_entry in source_manifest.get(
                    "skills",
                    {},
                ).items():
                    source_skills_state[skill_name] = {
                        field: skill_entry[field]
                        for field in (
                            "enabled",
                            "channels",
                            "config",
                            "source",
                        )
                        if field in skill_entry
                    }
            reconcile_workspace_manifest(default_workspace)
        except Exception as e:
            logger.warning(
                f"Failed to reconcile source workspace for tenant {self.tenant_id}: {e}",
            )
        return source_skills_state

    def seed_default_workspace_skills_from_default(self) -> dict[str, Any]:
        """Seed default workspace skills from default tenant (idempotent).

        Copies skills from default tenant's default workspace when target
        workspace has no skill state yet. Preserves enabled, channels,
        config, and source fields from source manifest.

        Uses filesystem skill directories as source of truth, reconciling
        source from disk before checking template availability.

        Returns:
            Dict with result status:
            - "seeded": True if seeded, False otherwise
            - "skills": list of skill names copied (if any)
        """
        from ...agents.skills_manager import (
            get_workspace_skills_dir,
            reconcile_workspace_manifest,
        )

        result: dict[str, Any] = {"seeded": False, "skills": []}

        # Skip if default workspace already has skills
        if self._has_default_workspace_skills():
            return result

        template_workspace = (
            self.base_working_dir
            / self.template_name
            / "workspaces"
            / "default"
        )
        template_skills_dir = get_workspace_skills_dir(template_workspace)

        # Prepare source state and reconcile
        source_skills_state = self._prepare_source_workspace_state(
            template_workspace,
        )

        # Check if source has usable skills after reconciliation
        source_skill_names = self._list_skill_directories(template_skills_dir)

        if not source_skill_names:
            # Source has no skills, check if target has existing skills
            target_workspace = self.tenant_dir / "workspaces" / "default"
            target_skills_dir = get_workspace_skills_dir(target_workspace)
            existing_skills = self._list_skill_directories(target_skills_dir)
            if existing_skills:
                return self._reconcile_existing_workspace_skills(
                    target_workspace,
                    existing_skills,
                )
            return result

        try:
            # Copy skill directories
            target_workspace = self.tenant_dir / "workspaces" / "default"
            target_skills_dir = get_workspace_skills_dir(target_workspace)
            copied = self._copy_skill_directories(
                template_skills_dir,
                target_skills_dir,
            )

            if not copied:
                return result

            # Reconcile target to build proper manifest
            reconcile_workspace_manifest(target_workspace)

            # Preserve durable state from source manifest
            if source_skills_state:
                self._merge_workspace_manifest_state(
                    target_workspace,
                    source_skills_state,
                )

            result["seeded"] = True
            result["skills"] = copied
            return result

        except Exception as e:
            logger.error(
                f"Failed to seed workspace skills for tenant {self.tenant_id}: {e}",
            )
            raise RuntimeError(
                f"Default workspace skill seeding failed for tenant {self.tenant_id}: {e}",
            ) from e

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

        This reuses ensure_seeded_bootstrap() for the runtime-safe seeding,
        plus creates the QA agent workspace (full-init only).

        Returns:
            Dict with initialization results:
            - "minimal": True if minimal initialization completed
            - "pool_seed": result from seed_skill_pool_from_default()
            - "workspace_seed": result from seed_default_workspace_skills_from_default()
            - "qa_agent": True if QA agent created
        """
        # Reuse the runtime-safe seeded bootstrap (no QA agent)
        result = self.ensure_seeded_bootstrap()

        # Full initialization also creates the QA agent
        try:
            self.ensure_qa_agent()
            result["qa_agent"] = True
        except Exception as e:
            logger.warning(
                f"Failed to create QA agent for tenant {self.tenant_id}: {e}",
            )
            result["qa_agent"] = False

        return result
