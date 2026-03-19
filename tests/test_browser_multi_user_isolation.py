# -*- coding: utf-8 -*-
"""Tests for multi-user browser isolation in browser_control.py.

These tests verify that browser state is properly isolated between different users,
ensuring cookie/session data, localStorage, and page refs are not shared.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from copaw.constant import set_request_user_id, reset_request_user_id


# Import the module under test
# Note: We import the module to access internal functions for testing
import copaw.agents.tools.browser_control as browser_control


class TestMultiUserBrowserIsolation:
    """Test suite for multi-user browser isolation."""

    @pytest.fixture(autouse=True)
    def reset_browser_state(self):
        """Reset browser state before each test to ensure isolation."""
        # Store original state
        original_state = browser_control._state

        # Reset to clean state
        browser_control._state = {"users": {}}

        yield

        # Restore original state after test
        browser_control._state = original_state

    @pytest.fixture
    def mock_user_context(self):
        """Fixture to provide mock user context management."""
        tokens = []

        def _set_user(user_id: str):
            token = set_request_user_id(user_id)
            tokens.append(token)
            return token

        yield _set_user

        # Cleanup: reset all tokens
        for token in tokens:
            try:
                reset_request_user_id(token)
            except Exception:
                pass

    def test_get_current_user_id_default(self):
        """Test that default user ID is returned when no context is set."""
        user_id = browser_control._get_current_user_id()
        assert user_id == "default"

    def test_get_current_user_id_from_context(self, mock_user_context):
        """Test that user ID is retrieved from request context."""
        mock_user_context("user_123")
        user_id = browser_control._get_current_user_id()
        assert user_id == "user_123"

    def test_get_user_state_creates_new_state(self):
        """Test that _get_user_state creates new state for new user."""
        token = set_request_user_id("new_user")
        try:
            state = browser_control._get_user_state()
            assert isinstance(state, browser_control.UserBrowserState)
            assert "new_user" in browser_control._state["users"]
        finally:
            reset_request_user_id(token)

    def test_get_user_state_returns_existing_state(self):
        """Test that _get_user_state returns existing state for existing user."""
        token = set_request_user_id("existing_user")
        try:
            # First call creates state
            state1 = browser_control._get_user_state()
            state1.page_counter = 42

            # Second call should return same state
            state2 = browser_control._get_user_state()
            assert state2.page_counter == 42
            assert state1 is state2
        finally:
            reset_request_user_id(token)

    def test_user_state_isolation(self):
        """Test that different users have completely isolated state."""
        # Set up user A
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            state_a.page_counter = 10
            state_a.pages["page1"] = MagicMock()
        finally:
            reset_request_user_id(token_a)

        # Set up user B
        token_b = set_request_user_id("user_b")
        try:
            state_b = browser_control._get_user_state()
            state_b.page_counter = 20
            state_b.pages["page2"] = MagicMock()
        finally:
            reset_request_user_id(token_b)

        # Verify isolation: User A's state should not be affected
        token_a = set_request_user_id("user_a")
        try:
            state_a_check = browser_control._get_user_state()
            assert state_a_check.page_counter == 10
            assert "page1" in state_a_check.pages
            assert "page2" not in state_a_check.pages
        finally:
            reset_request_user_id(token_a)

        # Verify isolation: User B's state should not be affected
        token_b = set_request_user_id("user_b")
        try:
            state_b_check = browser_control._get_user_state()
            assert state_b_check.page_counter == 20
            assert "page2" in state_b_check.pages
            assert "page1" not in state_b_check.pages
        finally:
            reset_request_user_id(token_b)

    def test_get_page_with_user_isolation(self):
        """Test that _get_page returns correct page for specific user."""
        mock_page_a = MagicMock()
        mock_page_b = MagicMock()

        # Set up user A with a page
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            state_a.pages["test_page"] = mock_page_a
        finally:
            reset_request_user_id(token_a)

        # Set up user B with same page ID but different page
        token_b = set_request_user_id("user_b")
        try:
            state_b = browser_control._get_user_state()
            state_b.pages["test_page"] = mock_page_b
        finally:
            reset_request_user_id(token_b)

        # Verify each user gets their own page
        page_a = browser_control._get_page("test_page", user_id="user_a")
        page_b = browser_control._get_page("test_page", user_id="user_b")

        assert page_a is mock_page_a
        assert page_b is mock_page_b
        assert page_a is not page_b

    def test_get_refs_with_user_isolation(self):
        """Test that _get_refs returns correct refs for specific user."""
        # Set up user A with refs
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            state_a.refs["page1"] = {"ref1": {"role": "button"}}
        finally:
            reset_request_user_id(token_a)

        # Set up user B with different refs
        token_b = set_request_user_id("user_b")
        try:
            state_b = browser_control._get_user_state()
            state_b.refs["page1"] = {"ref2": {"role": "link"}}
        finally:
            reset_request_user_id(token_b)

        # Verify refs are isolated
        refs_a = browser_control._get_refs("page1", user_id="user_a")
        refs_b = browser_control._get_refs("page1", user_id="user_b")

        assert "ref1" in refs_a
        assert "ref2" not in refs_a
        assert "ref2" in refs_b
        assert "ref1" not in refs_b

    def test_is_browser_running_for_user(self):
        """Test _is_browser_running_for_user checks correct user's browser."""
        # Initially no browser running for any user
        assert browser_control._is_browser_running_for_user("user_a") is False
        assert browser_control._is_browser_running_for_user("user_b") is False

        # Simulate browser running for user A
        # Check if sync or async mode and set appropriate browser field
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            if browser_control._USE_SYNC_PLAYWRIGHT:
                state_a._sync_browser = MagicMock()
            else:
                state_a.browser = MagicMock()
        finally:
            reset_request_user_id(token_a)

        # User A should have running browser, User B should not
        assert browser_control._is_browser_running_for_user("user_a") is True
        assert browser_control._is_browser_running_for_user("user_b") is False

    def test_touch_activity_user(self):
        """Test _touch_activity_user updates correct user's timestamp."""
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            original_time = state_a.last_activity_time

            browser_control._touch_activity_user("user_a")

            assert state_a.last_activity_time > original_time
        finally:
            reset_request_user_id(token_a)

    def test_reset_browser_state_user(self):
        """Test _reset_browser_state_user clears only specified user's state."""
        # Set up two users with state
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            state_a.page_counter = 10
            state_a.pages["page1"] = MagicMock()
        finally:
            reset_request_user_id(token_a)

        token_b = set_request_user_id("user_b")
        try:
            state_b = browser_control._get_user_state()
            state_b.page_counter = 20
            state_b.pages["page2"] = MagicMock()
        finally:
            reset_request_user_id(token_b)

        # Reset only user A
        browser_control._reset_browser_state_user("user_a")

        # User A's state should be cleared
        state_a_after = browser_control._state["users"].get("user_a")
        assert state_a_after.page_counter == 0
        assert len(state_a_after.pages) == 0

        # User B's state should remain intact
        state_b_after = browser_control._state["users"].get("user_b")
        assert state_b_after.page_counter == 20
        assert "page2" in state_b_after.pages

    def test_multiple_users_concurrent_simulation(self):
        """Simulate concurrent access from multiple users."""
        users = ["alice", "bob", "charlie"]

        # Each user creates their own state
        tokens = []
        for user in users:
            token = set_request_user_id(user)
            tokens.append(token)
            state = browser_control._get_user_state()
            state.page_counter = ord(user[0])  # Unique value per user

        # Reset all tokens
        for token in tokens:
            reset_request_user_id(token)

        # Verify each user's state is isolated
        for user in users:
            token = set_request_user_id(user)
            try:
                state = browser_control._get_user_state()
                assert state.page_counter == ord(user[0])
            finally:
                reset_request_user_id(token)

    def test_max_pages_per_user_constant(self):
        """Test that max pages per user constant is defined."""
        assert hasattr(browser_control, "_MAX_PAGES_PER_USER")
        assert browser_control._MAX_PAGES_PER_USER == 10

    def test_user_browser_state_dataclass(self):
        """Test UserBrowserState dataclass has expected fields."""
        state = browser_control.UserBrowserState()

        # Check default values
        assert state.playwright is None
        assert state.browser is None
        assert state.context is None
        assert state.pages == {}
        assert state.refs == {}
        assert state.headless is True
        assert state.current_page_id is None
        assert state.page_counter == 0
        assert state.last_activity_time == 0.0


class TestUserContextHelpers:
    """Tests for user context helper functions."""

    def test_get_current_user_id_with_none_context(self):
        """Test default user ID when request context is None."""
        # Ensure no context is set
        token = set_request_user_id(None)
        try:
            user_id = browser_control._get_current_user_id()
            assert user_id == "default"
        finally:
            reset_request_user_id(token)

    def test_user_state_lifecycle(self):
        """Test complete lifecycle of user state: create -> use -> cleanup."""
        # Create state for user
        token = set_request_user_id("lifecycle_user")
        try:
            state = browser_control._get_user_state()
            assert state is not None

            # Modify state
            state.headless = False
            state.page_counter = 5

            # Retrieve same state
            state2 = browser_control._get_user_state()
            assert state2.headless is False
            assert state2.page_counter == 5
        finally:
            reset_request_user_id(token)

        # State should still exist in global storage
        assert "lifecycle_user" in browser_control._state["users"]

        # Cleanup
        browser_control._reset_browser_state_user("lifecycle_user")
        cleaned_state = browser_control._state["users"]["lifecycle_user"]
        assert cleaned_state.page_counter == 0
        assert cleaned_state.headless is True


@pytest.mark.asyncio
class TestBrowserUseUserIsolation:
    """Async tests for browser_use function with user isolation."""

    @pytest.fixture(autouse=True)
    def reset_browser_state(self):
        """Reset browser state before each test."""
        original_state = browser_control._state
        browser_control._state = {"users": {}}
        yield
        browser_control._state = original_state

    @pytest.mark.asyncio
    async def test_browser_use_requires_action(self):
        """Test browser_use returns error when no action provided."""
        token = set_request_user_id("test_user")
        try:
            response = await browser_control.browser_use(action="")
            assert response is not None
            # ToolResponse content is a list
            if hasattr(response, "content") and isinstance(
                response.content, list
            ):
                # Content may be TextBlock objects or dicts
                item = response.content[0] if response.content else {}
                if isinstance(item, dict):
                    content_text = item.get("text", str(item))
                else:
                    content_text = (
                        item.text if hasattr(item, "text") else str(item)
                    )
            else:
                content_text = str(response)
            assert (
                "action required" in content_text.lower()
                or "error" in content_text.lower()
            )
        finally:
            reset_request_user_id(token)

    @pytest.mark.asyncio
    async def test_browser_use_unknown_action(self):
        """Test browser_use handles unknown action."""
        token = set_request_user_id("test_user")
        try:
            response = await browser_control.browser_use(
                action="unknown_action_xyz"
            )
            # ToolResponse content is a list
            if hasattr(response, "content") and isinstance(
                response.content, list
            ):
                # Content may be TextBlock objects or dicts
                item = response.content[0] if response.content else {}
                if isinstance(item, dict):
                    content_text = item.get("text", str(item))
                else:
                    content_text = (
                        item.text if hasattr(item, "text") else str(item)
                    )
            else:
                content_text = str(response)
            assert "unknown action" in content_text.lower()
        finally:
            reset_request_user_id(token)

    @pytest.mark.asyncio
    async def test_browser_use_install_action(self):
        """Test browser_use with install action (no browser needed)."""
        token = set_request_user_id("test_user")
        try:
            with patch.object(
                browser_control, "_action_install", new_callable=AsyncMock
            ) as mock_install:
                mock_install.return_value = MagicMock(content='{"ok": true}')
                response = await browser_control.browser_use(action="install")
                mock_install.assert_called_once()
        finally:
            reset_request_user_id(token)


class TestBrowserIsolationIntegration:
    """Integration tests simulating real-world multi-user browser scenarios."""

    @pytest.fixture(autouse=True)
    def reset_browser_state(self):
        """Reset browser state before each test."""
        original_state = browser_control._state
        browser_control._state = {"users": {}}
        yield
        browser_control._state = original_state

    def test_concurrent_user_page_creation(self):
        """Test that multiple users can create pages with same IDs without conflict."""
        users = ["alice", "bob", "charlie"]
        page_id = "shared_page_id"

        # Each user creates a page with the same ID
        for user in users:
            token = set_request_user_id(user)
            try:
                state = browser_control._get_user_state()
                mock_page = MagicMock()
                mock_page.url = f"https://{user}.example.com"
                state.pages[page_id] = mock_page
                state.page_counter += 1
            finally:
                reset_request_user_id(token)

        # Verify each user's page is isolated
        for user in users:
            page = browser_control._get_page(page_id, user_id=user)
            assert page is not None
            assert page.url == f"https://{user}.example.com"

    def test_user_refs_isolation_with_same_ref_ids(self):
        """Test that refs with same IDs don't conflict between users."""
        ref_id = "button_1"
        page_id = "main_page"

        # User A creates a ref
        token_a = set_request_user_id("user_a")
        try:
            state_a = browser_control._get_user_state()
            state_a.refs[page_id] = {
                ref_id: {"role": "button", "name": "Submit for User A"},
            }
        finally:
            reset_request_user_id(token_a)

        # User B creates a ref with same ID
        token_b = set_request_user_id("user_b")
        try:
            state_b = browser_control._get_user_state()
            state_b.refs[page_id] = {
                ref_id: {"role": "button", "name": "Submit for User B"},
            }
        finally:
            reset_request_user_id(token_b)

        # Verify refs are isolated
        refs_a = browser_control._get_refs(page_id, user_id="user_a")
        refs_b = browser_control._get_refs(page_id, user_id="user_b")

        assert refs_a[ref_id]["name"] == "Submit for User A"
        assert refs_b[ref_id]["name"] == "Submit for User B"

    def test_user_cleanup_does_not_affect_others(self):
        """Test that cleaning up one user doesn't affect others."""
        # Setup users
        for user in ["user_x", "user_y", "user_z"]:
            token = set_request_user_id(user)
            try:
                state = browser_control._get_user_state()
                state.page_counter = ord(user[-1])  # Unique counter per user
            finally:
                reset_request_user_id(token)

        # Reset only user_y
        browser_control._reset_browser_state_user("user_y")

        # Verify user_x and user_z are unaffected
        token_x = set_request_user_id("user_x")
        try:
            state_x = browser_control._get_user_state()
            assert state_x.page_counter == ord("x")
        finally:
            reset_request_user_id(token_x)

        token_z = set_request_user_id("user_z")
        try:
            state_z = browser_control._get_user_state()
            assert state_z.page_counter == ord("z")
        finally:
            reset_request_user_id(token_z)

        # Verify user_y was reset
        token_y = set_request_user_id("user_y")
        try:
            state_y = browser_control._get_user_state()
            assert state_y.page_counter == 0
        finally:
            reset_request_user_id(token_y)

    def test_request_context_switching(self):
        """Test that request context switching correctly isolates users."""
        # Simulate request 1 for user_1
        token1 = set_request_user_id("user_1")
        state1 = browser_control._get_user_state()
        state1.headless = False
        reset_request_user_id(token1)

        # Simulate request 2 for user_2
        token2 = set_request_user_id("user_2")
        state2 = browser_control._get_user_state()
        state2.headless = True
        reset_request_user_id(token2)

        # Switch back to user_1
        token1 = set_request_user_id("user_1")
        current_state = browser_control._get_user_state()
        assert current_state.headless is False
        reset_request_user_id(token1)

        # Switch to user_2 again
        token2 = set_request_user_id("user_2")
        current_state = browser_control._get_user_state()
        assert current_state.headless is True
        reset_request_user_id(token2)
