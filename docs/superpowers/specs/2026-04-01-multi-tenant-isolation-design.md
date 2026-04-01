# Multi-Tenant Isolation Design Specification

**Date:** 2026-04-01
**Status:** Draft
**Scope:** User isolation and permission control for CoPaw multi-tenant deployment

---

## 1. Overview

This document specifies the complete design for implementing multi-tenant isolation in CoPaw, enabling multiple independent users/organizations to share a single CoPaw instance while maintaining complete data and runtime isolation.

### 1.1 Key Requirements

- **Tenant Identification:** Via `X-Tenant-Id` HTTP header
- **Complete Data Isolation:** Each tenant has independent working directory
- **Runtime Isolation:** Each tenant runs in separate Workspace instance
- **Resource Management:** Configurable limits per tenant (concurrency, storage)
- **Security:** Tenant access control and cross-tenant leakage prevention

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│  Middleware Layer                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. TenantSecurityMiddleware                          │   │
│  │    - Validate X-Tenant-Id format                     │   │
│  │    - Check tenant allowlist/blocklist                │   │
│  │    - Set contextvars.current_tenant_id               │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. TenantContextMiddleware                           │   │
│  │    - Set contextvars.current_user_id                 │   │
│  │    - Initialize/request tenant workspace             │   │
│  │    - Rate limiting per tenant                        │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Router Layer                                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │   Console   │ │    Cron     │ │      Settings       │   │
│  │   Router    │ │    Router   │ │      Router         │   │
│  └──────┬──────┘ └──────┬──────┘ └──────────┬──────────┘   │
│         │               │                   │              │
│         └───────────────┼───────────────────┘              │
│                         │                                   │
├─────────────────────────┼───────────────────────────────────┤
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              TenantWorkspacePool                     │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  tenant-1: Workspace (agent_id, runtime)    │   │   │
│  │  │  tenant-2: Workspace (agent_id, runtime)    │   │   │
│  │  │  tenant-3: Workspace (agent_id, runtime)    │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  │  - Lazy loading / eviction                         │   │
│  │  - Resource limits enforcement                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Request → Security Check → Context Setup → Get Workspace → Process → Response
                ↓                ↓              ↓
           Validate ID    Set context    Lazy init if
           Check ACL      tenant/user    not exists
```

---

## 3. Core Components

### 3.1 Context Variables

**File:** `src/copaw/config/context.py`

```python
from contextvars import ContextVar
from typing import Optional

# Existing (keep)
current_workspace_dir: ContextVar[Path | None] = ContextVar(...)
current_recent_max_bytes: ContextVar[int | None] = ContextVar(...)

# NEW: Tenant identification
current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id",
    default=None,
)

# NEW: User identification within tenant
current_user_id: ContextVar[str | None] = ContextVar(
    "current_user_id",
    default=None,
)

# NEW: Tenant workspace reference (for quick access)
current_tenant_workspace: ContextVar["Workspace" | None] = ContextVar(
    "current_tenant_workspace",
    default=None,
)


# Access functions
def get_current_tenant_id() -> str:
    """Get current tenant ID or 'default'."""
    return current_tenant_id.get() or "default"


def get_current_user_id() -> str:
    """Get current user ID or 'anonymous'."""
    return current_user_id.get() or "anonymous"


def get_current_tenant_workspace() -> Optional["Workspace"]:
    """Get current tenant's workspace instance."""
    return current_tenant_workspace.get()
```

### 3.2 Tenant Workspace Pool

**File:** `src/copaw/app/workspace/tenant_pool.py`

```python
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Set

from .workspace import Workspace
from ...config.context import (
    current_tenant_workspace,
    current_tenant_id,
)

logger = logging.getLogger(__name__)


class TenantWorkspacePool:
    """Manages tenant workspace lifecycle with resource limits.

    Features:
    - Lazy initialization (create on first access)
    - LRU eviction (remove least recently used when at capacity)
    - Idle timeout (auto-cleanup inactive workspaces)
    - Resource tracking (memory, connections per tenant)
    """

    def __init__(
        self,
        base_working_dir: Path,
        max_tenants: int = 100,
        max_concurrent_per_tenant: int = 10,
        idle_timeout: timedelta = timedelta(hours=1),
    ):
        self._base = base_working_dir
        self._max_tenants = max_tenants
        self._max_concurrent = max_concurrent_per_tenant
        self._idle_timeout = idle_timeout

        # Active workspaces
        self._workspaces: Dict[str, Workspace] = {}
        self._last_access: Dict[str, datetime] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}

        # Synchronization
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False

    async def start(self) -> None:
        """Start background cleanup task."""
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop()
        )
        logger.info(
            f"TenantWorkspacePool started: "
            f"max_tenants={self._max_tenants}, "
            f"idle_timeout={self._idle_timeout}"
        )

    async def stop(self) -> None:
        """Stop all workspaces and cleanup."""
        self._shutdown = True

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            # Stop all workspaces
            stop_tasks = [
                ws.stop() for ws in self._workspaces.values()
            ]
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)

            self._workspaces.clear()
            self._last_access.clear()
            self._semaphores.clear()

        logger.info("TenantWorkspacePool stopped")

    async def get_or_create(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
    ) -> Workspace:
        """Get existing or create new workspace for tenant.

        Args:
            tenant_id: Unique tenant identifier
            agent_id: Optional agent ID (defaults to tenant_id)

        Returns:
            Workspace instance for the tenant

        Raises:
            TenantLimitExceeded: If max tenants reached and can't evict
            TenantBlocked: If tenant is in blocklist
        """
        if self._shutdown:
            raise RuntimeError("Pool is shutting down")

        async with self._lock:
            # Check if exists
            if tenant_id in self._workspaces:
                self._last_access[tenant_id] = datetime.now()
                return self._workspaces[tenant_id]

            # Check capacity
            if len(self._workspaces) >= self._max_tenants:
                await self._evict_lru_tenant()

            # Create workspace
            workspace_dir = self._get_tenant_dir(tenant_id)
            workspace_dir.mkdir(parents=True, exist_ok=True)

            # Initialize tenant structure if new
            await self._init_tenant_structure(workspace_dir)

            # Create and start workspace
            actual_agent_id = agent_id or tenant_id
            workspace = Workspace(
                agent_id=actual_agent_id,
                workspace_dir=str(workspace_dir),
            )
            await workspace.start()

            self._workspaces[tenant_id] = workspace
            self._last_access[tenant_id] = datetime.now()
            self._semaphores[tenant_id] = asyncio.Semaphore(
                self._max_concurrent
            )

            logger.info(
                f"Created workspace for tenant: {tenant_id} "
                f"at {workspace_dir}"
            )
            return workspace

    async def get_semaphore(self, tenant_id: str) -> asyncio.Semaphore:
        """Get concurrency semaphore for tenant."""
        async with self._lock:
            if tenant_id not in self._semaphores:
                self._semaphores[tenant_id] = asyncio.Semaphore(
                    self._max_concurrent
                )
            return self._semaphores[tenant_id]

    async def get_workspace(self, tenant_id: str) -> Optional[Workspace]:
        """Get workspace if exists (doesn't create)."""
        async with self._lock:
            return self._workspaces.get(tenant_id)

    async def remove_tenant(self, tenant_id: str) -> bool:
        """Remove and stop a tenant's workspace."""
        async with self._lock:
            if tenant_id not in self._workspaces:
                return False

            workspace = self._workspaces.pop(tenant_id)
            self._last_access.pop(tenant_id, None)
            self._semaphores.pop(tenant_id, None)

        # Stop outside lock
        await workspace.stop()
        logger.info(f"Removed workspace for tenant: {tenant_id}")
        return True

    def _get_tenant_dir(self, tenant_id: str) -> Path:
        """Get working directory for tenant."""
        if tenant_id == "default":
            return self._base / "default"
        # Sanitize tenant_id for filesystem
        safe_id = "".join(
            c for c in tenant_id
            if c.isalnum() or c in "_-"
        )
        return self._base / f"tenant-{safe_id}"

    async def _init_tenant_structure(self, tenant_dir: Path) -> None:
        """Initialize directory structure for new tenant."""
        # Core directories
        (tenant_dir / "skills").mkdir(exist_ok=True)
        (tenant_dir / "customized_skills").mkdir(exist_ok=True)
        (tenant_dir / "memory").mkdir(exist_ok=True)
        (tenant_dir / "media").mkdir(exist_ok=True)
        (tenant_dir / "files").mkdir(exist_ok=True)

        # Config and data files will be created on first use

    async def _evict_lru_tenant(self) -> None:
        """Evict least recently used tenant when at capacity."""
        if not self._last_access:
            raise TenantLimitExceeded(
                f"Max tenants ({self._max_tenants}) reached, "
                "no tenants available for eviction"
            )

        # Find LRU tenant
        lru_tenant = min(
            self._last_access.keys(),
            key=lambda k: self._last_access[k]
        )

        # Check if it's been idle long enough
        idle_time = datetime.now() - self._last_access[lru_tenant]
        if idle_time < timedelta(minutes=5):
            raise TenantLimitExceeded(
                f"Max tenants ({self._max_tenants}) reached "
                f"and all tenants are active"
            )

        await self.remove_tenant(lru_tenant)
        logger.info(f"Evicted idle tenant: {lru_tenant} (idle={idle_time})")

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup idle workspaces."""
        while not self._shutdown:
            try:
                await asyncio.sleep(60)  # Check every minute

                async with self._lock:
                    now = datetime.now()
                    to_evict = []

                    for tenant_id, last_access in self._last_access.items():
                        if now - last_access > self._idle_timeout:
                            to_evict.append(tenant_id)

                # Evict outside lock
                for tenant_id in to_evict:
                    await self.remove_tenant(tenant_id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Cleanup loop error")

    async def get_stats(self) -> dict:
        """Get pool statistics."""
        async with self._lock:
            return {
                "total_tenants": len(self._workspaces),
                "max_tenants": self._max_tenants,
                "active_semaphores": len(self._semaphores),
                "tenant_ids": list(self._workspaces.keys()),
            }


class TenantLimitExceeded(Exception):
    """Raised when tenant limit is reached."""
    pass


class TenantBlocked(Exception):
    """Raised when tenant is blocked."""
    pass
```

---

## 4. Middleware Implementation

### 4.1 Tenant Security Middleware

**File:** `src/copaw/app/middleware/tenant_security.py`

```python
import re
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...config.context import current_tenant_id, current_user_id


class TenantSecurityMiddleware(BaseHTTPMiddleware):
    """Validates tenant headers and sets security context.

    Order: Must be early in middleware stack (before routing).
    """

    # Valid tenant ID pattern: alphanumeric, underscore, hyphen
    TENANT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

    def __init__(
        self,
        app,
        allow_list: Optional[Set[str]] = None,
        block_list: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self._allow_list = allow_list
        self._block_list = block_list or set()

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id = request.headers.get("X-Tenant-Id", "default")
        user_id = request.headers.get("X-User-Id", "anonymous")

        # Validate tenant ID format
        if not self._validate_tenant_id(tenant_id):
            return Response(
                status_code=400,
                content=json.dumps({
                    "error": "Invalid tenant ID format",
                    "detail": "Must be 1-64 alphanumeric, underscore, or hyphen"
                }),
                media_type="application/json"
            )

        # Check block/allow lists
        if tenant_id in self._block_list:
            return Response(
                status_code=403,
                content=json.dumps({
                    "error": "Tenant access denied",
                    "detail": f"Tenant '{tenant_id}' is blocked"
                }),
                media_type="application/json"
            )

        if self._allow_list and tenant_id not in self._allow_list:
            return Response(
                status_code=403,
                content=json.dumps({
                    "error": "Tenant not authorized",
                    "detail": f"Tenant '{tenant_id}' not in allow list"
                }),
                media_type="application/json"
            )

        # Set context for this request
        tenant_token = current_tenant_id.set(tenant_id)
        user_token = current_user_id.set(user_id)

        try:
            response = await call_next(request)
            # Add tenant info to response headers for debugging
            response.headers["X-Tenant-Id-Processed"] = tenant_id
            return response
        finally:
            current_tenant_id.reset(tenant_token)
            current_user_id.reset(user_token)

    def _validate_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format."""
        if not tenant_id:
            return False
        return bool(self.TENANT_ID_PATTERN.match(tenant_id))
```

### 4.2 Tenant Context Middleware

**File:** `src/copaw/app/middleware/tenant_context.py`

```python
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...config.context import (
    current_tenant_workspace,
    get_current_tenant_id,
)
from ..workspace.tenant_pool import TenantWorkspacePool


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Sets up tenant workspace and manages request-level context.

    Must run after TenantSecurityMiddleware.
    """

    def __init__(self, app, tenant_pool: TenantWorkspacePool):
        super().__init__(app)
        self._pool = tenant_pool

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id = get_current_tenant_id()

        # Get or create workspace (may raise TenantLimitExceeded)
        try:
            workspace = await self._pool.get_or_create(tenant_id)
        except TenantLimitExceeded as e:
            return Response(
                status_code=503,
                content=json.dumps({
                    "error": "Service overloaded",
                    "detail": str(e)
                }),
                media_type="application/json"
            )

        # Set workspace in context for quick access
        workspace_token = current_tenant_workspace.set(workspace)
        request.state.workspace = workspace

        # Get semaphore for concurrency control
        semaphore = await self._pool.get_semaphore(tenant_id)

        try:
            # Limit concurrent requests per tenant
            async with semaphore:
                response = await call_next(request)
                return response
        finally:
            current_tenant_workspace.reset(workspace_token)
```

---

## 5. Router Adaptations

### 5.1 Console Router

**File:** `src/copaw/app/routers/console.py`

```python
@router.post("/chat")
async def post_console_chat(
    request_data: Union[AgentRequest, dict],
    request: Request,
) -> StreamingResponse:
    """Stream agent response with tenant isolation."""

    # Get workspace from context (set by middleware)
    workspace = request.state.workspace

    # Get tenant/user info from context
    tenant_id = get_current_tenant_id()
    user_id = get_current_user_id()

    console_channel = await workspace.channel_manager.get_channel("console")
    if console_channel is None:
        raise HTTPException(
            status_code=503,
            detail="Channel Console not found",
        )

    # Build payload with tenant context
    native_payload = _extract_session_and_payload(request_data)

    # Session ID includes tenant for isolation
    session_id = f"console:{tenant_id}:{user_id}:{uuid.uuid4().hex[:8]}"

    # Create chat with tenant-scoped session
    chat = await workspace.chat_manager.get_or_create_chat(
        session_id=session_id,
        user_id=user_id,
        channel_id="console",
        name=f"Chat-{tenant_id}-{user_id[:8]}",
    )

    # ... rest of implementation
```

### 5.2 Cron Router

**File:** `src/copaw/app/routers/cron.py`

```python
@router.get("/crons")
async def list_cron_jobs(request: Request) -> list[CronJobView]:
    """List cron jobs for current tenant only."""
    workspace = request.state.workspace

    # CronManager is tenant-scoped via Workspace
    jobs = await workspace.cron_manager.list_jobs()

    # Add state information
    views = []
    for job in jobs:
        state = workspace.cron_manager.get_state(job.id)
        views.append(CronJobView(spec=job, state=state))

    return views


@router.post("/crons")
async def create_cron_job(
    request: Request,
    spec: CronJobSpec,
) -> dict:
    """Create cron job for current tenant."""
    workspace = request.state.workspace
    tenant_id = get_current_tenant_id()

    # Ensure job is tagged with tenant
    spec.meta["tenant_id"] = tenant_id

    await workspace.cron_manager.create_or_replace_job(spec)
    return {"id": spec.id, "status": "created"}
```

---

## 6. Tenant-Aware Components

### 6.1 Token Usage Manager

**File:** `src/copaw/token_usage/tenant_manager.py`

```python
from pathlib import Path
from typing import Dict, Optional
import asyncio

from .manager import TokenManager


class TenantTokenManager:
    """Manages token usage tracking per tenant with isolation."""

    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._managers: Dict[str, TokenManager] = {}
        self._lock = asyncio.Lock()

    async def get_manager(self, tenant_id: str) -> TokenManager:
        """Get or create token manager for tenant."""
        async with self._lock:
            if tenant_id not in self._managers:
                tenant_dir = self._base / f"tenant-{tenant_id}"
                tenant_dir.mkdir(parents=True, exist_ok=True)

                self._managers[tenant_id] = TokenManager(
                    storage_dir=tenant_dir
                )
            return self._managers[tenant_id]

    async def record_usage(
        self,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage for tenant."""
        manager = await self.get_manager(tenant_id)
        await manager.record_usage(model, input_tokens, output_tokens)

    async def get_usage_stats(
        self,
        tenant_id: str,
        period: str = "day",
    ) -> dict:
        """Get token usage stats for tenant."""
        manager = await self.get_manager(tenant_id)
        return await manager.get_stats(period)

    async def check_quota(self, tenant_id: str) -> bool:
        """Check if tenant has exceeded quota."""
        # TODO: Implement quota checking
        stats = await self.get_usage_stats(tenant_id)
        # Compare against tenant-specific limits
        return True
```

### 6.2 Tool Guard Configuration

**File:** `src/copaw/security/tenant_tool_guard.py`

```python
from pathlib import Path
from typing import Dict, Optional, Any
import yaml

from .tool_guard import ToolGuard


class TenantToolGuard:
    """Tenant-specific tool guard with custom policies."""

    def __init__(self, base_config_dir: Path):
        self._base = base_config_dir
        self._guards: Dict[str, ToolGuard] = {}

    def get_guard(self, tenant_id: str) -> ToolGuard:
        """Get or load tool guard for tenant."""
        if tenant_id not in self._guards:
            config_path = self._get_tenant_config_path(tenant_id)

            if config_path.exists():
                config = yaml.safe_load(config_path.read_text())
            else:
                # Use default config
                config = self._load_default_config()

            self._guards[tenant_id] = ToolGuard(config)

        return self._guards[tenant_id]

    def _get_tenant_config_path(self, tenant_id: str) -> Path:
        tenant_dir = self._base / f"tenant-{tenant_id}"
        return tenant_dir / "tool_guard.yaml"

    def _load_default_config(self) -> dict:
        """Load default tool guard configuration."""
        default_path = self._base / "default" / "tool_guard.yaml"
        if default_path.exists():
            return yaml.safe_load(default_path.read_text())
        return {}

    async def check_tool_execution(
        self,
        tenant_id: str,
        tool_name: str,
        params: dict,
    ) -> ToolGuardResult:
        """Check if tool execution is allowed for tenant."""
        guard = self.get_guard(tenant_id)
        return await guard.check(tool_name, params)
```

### 6.3 Screenshot Storage Isolation

**File:** `src/copaw/agents/tools/desktop_screenshot.py`

```python
from ...config.context import get_current_tenant_id
from ...constant import get_tenant_working_dir


def get_screenshot_storage_path() -> Path:
    """Get tenant-isolated screenshot storage path."""
    tenant_id = get_current_tenant_id()
    tenant_dir = get_tenant_working_dir(tenant_id)
    screenshot_dir = tenant_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    return screenshot_dir


async def desktop_screenshot() -> ToolResponse:
    """Capture screenshot with tenant isolation."""
    # ... capture logic ...

    # Store in tenant-specific directory
    storage_dir = get_screenshot_storage_path()
    filename = f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    filepath = storage_dir / filename

    # ... save screenshot ...
```

---

## 7. Directory Structure

### 7.1 Tenant Directory Layout

```
~/.copaw/  # or COPAW_WORKING_DIR
├── default/                          # Default tenant (backward compatible)
│   ├── config.yaml
│   ├── config.json
│   ├── skills/
│   ├── customized_skills/
│   ├── memory/
│   ├── media/
│   ├── files/
│   ├── screenshots/
│   ├── jobs.json
│   ├── chats.json
│   ├── token_usage.json
│   └── tool_guard.yaml
├── tenant-acme-corp/                 # Tenant: acme-corp
│   ├── config.yaml
│   ├── config.json
│   ├── skills/
│   ├── customized_skills/
│   ├── memory/
│   ├── media/
│   ├── files/
│   ├── screenshots/
│   ├── jobs.json
│   ├── chats.json
│   ├── token_usage.json
│   └── tool_guard.yaml
└── tenant-startup-inc/               # Tenant: startup-inc
    └── ... (same structure)
```

### 7.2 Tenant-Aware Path Utilities

**File:** `src/copaw/config/tenant_paths.py`

```python
from pathlib import Path
from .constant import WORKING_DIR
from .context import get_current_tenant_id


def get_tenant_working_dir(tenant_id: Optional[str] = None) -> Path:
    """Get working directory for tenant.

    Args:
        tenant_id: Tenant ID (defaults to current context)

    Returns:
        Path to tenant's working directory
    """
    if tenant_id is None:
        tenant_id = get_current_tenant_id()

    if tenant_id == "default":
        return WORKING_DIR / "default"

    # Sanitize for filesystem safety
    safe_id = "".join(
        c for c in tenant_id
        if c.isalnum() or c in "_-"
    )
    return WORKING_DIR / f"tenant-{safe_id}"


def get_tenant_config_path(tenant_id: Optional[str] = None) -> Path:
    """Get config file path for tenant."""
    return get_tenant_working_dir(tenant_id) / "config.yaml"


def get_tenant_memory_dir(tenant_id: Optional[str] = None) -> Path:
    """Get memory directory for tenant."""
    return get_tenant_working_dir(tenant_id) / "memory"


def get_tenant_media_dir(tenant_id: Optional[str] = None) -> Path:
    """Get media directory for tenant."""
    return get_tenant_working_dir(tenant_id) / "media"


def get_tenant_jobs_path(tenant_id: Optional[str] = None) -> Path:
    """Get cron jobs file path for tenant."""
    return get_tenant_working_dir(tenant_id) / "jobs.json"
```

---

## 8. Migration Strategy

### 8.1 Backward Compatibility

Existing single-tenant deployments should continue to work:

```python
# src/copaw/config/context.py

def get_current_tenant_id() -> str:
    """Get current tenant ID with backward compatibility.

    Returns 'default' if not in multi-tenant context.
    """
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        # Not in multi-tenant context, use legacy behavior
        return "default"
    return tenant_id
```

### 8.2 Data Migration

```python
# migration script
async def migrate_existing_to_tenant():
    """Migrate existing default data to tenant-default structure."""
    source = WORKING_DIR  # Legacy flat structure
    target = WORKING_DIR / "default"  # New tenant structure

    if target.exists():
        return  # Already migrated

    target.mkdir(parents=True, exist_ok=True)

    # Move existing files
    for item in source.iterdir():
        if item.name.startswith("tenant-"):
            continue  # Skip existing tenant directories
        if item.name == "default":
            continue  # Skip target itself

        shutil.move(str(item), str(target / item.name))
```

---

## 9. Security Considerations

### 9.1 Tenant Isolation Enforcement

| Layer | Enforcement Mechanism |
|-------|----------------------|
| Filesystem | Path resolution through `get_tenant_working_dir()` |
| Memory | Separate Workspace instances per tenant |
| Network | N/A (shared HTTP server) |
| Database | Separate JSON files per tenant |
| Process | Same process, context-based isolation |

### 9.2 Cross-Tenant Attack Prevention

1. **Path Traversal:** Sanitize tenant_id, validate resolved paths
2. **Resource Exhaustion:** Per-tenant semaphores and limits
3. **Information Leakage:** Clear context between requests
4. **Privilege Escalation:** No tenant can access "default" without permission

---

## 10. Performance Considerations

### 10.1 Resource Overhead

| Metric | Single-Tenant | Multi-Tenant |
|--------|---------------|--------------|
| Memory | 1x | ~1.5-2x (workspace pool) |
| Startup | Fast | Slower (lazy init) |
| Per-request | Minimal | +context switch |
| Storage | 1x | Nx (per tenant) |

### 10.2 Optimization Strategies

1. **Workspace Pooling:** Reuse workspace instances with LRU eviction
2. **Lazy Loading:** Only create workspace on first tenant access
3. **Connection Pooling:** Share DB connections where safe
4. **Caching:** Tenant-scoped caches with TTL

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/unit/test_tenant_isolation.py

async def test_tenant_workspace_isolation():
    """Verify workspaces are properly isolated."""
    pool = TenantWorkspacePool(base_dir=tmp_path)
    await pool.start()

    ws1 = await pool.get_or_create("tenant-1")
    ws2 = await pool.get_or_create("tenant-2")

    # Workspaces should be different instances
    assert ws1 is not ws2

    # Working directories should be different
    assert ws1.workspace_dir != ws2.workspace_dir

    await pool.stop()


async def test_tenant_context_propagation():
    """Verify context variables propagate correctly."""
    token = current_tenant_id.set("test-tenant")

    try:
        # Simulate async call
        async def inner():
            return get_current_tenant_id()

        result = await inner()
        assert result == "test-tenant"
    finally:
        current_tenant_id.reset(token)
```

### 11.2 Integration Tests

```python
# tests/integrated/test_tenant_api.py

async def test_tenant_api_isolation(client):
    """Test that API calls respect tenant boundaries."""

    # Create file as tenant-1
    response = await client.post(
        "/api/files",
        headers={"X-Tenant-Id": "tenant-1"},
        data={"content": "secret"}
    )
    file_id = response.json()["id"]

    # Try to access as tenant-2
    response = await client.get(
        f"/api/files/{file_id}",
        headers={"X-Tenant-Id": "tenant-2"}
    )
    assert response.status_code == 404
```

---

## 12. Deployment Configuration

### 12.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COPAW_MULTI_TENANT` | Enable multi-tenant mode | `false` |
| `COPAW_MAX_TENANTS` | Maximum concurrent tenants | `100` |
| `COPAW_TENANT_IDLE_TIMEOUT` | Minutes before eviction | `60` |
| `COPAW_MAX_CONCURRENT_PER_TENANT` | Max concurrent requests | `10` |

### 12.2 Feature Flag

```python
# src/copaw/config/constant.py

MULTI_TENANT_ENABLED = EnvVarLoader.get_bool(
    "COPAW_MULTI_TENANT",
    False
)
```

---

## 13. Summary

This design provides comprehensive multi-tenant isolation through:

1. **Workspace Pool Pattern:** Each tenant gets independent Workspace instance
2. **Context-Based Routing:** `contextvars` propagate tenant identity
3. **Path Isolation:** All file operations use tenant-scoped directories
4. **Resource Management:** Per-tenant limits with LRU eviction
5. **Backward Compatibility:** Existing deployments work without changes

The design balances isolation strength with resource efficiency, allowing CoPaw to serve multiple users from a single instance while maintaining security boundaries.
