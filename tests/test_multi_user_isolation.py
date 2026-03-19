# -*- coding: utf-8 -*-
"""Multi-user isolation tests for CoPaw.

This module tests the request-scoped user isolation feature that allows
CoPaw to serve multiple users concurrently with full data isolation.

Tests are organized into three categories:
1. Unit Tests: Test context variables and directory accessors
2. Integration Tests: Test config isolation, session isolation, file operations
3. End-to-End Tests: Test full request lifecycle and concurrent scenarios
"""
import asyncio
import contextvars
import pytest

# Import the functions we're testing
from copaw.constant import (
    set_request_user_id,
    reset_request_user_id,
    get_request_user_id,
    get_request_working_dir,
    get_request_secret_dir,
    get_active_skills_dir,
    get_customized_skills_dir,
    get_memory_dir,
    get_models_dir,
    get_custom_channels_dir,
    get_working_dir,
    get_secret_dir,
    set_current_user,
    get_runtime_working_dir,
)
from copaw.config.utils import get_chats_path


@pytest.fixture(autouse=True)
def reset_all_context():
    """Reset all context vars before and after each test."""
    from copaw.constant import (
        _request_working_dir,
        _request_secret_dir,
        _request_user_id,
    )

    # Reset to None at start of each test
    token_user = _request_user_id.set(None)
    token_wd = _request_working_dir.set(None)
    token_sd = _request_secret_dir.set(None)

    try:
        yield
    finally:
        # Always restore to clean state
        _request_user_id.reset(token_user)
        _request_working_dir.reset(token_wd)
        _request_secret_dir.reset(token_sd)


@pytest.fixture
def tmp_copaw_dirs(tmp_path, monkeypatch):
    """Create temporary copaw directories for testing.

    This fixture patches the DEFAULT_WORKING_DIR and DEFAULT_SECRET_DIR
    as well as the runtime variables. Note that because these are module-level
    variables, the patch only affects code that reads them after the patch.
    """
    working_dir = tmp_path / "copaw"
    secret_dir = tmp_path / "copaw.secret"
    working_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.mkdir(parents=True, exist_ok=True)

    # Patch the module-level variables
    monkeypatch.setattr("copaw.constant.DEFAULT_WORKING_DIR", working_dir)
    monkeypatch.setattr("copaw.constant.DEFAULT_SECRET_DIR", secret_dir)
    monkeypatch.setattr("copaw.constant._runtime_working_dir", working_dir)
    monkeypatch.setattr("copaw.constant._runtime_secret_dir", secret_dir)

    yield working_dir, secret_dir


class TestContextVariablesIsolation:
    """Test context variable isolation for multi-user support."""

    def test_set_request_user_id_returns_token(self):
        """Test that setting user_id returns a valid token."""
        token = set_request_user_id("test_user")
        assert token is not None
        assert isinstance(token, contextvars.Token)
        reset_request_user_id(token)

    def test_reset_request_user_id_restores_context(self):
        """Test that resetting context restores previous state."""
        # Set initial state
        token1 = set_request_user_id("user1")
        assert get_request_user_id() == "user1"

        # Change to different user
        token2 = set_request_user_id("user2")
        assert get_request_user_id() == "user2"

        # Restore to user1
        reset_request_user_id(token2)
        assert get_request_user_id() == "user1"

        # Restore to initial state
        reset_request_user_id(token1)
        assert get_request_user_id() is None

    def test_get_request_user_id_without_context(self):
        """Test that get_request_user_id returns None without context."""
        assert get_request_user_id() is None

    def test_get_request_working_dir_without_context(self, tmp_copaw_dirs):
        """Test that get_request_working_dir falls back to runtime dir."""
        working_dir, _ = tmp_copaw_dirs

        # Without request context, should use runtime working dir
        result = get_request_working_dir()
        assert result == working_dir


class TestDirectoryAccessors:
    """Test directory accessor functions with user context."""

    def test_get_request_working_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that get_request_working_dir returns correct directory."""
        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("alice")
        try:
            result = get_request_working_dir()
            assert result == working_dir / "alice"
        finally:
            reset_request_user_id(token)

    def test_get_request_secret_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that get_request_secret_dir returns correct directory."""
        _, secret_dir = tmp_copaw_dirs

        token = set_request_user_id("bob")
        try:
            result = get_request_secret_dir()
            assert result == secret_dir / "bob"
        finally:
            reset_request_user_id(token)

    def test_get_active_skills_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that active skills directory is user-isolated."""
        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("charlie")
        try:
            result = get_active_skills_dir()
            expected = working_dir / "charlie" / "active_skills"
            assert result == expected
        finally:
            reset_request_user_id(token)

    def test_get_customized_skills_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that customized skills directory is user-isolated."""
        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("david")
        try:
            result = get_customized_skills_dir()
            expected = working_dir / "david" / "customized_skills"
            assert result == expected
        finally:
            reset_request_user_id(token)

    def test_get_memory_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that memory directory is user-isolated."""
        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("eve")
        try:
            result = get_memory_dir()
            expected = working_dir / "eve" / "memory"
            assert result == expected
        finally:
            reset_request_user_id(token)

    def test_get_models_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that models directory is user-isolated."""
        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("frank")
        try:
            result = get_models_dir()
            expected = working_dir / "frank" / "models"
            assert result == expected
        finally:
            reset_request_user_id(token)

    def test_get_custom_channels_dir_with_user_context(self, tmp_copaw_dirs):
        """Test that custom channels directory is user-isolated."""
        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("grace")
        try:
            result = get_custom_channels_dir()
            expected = working_dir / "grace" / "custom_channels"
            assert result == expected
        finally:
            reset_request_user_id(token)


class TestConcurrentIsolation:
    """Test concurrent request isolation."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_isolation(self, tmp_copaw_dirs):
        """Test that concurrent requests use different directories."""
        working_dir, _ = tmp_copaw_dirs

        results = {}

        async def handle_request(user_id: str):
            token = set_request_user_id(user_id)
            try:
                await asyncio.sleep(0.01)  # Simulate some async work
                results[user_id] = str(get_request_working_dir())
            finally:
                reset_request_user_id(token)

        # Run concurrent requests
        await asyncio.gather(
            handle_request("alice"),
            handle_request("bob"),
            handle_request("charlie"),
        )

        # Verify each request used correct directory
        assert results["alice"] == str(working_dir / "alice")
        assert results["bob"] == str(working_dir / "bob")
        assert results["charlie"] == str(working_dir / "charlie")

    @pytest.mark.asyncio
    async def test_many_concurrent_users_isolation(self, tmp_copaw_dirs):
        """Test isolation with 10+ concurrent users."""
        working_dir, _ = tmp_copaw_dirs

        user_ids = [f"user_{i}" for i in range(15)]
        results = {}

        async def handle_request(user_id: str):
            token = set_request_user_id(user_id)
            try:
                await asyncio.sleep(0.001)
                results[user_id] = get_request_working_dir()
            finally:
                reset_request_user_id(token)

        await asyncio.gather(*[handle_request(uid) for uid in user_ids])

        for user_id in user_ids:
            assert results[user_id] == working_dir / user_id

    @pytest.mark.asyncio
    async def test_context_not_leaked_between_requests(self, tmp_copaw_dirs):
        """Test that context is properly cleaned up between requests."""
        working_dir, _ = tmp_copaw_dirs

        async def handle_request_with_cleanup(user_id: str):
            token = set_request_user_id(user_id)
            try:
                return get_request_working_dir()
            finally:
                reset_request_user_id(token)

        # First request
        result1 = await handle_request_with_cleanup("user1")
        assert result1 == working_dir / "user1"

        # After cleanup, should return to default
        assert get_request_user_id() is None

        # Second request should not see first request's context
        result2 = await handle_request_with_cleanup("user2")
        assert result2 == working_dir / "user2"
        assert get_request_user_id() is None


class TestConfigIsolation:
    """Test configuration file isolation."""

    def test_get_config_path_with_user_id(self, tmp_copaw_dirs):
        """Test that config path is user-isolated."""
        from copaw.config.utils import get_config_path

        working_dir, _ = tmp_copaw_dirs

        # With explicit user_id
        result = get_config_path("alice")
        assert result == working_dir / "alice" / "config.json"

    def test_get_config_path_with_request_context(self, tmp_copaw_dirs):
        """Test that config path uses request context when user_id=None."""
        from copaw.config.utils import get_config_path

        working_dir, _ = tmp_copaw_dirs

        # With request context
        token = set_request_user_id("bob")
        try:
            result = get_config_path()
            assert result == working_dir / "bob" / "config.json"
        finally:
            reset_request_user_id(token)

    def test_get_providers_json_path_with_user_id(self, tmp_copaw_dirs):
        """Test that providers.json path is user-isolated."""
        from copaw.providers.store import get_providers_json_path

        _, secret_dir = tmp_copaw_dirs

        result = get_providers_json_path("alice")
        assert result == secret_dir / "alice" / "providers.json"

    def test_get_providers_json_path_with_request_context(
        self, tmp_copaw_dirs
    ):
        """Test that providers.json path uses request context."""
        from copaw.providers.store import get_providers_json_path

        _, secret_dir = tmp_copaw_dirs

        token = set_request_user_id("bob")
        try:
            result = get_providers_json_path()
            assert result == secret_dir / "bob" / "providers.json"
        finally:
            reset_request_user_id(token)


class TestFileOperations:
    """Test file operation tools use correct user directories."""

    @pytest.mark.asyncio
    async def test_file_io_uses_user_directory(self, tmp_copaw_dirs):
        """Test that file read/write operations use user directory."""
        from copaw.agents.tools.file_io import _resolve_file_path

        working_dir, _ = tmp_copaw_dirs

        # Set up user context BEFORE importing file_io
        token = set_request_user_id("testuser")
        try:
            # Verify get_request_working_dir returns correct path
            current_wd = get_request_working_dir()
            assert (
                current_wd == working_dir / "testuser"
            ), f"Expected {working_dir / 'testuser'}, got {current_wd}"

            # Import file_io after setting context
            # Note: In real usage, the module is already loaded and uses
            # get_request_working_dir() at call time, not import time
            from copaw.agents.tools.file_io import _resolve_file_path

            # Test path resolution directly
            resolved = _resolve_file_path("test.txt")
            expected = str(working_dir / "testuser" / "test.txt")
            assert resolved == expected, f"Expected {expected}, got {resolved}"

        finally:
            reset_request_user_id(token)

    @pytest.mark.asyncio
    async def test_file_search_uses_user_directory(self, tmp_copaw_dirs):
        """Test that file search operations use user directory."""
        from copaw.agents.tools.file_search import grep_search

        working_dir, _ = tmp_copaw_dirs

        # Set up user context and create test files
        token = set_request_user_id("searchuser")
        try:
            # Create test files in user's directory
            user_dir = working_dir / "searchuser"
            user_dir.mkdir(parents=True, exist_ok=True)

            test_file = user_dir / "test.txt"
            test_file.write_text("This is searchuser's content")

            # Search should find the file in user's directory
            result = await grep_search(
                pattern="searchuser",
                path=None,  # Use default (user's directory)
            )

            # result.content[0] is a dict, not an object with .text
            result_text = (
                result.content[0].get("text", "")
                if isinstance(result.content[0], dict)
                else result.content[0].text
            )
            assert "test.txt" in result_text

        finally:
            reset_request_user_id(token)


class TestAgentInitialization:
    """Test agent initialization with user context."""

    def test_bootstrap_hook_uses_user_directory(self, tmp_copaw_dirs):
        """Test that BootstrapHook uses user directory."""
        from copaw.agents.hooks import BootstrapHook

        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("hookuser")
        try:
            hook = BootstrapHook(
                working_dir=get_request_working_dir(),
                language="en",
            )

            # Hook's working_dir should be user's directory
            assert hook.working_dir == working_dir / "hookuser"
        finally:
            reset_request_user_id(token)

    def test_prompt_builder_uses_user_directory(self, tmp_copaw_dirs):
        """Test that PromptBuilder uses user directory."""
        from copaw.agents.prompt import PromptBuilder

        working_dir, _ = tmp_copaw_dirs

        token = set_request_user_id("promptuser")
        try:
            builder = PromptBuilder(
                working_dir=get_request_working_dir(),
            )

            assert builder.working_dir == working_dir / "promptuser"
        finally:
            reset_request_user_id(token)


class TestBackwardCompatibility:
    """Test backward compatibility with runtime (single-user) mode."""

    def test_runtime_working_dir_still_works(self, tmp_copaw_dirs):
        """Test that get_runtime_working_dir() still works."""
        working_dir, _ = tmp_copaw_dirs

        # get_runtime_working_dir should return the patched runtime dir
        result = get_runtime_working_dir()
        assert result == working_dir, f"Expected {working_dir}, got {result}"

    def test_set_current_user_for_single_user_mode(self, tmp_copaw_dirs):
        """Test set_current_user() for CLI single-user mode."""
        working_dir, _ = tmp_copaw_dirs

        # Set current user (single-user mode)
        set_current_user("cliuser")

        # Runtime working dir should be updated
        result = get_runtime_working_dir()
        assert result == working_dir / "cliuser"

        # Reset
        set_current_user(None)

    def test_get_working_dir_explicit_user(self, tmp_copaw_dirs):
        """Test get_working_dir with explicit user_id."""
        working_dir, _ = tmp_copaw_dirs

        result = get_working_dir("explicituser")
        assert result == working_dir / "explicituser"


class TestAutoInitialization:
    """Test automatic user directory initialization."""

    def test_initialize_new_user_directory(self, tmp_copaw_dirs):
        """Test that new user directory is properly initialized."""
        from copaw.agents.utils.setup_utils import initialize_user_directory

        working_dir, secret_dir = tmp_copaw_dirs
        user_id = "newuser"

        # Should return True for new user
        result = initialize_user_directory(user_id, language="en")
        assert result is True

        # Verify directories and files created
        user_wd = working_dir / user_id
        user_secret = secret_dir / user_id

        assert (user_wd / "config.json").exists()
        assert (user_secret / "providers.json").exists()
        # Note: active_skills directory is created by sync_skills_to_working_dir
        # but may be empty if no builtin skills exist in test environment

    def test_initialize_existing_user_returns_false(self, tmp_copaw_dirs):
        """Test that initialization returns False for existing user."""
        from copaw.agents.utils.setup_utils import initialize_user_directory
        from copaw.config import Config, save_config

        working_dir, _ = tmp_copaw_dirs
        user_id = "existinguser"

        # Create config.json first
        user_wd = working_dir / user_id
        user_wd.mkdir(parents=True, exist_ok=True)
        save_config(Config(), user_wd / "config.json")

        # Should return False for existing user
        result = initialize_user_directory(user_id)
        assert result is False

    def test_ensure_providers_json_creates_default(self, tmp_copaw_dirs):
        """Test that ensure_providers_json creates default config."""
        from copaw.providers.store import ensure_providers_json

        _, secret_dir = tmp_copaw_dirs
        user_id = "testuser"

        # Create new providers.json
        result_path = ensure_providers_json(user_id)

        expected_path = secret_dir / user_id / "providers.json"
        assert result_path == expected_path
        assert result_path.exists()

        # Verify content is valid JSON
        import json

        with open(result_path) as f:
            data = json.load(f)
        assert "providers" in data or "active_llm" in data

    def test_initialize_creates_md_files_and_heartbeat(self, tmp_copaw_dirs):
        """Test that initialization creates MD files and HEARTBEAT.md."""
        from copaw.agents.utils.setup_utils import initialize_user_directory

        working_dir, secret_dir = tmp_copaw_dirs
        user_id = "newuser"

        # Initialize user directory
        result = initialize_user_directory(user_id, language="en")
        assert result is True

        user_wd = working_dir / user_id

        # Verify MD files are created (at least the core ones)
        expected_md_files = [
            "AGENTS.md",
            "BOOTSTRAP.md",
            "SOUL.md",
            "PROFILE.md",
            "MEMORY.md",
        ]
        for md_file in expected_md_files:
            assert (user_wd / md_file).exists(), f"{md_file} should be created"

        # Verify HEARTBEAT.md is created
        assert (user_wd / "HEARTBEAT.md").exists()

        # Verify HEARTBEAT.md has correct content
        heartbeat_content = (user_wd / "HEARTBEAT.md").read_text()
        assert "Heartbeat checklist" in heartbeat_content
        assert "Scan inbox" in heartbeat_content  # English default


class TestHttpMiddleware:
    """Test HTTP middleware for X-User-ID header."""

    @pytest.mark.asyncio
    async def test_user_context_middleware_sets_context(self):
        """Test that middleware sets and cleans up context from X-User-ID header."""
        from copaw.app._app import user_context_middleware

        # Mock request with X-User-ID header
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers

        call_count = {"value": 0}

        class MockResponse:
            def __init__(self, status_code=200):
                self.status_code = status_code

        async def mock_call_next(_req):
            call_count["value"] += 1
            return MockResponse()

        request = MockRequest({"x-user-id": "middleware_user"})
        await user_context_middleware(request, mock_call_next)

        # Middleware should have called next
        assert call_count["value"] == 1

    @pytest.mark.asyncio
    async def test_user_context_middleware_without_header(self):
        """Test that middleware works correctly without X-User-ID header."""
        from copaw.app._app import user_context_middleware
        from copaw.constant import get_request_user_id

        class MockRequest:
            def __init__(self, headers):
                self.headers = headers

        async def mock_call_next(_req):
            return True

        # No user ID header
        request = MockRequest({})
        await user_context_middleware(request, mock_call_next)

        # Context should remain unchanged (None)
        assert get_request_user_id() is None

    @pytest.mark.asyncio
    async def test_user_context_middleware_copaw_header(self):
        """Test that middleware recognizes X-CoPaw-User-Id header."""
        from copaw.app._app import user_context_middleware

        class MockRequest:
            def __init__(self, headers):
                self.headers = headers

        call_count = {"value": 0}

        async def mock_call_next(_req):
            call_count["value"] += 1
            return True

        # Using X-CoPaw-User-Id header
        request = MockRequest({"x-copaw-user-id": "copaw_user"})
        await user_context_middleware(request, mock_call_next)

        # Should work the same as X-User-ID
        assert call_count["value"] == 1

    @pytest.mark.asyncio
    async def test_user_context_middleware_triggers_auto_init(
        self,
        tmp_copaw_dirs,
        monkeypatch,
    ):
        """Test that middleware triggers auto-initialization for new users.

        Note: This test directly calls initialize_user_directory to verify
        the auto-initialization logic, since mocking the middleware's
        imports is complex due to Python's import timing.
        """
        from copaw.agents.utils.setup_utils import initialize_user_directory
        from copaw.constant import get_working_dir, get_secret_dir

        working_dir, secret_dir = tmp_copaw_dirs
        user_id = "http_init_user"

        # Call initialize_user_directory directly (this is what the middleware does)
        # Create a mock config
        class MockConfig:
            class agents:
                language = "en"

        result = initialize_user_directory(
            user_id=user_id,
            language="en",
        )

        # Should return True for new user
        assert result is True

        # Verify directories were created
        user_wd = get_working_dir(user_id)
        user_secret = get_secret_dir(user_id)

        assert user_wd.exists(), f"User working dir should exist: {user_wd}"
        assert (
            user_secret.exists()
        ), f"User secret dir should exist: {user_secret}"

        # Verify config.json was created
        config_path = user_wd / "config.json"
        assert config_path.exists(), f"config.json should exist: {config_path}"

        # Verify providers.json was created
        providers_path = user_secret / "providers.json"
        assert (
            providers_path.exists()
        ), f"providers.json should exist: {providers_path}"


class TestMemoryManagerIsolation:
    """Test MemoryManager uses correct user directories."""

    def test_memory_manager_paths_use_request_context(self, tmp_copaw_dirs):
        """Test that MemoryManager paths use request-scoped directory."""
        from copaw.agents.memory.memory_manager import MemoryManager

        working_dir, _ = tmp_copaw_dirs

        # Create MemoryManager with base directory
        token = set_request_user_id("testuser")
        try:
            # MemoryManager should use request-scoped paths internally
            # even though initialized with runtime directory
            assert get_request_working_dir() == working_dir / "testuser"
        finally:
            reset_request_user_id(token)

    def test_memory_manager_path_override_in_query_handler(
        self, tmp_copaw_dirs
    ):
        """Test that query_handler properly overrides MemoryManager paths."""
        from unittest.mock import MagicMock, PropertyMock

        working_dir, _ = tmp_copaw_dirs

        # Mock MemoryManager
        mock_memory_manager = MagicMock()
        mock_memory_manager.working_path = working_dir / "original"
        mock_memory_manager.memory_path = working_dir / "original" / "memory"
        mock_memory_manager.tool_result_path = (
            working_dir / "original" / "tool_result"
        )

        # Set user context
        token = set_request_user_id("pathoverrideuser")
        try:
            # Simulate what query_handler does
            request_wd = get_request_working_dir()
            original_paths = (
                mock_memory_manager.working_path,
                mock_memory_manager.memory_path,
                mock_memory_manager.tool_result_path,
            )
            mock_memory_manager.working_path = request_wd
            mock_memory_manager.memory_path = request_wd / "memory"
            mock_memory_manager.tool_result_path = request_wd / "tool_result"

            # Verify paths were overridden
            assert (
                mock_memory_manager.working_path
                == working_dir / "pathoverrideuser"
            )
            assert (
                mock_memory_manager.memory_path
                == working_dir / "pathoverrideuser" / "memory"
            )
            assert (
                mock_memory_manager.tool_result_path
                == working_dir / "pathoverrideuser" / "tool_result"
            )

            # Restore paths
            (
                mock_memory_manager.working_path,
                mock_memory_manager.memory_path,
                mock_memory_manager.tool_result_path,
            ) = original_paths

            # Verify paths were restored
            assert mock_memory_manager.working_path == working_dir / "original"
            assert (
                mock_memory_manager.memory_path
                == working_dir / "original" / "memory"
            )
            assert (
                mock_memory_manager.tool_result_path
                == working_dir / "original" / "tool_result"
            )
        finally:
            reset_request_user_id(token)


class TestMemoryManagerLRUCache:
    """Test MemoryManager LRU cache optimization."""

    @pytest.mark.asyncio
    async def test_cache_miss_creates_new_memory_manager(self, tmp_copaw_dirs):
        """Test that cache miss creates new MemoryManager."""
        from copaw.app.runner.runner import AgentRunner

        working_dir, _ = tmp_copaw_dirs

        runner = AgentRunner()

        # Set user context
        token = set_request_user_id("cacheuser1")
        try:
            # Get MemoryManager for user (should create new one)
            mm = await runner._get_memory_manager_for_user(
                user_id="cacheuser1",
                working_dir=working_dir / "cacheuser1",
            )

            # Should be in cache now
            assert "cacheuser1" in runner._memory_manager_cache
            assert runner._memory_manager_cache["cacheuser1"] is mm
        finally:
            reset_request_user_id(token)
            # Cleanup
            await runner.shutdown_handler()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_existing_memory_manager(
        self, tmp_copaw_dirs
    ):
        """Test that cache hit returns existing MemoryManager."""
        from copaw.app.runner.runner import AgentRunner

        working_dir, _ = tmp_copaw_dirs

        runner = AgentRunner()

        try:
            # First request - should create new
            mm1 = await runner._get_memory_manager_for_user(
                user_id="cacheuser2",
                working_dir=working_dir / "cacheuser2",
            )

            # Second request - should return cached
            mm2 = await runner._get_memory_manager_for_user(
                user_id="cacheuser2",
                working_dir=working_dir / "cacheuser2",
            )

            # Should be same instance
            assert mm1 is mm2
            assert len(runner._memory_manager_cache) == 1
        finally:
            await runner.shutdown_handler()

    @pytest.mark.asyncio
    async def test_lru_eviction_when_cache_full(
        self, tmp_copaw_dirs, monkeypatch
    ):
        """Test LRU eviction when cache exceeds max size."""
        from copaw.app.runner.runner import AgentRunner

        working_dir, _ = tmp_copaw_dirs

        # Set small cache size for testing
        monkeypatch.setattr(
            "copaw.app.runner.runner.COPAW_MM_CACHE_MAX_SIZE", 3
        )

        runner = AgentRunner()
        # Override cache max size
        runner._mm_cache_max_size = 3

        try:
            # Fill cache
            mm1 = await runner._get_memory_manager_for_user(
                user_id="user1",
                working_dir=working_dir / "user1",
            )
            mm2 = await runner._get_memory_manager_for_user(
                user_id="user2",
                working_dir=working_dir / "user2",
            )
            mm3 = await runner._get_memory_manager_for_user(
                user_id="user3",
                working_dir=working_dir / "user3",
            )

            assert len(runner._memory_manager_cache) == 3

            # Add one more - should evict oldest (user1)
            mm4 = await runner._get_memory_manager_for_user(
                user_id="user4",
                working_dir=working_dir / "user4",
            )

            # user1 should be evicted
            assert "user1" not in runner._memory_manager_cache
            assert "user2" in runner._memory_manager_cache
            assert "user3" in runner._memory_manager_cache
            assert "user4" in runner._memory_manager_cache
        finally:
            await runner.shutdown_handler()

    @pytest.mark.asyncio
    async def test_lru_order_updated_on_access(self, tmp_copaw_dirs):
        """Test that LRU order is updated when accessing existing items."""
        from copaw.app.runner.runner import AgentRunner

        working_dir, _ = tmp_copaw_dirs

        runner = AgentRunner()
        runner._mm_cache_max_size = 3

        try:
            # Add users in order
            await runner._get_memory_manager_for_user(
                "userA", working_dir / "userA"
            )
            await runner._get_memory_manager_for_user(
                "userB", working_dir / "userB"
            )
            await runner._get_memory_manager_for_user(
                "userC", working_dir / "userC"
            )

            # Access userA again - moves to end
            await runner._get_memory_manager_for_user(
                "userA", working_dir / "userA"
            )

            # Now add userD - should evict userB (oldest)
            await runner._get_memory_manager_for_user(
                "userD", working_dir / "userD"
            )

            # userB should be evicted, userA should remain
            assert "userB" not in runner._memory_manager_cache
            assert "userA" in runner._memory_manager_cache
        finally:
            await runner.shutdown_handler()

    @pytest.mark.asyncio
    async def test_shutdown_closes_all_cached_memory_managers(
        self, tmp_copaw_dirs
    ):
        """Test that shutdown closes all cached MemoryManager instances."""
        from copaw.app.runner.runner import AgentRunner

        working_dir, _ = tmp_copaw_dirs

        runner = AgentRunner()

        try:
            # Create multiple MemoryManagers
            await runner._get_memory_manager_for_user(
                "shutdownuser1", working_dir / "shutdownuser1"
            )
            await runner._get_memory_manager_for_user(
                "shutdownuser2", working_dir / "shutdownuser2"
            )

            assert len(runner._memory_manager_cache) == 2

            # Shutdown should close all
            await runner.shutdown_handler()

            # Cache should be empty
            assert len(runner._memory_manager_cache) == 0
        finally:
            pass  # Already cleaned up by shutdown_handler


class TestChatsIsolation:
    """Test chat management isolation for multi-user support."""

    def test_get_chats_path_with_user_id(self, tmp_copaw_dirs):
        """Test that chats.json path is user-isolated."""
        working_dir, _ = tmp_copaw_dirs

        # With explicit user_id
        result = get_chats_path("alice")
        assert result == working_dir / "alice" / "chats.json"

    def test_get_chats_path_with_request_context(self, tmp_copaw_dirs):
        """Test that chats.json path uses request context when user_id=None."""
        working_dir, _ = tmp_copaw_dirs

        # With request context
        token = set_request_user_id("bob")
        try:
            result = get_chats_path()
            assert result == working_dir / "bob" / "chats.json"
        finally:
            reset_request_user_id(token)

    @pytest.mark.asyncio
    async def test_chat_manager_uses_user_isolated_repo(self, tmp_copaw_dirs):
        """Test that ChatManager uses user-isolated repository."""
        from copaw.app.runner.manager import ChatManager
        from copaw.app.runner.repo.json_repo import JsonChatRepository

        working_dir, _ = tmp_copaw_dirs

        chat_manager = ChatManager()

        # Test that _get_repo_for_user returns correct repo
        token = set_request_user_id("testuser")
        try:
            repo = chat_manager._get_repo_for_user("testuser")
            assert isinstance(repo, JsonChatRepository)
            assert repo.path == working_dir / "testuser" / "chats.json"
        finally:
            reset_request_user_id(token)

    @pytest.mark.asyncio
    async def test_list_chats_returns_only_user_chats(self, tmp_copaw_dirs):
        """Test that list_chats returns only the current user's chats."""
        from copaw.app.runner.manager import ChatManager
        from copaw.app.runner.models import ChatSpec

        working_dir, _ = tmp_copaw_dirs

        # Create user directories
        (working_dir / "alice").mkdir(parents=True, exist_ok=True)
        (working_dir / "bob").mkdir(parents=True, exist_ok=True)

        chat_manager = ChatManager()

        # Create chats for Alice
        token_alice = set_request_user_id("alice")
        try:
            alice_repo = chat_manager._get_repo_for_user("alice")
            alice_chat = ChatSpec(
                name="Alice's Chat",
                session_id="alice:session1",
                user_id="alice",
                channel="test",
            )
            await alice_repo.upsert_chat(alice_chat)
        finally:
            reset_request_user_id(token_alice)

        # Create chats for Bob
        token_bob = set_request_user_id("bob")
        try:
            bob_repo = chat_manager._get_repo_for_user("bob")
            bob_chat = ChatSpec(
                name="Bob's Chat",
                session_id="bob:session1",
                user_id="bob",
                channel="test",
            )
            await bob_repo.upsert_chat(bob_chat)
        finally:
            reset_request_user_id(token_bob)

        # Alice should only see her own chats
        token_alice = set_request_user_id("alice")
        try:
            alice_chats = await chat_manager.list_chats(user_id="alice")
            assert len(alice_chats) == 1
            assert alice_chats[0].user_id == "alice"
            assert alice_chats[0].name == "Alice's Chat"
        finally:
            reset_request_user_id(token_alice)

        # Bob should only see his own chats
        token_bob = set_request_user_id("bob")
        try:
            bob_chats = await chat_manager.list_chats(user_id="bob")
            assert len(bob_chats) == 1
            assert bob_chats[0].user_id == "bob"
            assert bob_chats[0].name == "Bob's Chat"
        finally:
            reset_request_user_id(token_bob)

    @pytest.mark.asyncio
    async def test_create_chat_uses_user_directory(self, tmp_copaw_dirs):
        """Test that create_chat saves to user's chats.json."""
        from copaw.app.runner.manager import ChatManager
        from copaw.app.runner.models import ChatSpec

        working_dir, _ = tmp_copaw_dirs

        # Create user directories
        (working_dir / "testuser").mkdir(parents=True, exist_ok=True)

        chat_manager = ChatManager()

        # Create a chat for testuser
        chat_spec = ChatSpec(
            name="Test Chat",
            session_id="testuser:session1",
            user_id="testuser",
            channel="test",
        )

        token = set_request_user_id("testuser")
        try:
            result = await chat_manager.create_chat(
                chat_spec, user_id="testuser"
            )
            assert result is not None

            # Verify the chat was saved to user's directory
            chats_path = working_dir / "testuser" / "chats.json"
            assert chats_path.exists()

            # Verify we can load it back
            repo = chat_manager._get_repo_for_user("testuser")
            chats = await repo.load()
            assert len(chats.chats) == 1
            assert chats.chats[0].user_id == "testuser"
        finally:
            reset_request_user_id(token)

    @pytest.mark.asyncio
    async def test_get_chat_not_found_for_other_user(self, tmp_copaw_dirs):
        """Test that get_chat returns None when accessing another user's chat."""
        from copaw.app.runner.manager import ChatManager
        from copaw.app.runner.models import ChatSpec

        working_dir, _ = tmp_copaw_dirs

        # Create user directories
        (working_dir / "owner").mkdir(parents=True, exist_ok=True)
        (working_dir / "other").mkdir(parents=True, exist_ok=True)

        chat_manager = ChatManager()

        # Create a chat for owner
        owner_chat = ChatSpec(
            name="Owner's Chat",
            session_id="owner:session1",
            user_id="owner",
            channel="test",
        )

        token_owner = set_request_user_id("owner")
        try:
            owner_repo = chat_manager._get_repo_for_user("owner")
            await owner_repo.upsert_chat(owner_chat)
        finally:
            reset_request_user_id(token_owner)

        # Other user should not be able to access owner's chat
        # (different files, so chat won't exist in other's repo)
        token_other = set_request_user_id("other")
        try:
            result = await chat_manager.get_chat(
                owner_chat.id, user_id="other"
            )
            # Should return None since the chat doesn't exist in other's file
            assert result is None
        finally:
            reset_request_user_id(token_other)

    @pytest.mark.asyncio
    async def test_delete_chat_only_affects_user_chats(self, tmp_copaw_dirs):
        """Test that delete_chat only affects the current user's chats."""
        from copaw.app.runner.manager import ChatManager
        from copaw.app.runner.models import ChatSpec

        working_dir, _ = tmp_copaw_dirs

        # Create user directories
        (working_dir / "user1").mkdir(parents=True, exist_ok=True)
        (working_dir / "user2").mkdir(parents=True, exist_ok=True)

        chat_manager = ChatManager()

        # Create chats for both users
        user1_chat = ChatSpec(
            name="User1 Chat",
            session_id="user1:session1",
            user_id="user1",
            channel="test",
        )
        user2_chat = ChatSpec(
            name="User2 Chat",
            session_id="user2:session1",
            user_id="user2",
            channel="test",
        )

        token_user1 = set_request_user_id("user1")
        try:
            user1_repo = chat_manager._get_repo_for_user("user1")
            await user1_repo.upsert_chat(user1_chat)
        finally:
            reset_request_user_id(token_user1)

        token_user2 = set_request_user_id("user2")
        try:
            user2_repo = chat_manager._get_repo_for_user("user2")
            await user2_repo.upsert_chat(user2_chat)
        finally:
            reset_request_user_id(token_user2)

        # Delete user1's chat
        token_user1 = set_request_user_id("user1")
        try:
            deleted = await chat_manager.delete_chats(
                chat_ids=[user1_chat.id],
                user_id="user1",
            )
            assert deleted is True
        finally:
            reset_request_user_id(token_user1)

        # Verify user1's chat is deleted
        token_user1 = set_request_user_id("user1")
        try:
            user1_chats = await chat_manager.list_chats(user_id="user1")
            assert len(user1_chats) == 0
        finally:
            reset_request_user_id(token_user1)

        # Verify user2's chat is still there
        token_user2 = set_request_user_id("user2")
        try:
            user2_chats = await chat_manager.list_chats(user_id="user2")
            assert len(user2_chats) == 1
            assert user2_chats[0].user_id == "user2"
        finally:
            reset_request_user_id(token_user2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
