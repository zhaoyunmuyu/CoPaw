# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
import os
from collections import OrderedDict
from pathlib import Path

from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from dotenv import load_dotenv

from .command_dispatch import (
    _get_last_user_text,
    _is_command,
    run_command_path,
)
from .query_error_dump import write_query_error_dump
from .session import SafeJSONSession
from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.memory import MemoryManager
from ...agents.model_factory import create_model_and_formatter
from ...agents.react_agent import CoPawAgent
from ...agents.tools import read_file, write_file, edit_file
from ...agents.utils.token_counting import _get_token_counter
from ...config import load_config
from ...config.utils import get_config_path
from ...providers.store import get_providers_json_path
from ...constant import (
    MEMORY_COMPACT_RATIO,
    get_runtime_working_dir,
    set_request_user_id,
    reset_request_user_id,
    get_request_working_dir,
    get_request_user_id,
)

logger = logging.getLogger(__name__)

# Environment variable for MemoryManager cache max size
COPAW_MM_CACHE_MAX_SIZE = int(os.environ.get("COPAW_MM_CACHE_MAX_SIZE", "50"))


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._mcp_manager = None  # MCP client manager for hot-reload
        self.memory_manager: MemoryManager | None = None
        # Per-user MemoryManager cache for performance optimization
        self._memory_manager_cache: OrderedDict[
            str, MemoryManager
        ] = OrderedDict()
        self._mm_cache_lock = asyncio.Lock()
        self._mm_cache_max_size = COPAW_MM_CACHE_MAX_SIZE

    def set_chat_manager(self, chat_manager):
        """Set chat manager for auto-registration.

        Args:
            chat_manager: ChatManager instance
        """
        self._chat_manager = chat_manager

    def set_mcp_manager(self, mcp_manager):
        """Set MCP client manager for hot-reload support.

        Args:
            mcp_manager: MCPClientManager instance
        """
        self._mcp_manager = mcp_manager

    async def _get_memory_manager_for_user(
        self,
        user_id: str,
        working_dir: Path,
    ) -> MemoryManager:
        """Get or create MemoryManager for user with LRU caching.

        This method caches MemoryManager instances per user to avoid the
        ~500ms initialization overhead on subsequent requests from the same user.
        Uses LRU eviction to limit memory usage.

        Args:
            user_id: User identifier
            working_dir: User's working directory

        Returns:
            MemoryManager instance for the user
        """
        async with self._mm_cache_lock:
            if user_id in self._memory_manager_cache:
                # Move to end for LRU
                self._memory_manager_cache.move_to_end(user_id)
                logger.debug("Cache hit: MemoryManager for user %s", user_id)
                return self._memory_manager_cache[user_id]

            # Create new MemoryManager for user
            config = load_config()
            chat_model, formatter = create_model_and_formatter()
            token_counter = _get_token_counter()
            toolkit = Toolkit()
            toolkit.register_tool_function(read_file)
            toolkit.register_tool_function(write_file)
            toolkit.register_tool_function(edit_file)

            mm = MemoryManager(
                working_dir=str(working_dir),
                chat_model=chat_model,
                formatter=formatter,
                token_counter=token_counter,
                toolkit=toolkit,
                max_input_length=config.agents.running.max_input_length,
                memory_compact_ratio=MEMORY_COMPACT_RATIO,
            )
            await mm.start()
            self._memory_manager_cache[user_id] = mm
            logger.info(
                "Created and cached MemoryManager for user: %s", user_id
            )

            # Evict oldest if over limit
            while len(self._memory_manager_cache) > self._mm_cache_max_size:
                oldest_user, oldest_mm = self._memory_manager_cache.popitem(
                    last=False
                )
                try:
                    await oldest_mm.close()
                    logger.info(
                        "Evicted MemoryManager from cache for user: %s",
                        oldest_user,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to close evicted MemoryManager: %s", e
                    )

            return mm

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """Handle agent query with per-request user isolation.

        For HTTP requests, user directory auto-initialization is handled
        by the HTTP middleware. For Channel requests (which bypass the
        HTTP middleware), initialization happens here.
        """
        from ...agents.utils.setup_utils import initialize_user_directory

        # Set request context for user-specific directory routing
        # 优先使用 request 中的 user_id，否则使用当前请求上下文中的 user_id（支持 cron 任务）
        user_id = (
            request.user_id if request else None
        ) or get_request_user_id()
        user_token = set_request_user_id(user_id)

        # Auto-initialize user directory if this is a new user.
        # Channel requests bypass HTTP middleware, so initialization
        # happens here. HTTP requests already initialized in middleware.
        user_id = request.user_id if request else None
        if user_id:
            try:
                config = load_config()  # Uses request-scoped directory
                initialized = initialize_user_directory(
                    user_id=user_id,
                    language=config.agents.language,
                )
                if initialized:
                    logger.info(
                        "Auto-initialized directory for user: %s (via query_handler)",
                        user_id,
                    )
            except Exception as e:
                logger.warning(
                    "Auto-initialization failed for user %s: %s",
                    user_id,
                    e,
                )
                # Continue anyway - let the request proceed and fail naturally
                # if config is truly missing

        # Command path: do not create agent; yield from run_command_path
        query = _get_last_user_text(msgs)
        if query and _is_command(query):
            logger.info("Command path: %s", query.strip()[:50])
            try:
                async for msg, last in run_command_path(request, msgs, self):
                    yield msg, last
                return
            finally:
                # Always restore previous context
                reset_request_user_id(user_token)

        agent = None
        chat = None
        session_state_loaded = False
        request_memory_manager = (
            None  # Per-request MemoryManager (for LRU cache)
        )
        # Note: We no longer override the shared MemoryManager's working_path.
        # Instead, we use per-user cached MemoryManager instances for better performance.
        if self.memory_manager is not None:
            # Global memory_manager is deprecated, close it if exists
            try:
                await self.memory_manager.close()
                logger.info("Closed deprecated global MemoryManager")
            except Exception as e:
                logger.warning("Failed to close global MemoryManager: %s", e)
            self.memory_manager = None
        try:
            session_id = request.session_id
            user_id = request.user_id
            channel = getattr(request, "channel", DEFAULT_CHANNEL)

            # Debug: Log config path and providers.json path
            config_path = get_config_path()
            providers_path = get_providers_json_path()
            logger.info(
                "Handle agent query:\n%s",
                json.dumps(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "channel": channel,
                        "msgs_len": len(msgs) if msgs else 0,
                        "config_path": str(config_path),
                        "providers_path": str(providers_path),
                        "working_dir": str(get_request_working_dir()),
                        "msgs_str": str(msgs)[:300] + "...",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            env_context = build_env_context(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(
                    get_request_working_dir()
                ),  # Use request-scoped
            )

            # Get MCP clients from manager (hot-reloadable)
            mcp_clients = []
            if self._mcp_manager is not None:
                mcp_clients = await self._mcp_manager.get_clients()

            config = load_config()
            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length

            # Create per-request chat_model and formatter using request-scoped config
            # This ensures each user's API keys and model settings are used
            chat_model, formatter = create_model_and_formatter()

            # Create per-request toolkit
            toolkit = Toolkit()
            toolkit.register_tool_function(read_file)
            toolkit.register_tool_function(write_file)
            toolkit.register_tool_function(edit_file)

            # Get token counter
            token_counter = _get_token_counter()

            # Get MemoryManager for user from LRU cache (or create new one)
            # This avoids ~500ms initialization overhead for returning users
            working_dir = get_request_working_dir()
            memory_manager_to_use = await self._get_memory_manager_for_user(
                user_id=user_id,
                working_dir=working_dir,
            )
            logger.debug("Using MemoryManager for user: %s", user_id)

            agent = CoPawAgent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                memory_manager=memory_manager_to_use,
                max_iters=max_iters,
                max_input_length=max_input_length,
            )
            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)

            logger.debug(
                f"Agent Query msgs {msgs}",
            )

            name = "New Chat"
            if len(msgs) > 0:
                content = msgs[0].get_text_content()
                if content:
                    name = msgs[0].get_text_content()[:10]
                else:
                    name = "Media Message"

            if self._chat_manager is not None:
                chat = await self._chat_manager.get_or_create_chat(
                    session_id,
                    user_id,
                    channel,
                    name=name,
                )

            try:
                await self.session.load_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )
            except KeyError as e:
                logger.warning(
                    "load_session_state skipped (state schema mismatch): %s; "
                    "will save fresh state on completion to recover file",
                    e,
                )
            session_state_loaded = True

            # Rebuild system prompt so it always reflects the latest
            # AGENTS.md / SOUL.md / PROFILE.md, not the stale one saved
            # in the session state.
            agent.rebuild_sys_prompt()

            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent(msgs),
            ):
                yield msg, last

        except asyncio.CancelledError as exc:
            logger.info(f"query_handler: {session_id} cancelled!")
            if agent is not None:
                await agent.interrupt()
            raise RuntimeError("Task has been cancelled!") from exc
        except Exception as e:
            debug_dump_path = write_query_error_dump(
                request=request,
                exc=e,
                locals_=locals(),
            )
            path_hint = (
                f"\n(Details:  {debug_dump_path})" if debug_dump_path else ""
            )
            logger.exception(f"Error in query handler: {e}{path_hint}")
            if debug_dump_path:
                setattr(e, "debug_dump_path", debug_dump_path)
                if hasattr(e, "add_note"):
                    e.add_note(
                        f"(Details:  {debug_dump_path})",
                    )
                suffix = f"\n(Details:  {debug_dump_path})"
                e.args = (
                    (f"{e.args[0]}{suffix}" if e.args else suffix.strip()),
                ) + e.args[1:]
            raise
        finally:
            try:
                if agent is not None and session_state_loaded:
                    await self.session.save_session_state(
                        session_id=session_id,
                        user_id=user_id,
                        agent=agent,
                    )

                if self._chat_manager is not None and chat is not None:
                    await self._chat_manager.update_chat(chat, user_id=user_id)
            finally:
                # Always restore previous context
                reset_request_user_id(user_token)

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        # Load environment variables from .env file
        env_path = Path(__file__).resolve().parents[4] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded environment variables from {env_path}")
        else:
            logger.debug(
                f".env file not found at {env_path}, "
                "using existing environment variables",
            )

        # Use runtime working dir for session storage (global initialization)
        session_dir = str(get_runtime_working_dir() / "sessions")
        self.session = SafeJSONSession(save_dir=session_dir)

        # Note: MemoryManager instances are now created on-demand per user
        # via _get_memory_manager_for_user() with LRU caching, rather than
        # a single global instance. This provides better performance and
        # full user isolation.

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        # Close all cached MemoryManager instances
        async with self._mm_cache_lock:
            for user_id, mm in list(self._memory_manager_cache.items()):
                try:
                    await mm.close()
                    logger.info("Closed MemoryManager for user: %s", user_id)
                except Exception as e:
                    logger.warning(
                        "Failed to close MemoryManager for user %s: %s",
                        user_id,
                        e,
                    )
            self._memory_manager_cache.clear()

        # Also close the legacy shared memory_manager if exists
        try:
            await self.memory_manager.close()
        except Exception as e:
            logger.warning(f"MemoryManager stop failed: {e}")
