# -*- coding: utf-8 -*-
"""Tenant workspace pool: registry and cache for tenant-scoped workspaces.

Provides lazy creation, per-tenant locking, and lifecycle management
for tenant workspaces. Ensures thread-safe access and prevents duplicate
concurrent workspace creation.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Optional

from .workspace import Workspace

logger = logging.getLogger(__name__)


@dataclass
class TenantWorkspaceEntry:
    """Entry in the tenant workspace pool.

    Tracks workspace instance and metadata for a tenant.
    """

    tenant_id: str
    workspace: Workspace
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    last_accessed_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    access_count: int = 0


class TenantWorkspacePool:
    """Pool of tenant workspaces with lazy creation and lifecycle management.

    Each tenant gets their own workspace directory under the base working dir:
        WORKING_DIR/<tenant_id>/

    Features:
    - Lazy creation: Workspaces created on first access
    - Per-tenant locking: Prevents duplicate concurrent creation
    - Access tracking: Tracks last access time and count
    - Lifecycle management: stop_all for graceful shutdown
    """

    def __init__(self, base_working_dir: Path):
        """Initialize the tenant workspace pool.

        Args:
            base_working_dir: Base directory where tenant workspaces are created.
                Each tenant gets a subdirectory: base_working_dir / tenant_id
        """
        self._base_working_dir = Path(base_working_dir).expanduser().resolve()
        self._base_working_dir.mkdir(parents=True, exist_ok=True)

        # Tenant workspace registry: tenant_id -> TenantWorkspaceEntry
        self._workspaces: dict[str, TenantWorkspaceEntry] = {}

        # Per-tenant creation locks to prevent duplicate concurrent creation
        self._creation_locks: dict[str, Lock] = {}

        # Global lock for registry operations
        self._registry_lock = Lock()

        logger.info(
            f"TenantWorkspacePool initialized at {self._base_working_dir}",
        )

    def _get_tenant_workspace_dir(self, tenant_id: str) -> Path:
        """Get the workspace directory for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            Path to the tenant's workspace directory.
        """
        return self._base_working_dir / tenant_id

    def _get_or_create_creation_lock(self, tenant_id: str) -> Lock:
        """Get or create a creation lock for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            Lock for the tenant's creation.
        """
        with self._registry_lock:
            if tenant_id not in self._creation_locks:
                self._creation_locks[tenant_id] = Lock()
            return self._creation_locks[tenant_id]

    def get_or_create(
        self,
        tenant_id: str,
        agent_id: str = "default",
    ) -> Workspace:
        """Get existing workspace or create new one for tenant.

        Thread-safe: Uses per-tenant locking to prevent duplicate creation.
        If creation fails, the half-started workspace is not cached.

        Args:
            tenant_id: The tenant identifier.
            agent_id: The agent ID to use for the workspace (default: "default").

        Returns:
            Workspace instance for the tenant.

        Raises:
            RuntimeError: If workspace creation fails.
        """
        # Fast path: check if already exists
        with self._registry_lock:
            entry = self._workspaces.get(tenant_id)
            if entry is not None:
                self._mark_access(entry)
                return entry.workspace

        # Slow path: need to create (with per-tenant lock)
        creation_lock = self._get_or_create_creation_lock(tenant_id)
        with creation_lock:
            # Double-check after acquiring lock
            with self._registry_lock:
                entry = self._workspaces.get(tenant_id)
                if entry is not None:
                    self._mark_access(entry)
                    return entry.workspace

            # Create workspace (outside registry lock to avoid blocking)
            workspace_dir = self._get_tenant_workspace_dir(tenant_id)
            logger.info(
                f"Creating workspace for tenant: {tenant_id} at {workspace_dir}",
            )

            try:
                workspace = Workspace(agent_id, str(workspace_dir))

                # Register in pool
                with self._registry_lock:
                    entry = TenantWorkspaceEntry(
                        tenant_id=tenant_id,
                        workspace=workspace,
                    )
                    self._workspaces[tenant_id] = entry

                logger.info(f"Workspace created for tenant: {tenant_id}")
                return workspace

            except Exception as e:
                logger.error(
                    f"Failed to create workspace for tenant {tenant_id}: {e}",
                )
                # Failed initialization does not leave cached half-started workspace
                raise RuntimeError(
                    f"Failed to create workspace for tenant {tenant_id}: {e}",
                ) from e

    def get(self, tenant_id: str) -> Optional[Workspace]:
        """Get existing workspace for tenant if it exists.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            Workspace instance if found, None otherwise.
        """
        with self._registry_lock:
            entry = self._workspaces.get(tenant_id)
            if entry is not None:
                self._mark_access(entry)
                return entry.workspace
            return None

    def remove(self, tenant_id: str) -> Optional[Workspace]:
        """Remove workspace from pool without stopping it.

        The caller is responsible for stopping the workspace if needed.
        Use stop() for graceful shutdown and removal.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The removed workspace if it existed, None otherwise.
        """
        with self._registry_lock:
            entry = self._workspaces.pop(tenant_id, None)
            if entry is not None:
                logger.info(f"Removed workspace from pool: {tenant_id}")
                return entry.workspace
            return None

    async def stop(self, tenant_id: str, final: bool = True) -> bool:
        """Stop and remove workspace for a tenant.

        Args:
            tenant_id: The tenant identifier.
            final: If True, stop all services including reusable ones.

        Returns:
            True if workspace was found and stopped, False otherwise.
        """
        workspace = self.remove(tenant_id)
        if workspace is None:
            return False

        try:
            await workspace.stop(final=final)
            logger.info(f"Stopped workspace for tenant: {tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Error stopping workspace for tenant {tenant_id}: {e}")
            raise

    def mark_access(self, tenant_id: str) -> bool:
        """Mark access time for a tenant's workspace.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            True if workspace exists and was marked, False otherwise.
        """
        with self._registry_lock:
            entry = self._workspaces.get(tenant_id)
            if entry is not None:
                self._mark_access(entry)
                return True
            return False

    def _mark_access(self, entry: TenantWorkspaceEntry) -> None:
        """Update access time and count for an entry (registry lock held).

        Args:
            entry: The tenant workspace entry to mark.
        """
        entry.last_accessed_at = asyncio.get_event_loop().time()
        entry.access_count += 1

    async def stop_all(self, final: bool = True) -> None:
        """Stop all workspaces in the pool.

        Args:
            final: If True, stop all services including reusable ones.
        """
        with self._registry_lock:
            entries = list(self._workspaces.values())
            self._workspaces.clear()

        if not entries:
            logger.debug("No workspaces to stop")
            return

        logger.info(f"Stopping {len(entries)} tenant workspaces")

        # Stop all workspaces concurrently
        exceptions = []
        for entry in entries:
            try:
                await entry.workspace.stop(final=final)
                logger.debug(f"Stopped workspace: {entry.tenant_id}")
            except Exception as e:
                logger.error(f"Error stopping workspace {entry.tenant_id}: {e}")
                exceptions.append((entry.tenant_id, e))

        if exceptions:
            tenant_ids = [tid for tid, _ in exceptions]
            raise RuntimeError(
                f"Failed to stop workspaces for tenants: {', '.join(tenant_ids)}",
            )

        logger.info("All tenant workspaces stopped")

    def get_stats(self) -> dict:
        """Get statistics about the pool.

        Returns:
            Dictionary with pool statistics.
        """
        with self._registry_lock:
            return {
                "tenant_count": len(self._workspaces),
                "tenants": {
                    tenant_id: {
                        "created_at": entry.created_at,
                        "last_accessed_at": entry.last_accessed_at,
                        "access_count": entry.access_count,
                    }
                    for tenant_id, entry in self._workspaces.items()
                },
            }

    def __contains__(self, tenant_id: str) -> bool:
        """Check if a tenant has a workspace in the pool.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            True if the tenant has a workspace, False otherwise.
        """
        with self._registry_lock:
            return tenant_id in self._workspaces

    def __len__(self) -> int:
        """Return the number of workspaces in the pool.

        Returns:
            Number of tenant workspaces.
        """
        with self._registry_lock:
            return len(self._workspaces)

    def __repr__(self) -> str:
        """String representation of the pool."""
        with self._registry_lock:
            count = len(self._workspaces)
            tenants = list(self._workspaces.keys())
        return (
            f"TenantWorkspacePool("
            f"base={self._base_working_dir}, "
            f"tenants={count}, "
            f"ids={tenants}"
            f")"
        )


__all__ = [
    "TenantWorkspacePool",
    "TenantWorkspaceEntry",
]
