# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
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
from ...constant import (
    MEMORY_COMPACT_RATIO,
    get_runtime_working_dir,
    set_request_user_id,
    reset_request_user_id,
    get_request_working_dir,
)

logger = logging.getLogger(__name__)


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._mcp_manager = None  # MCP client manager for hot-reload
        self.memory_manager: MemoryManager | None = None

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
        user_token = set_request_user_id(request.user_id if request else None)

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
                    logger.info("Auto-initialized directory for user: %s (via query_handler)", user_id)
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
        # Temporarily override MemoryManager's working_path for this request
        original_memory_manager_paths = None
        if self.memory_manager is not None:
            original_memory_manager_paths = (
                self.memory_manager.working_path,
                self.memory_manager.memory_path,
                self.memory_manager.tool_result_path,
            )
            request_wd = get_request_working_dir()
            self.memory_manager.working_path = request_wd
            self.memory_manager.memory_path = request_wd / "memory"
            self.memory_manager.tool_result_path = request_wd / "tool_result"
        try:
            session_id = request.session_id
            user_id = request.user_id
            channel = getattr(request, "channel", DEFAULT_CHANNEL)

            logger.info(
                "Handle agent query:\n%s",
                json.dumps(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "channel": channel,
                        "msgs_len": len(msgs) if msgs else 0,
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
                working_dir=str(get_request_working_dir()),  # Use request-scoped
            )

            # Get MCP clients from manager (hot-reloadable)
            mcp_clients = []
            if self._mcp_manager is not None:
                mcp_clients = await self._mcp_manager.get_clients()

            config = load_config()
            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length

            agent = CoPawAgent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                memory_manager=self.memory_manager,
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
                    await self._chat_manager.update_chat(chat)
            finally:
                # Restore MemoryManager's working_path
                if original_memory_manager_paths is not None and self.memory_manager is not None:
                    (
                        self.memory_manager.working_path,
                        self.memory_manager.memory_path,
                        self.memory_manager.tool_result_path,
                    ) = original_memory_manager_paths
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

        try:
            if self.memory_manager is None:
                # Get config for memory manager
                config = load_config()
                max_input_length = config.agents.running.max_input_length

                # Create model and formatter
                chat_model, formatter = create_model_and_formatter()

                # Get token counter
                token_counter = _get_token_counter()

                # Create toolkit for memory manager
                toolkit = Toolkit()
                toolkit.register_tool_function(read_file)
                toolkit.register_tool_function(write_file)
                toolkit.register_tool_function(edit_file)

                # Initialize MemoryManager with new parameters
                # Note: MemoryManager now uses request-scoped directories internally
                self.memory_manager = MemoryManager(
                    working_dir=str(get_runtime_working_dir()),  # Base path, overridden per-request
                    chat_model=chat_model,
                    formatter=formatter,
                    token_counter=token_counter,
                    toolkit=toolkit,
                    max_input_length=max_input_length,
                    memory_compact_ratio=MEMORY_COMPACT_RATIO,
                )
            await self.memory_manager.start()
        except Exception as e:
            logger.exception(f"MemoryManager start failed: {e}")

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        try:
            await self.memory_manager.close()
        except Exception as e:
            logger.warning(f"MemoryManager stop failed: {e}")
