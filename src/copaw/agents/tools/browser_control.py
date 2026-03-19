# -*- coding: utf-8 -*-
# flake8: noqa: E501
"""Browser automation tool using Playwright.

Single tool with action-based API matching browser MCP: start, stop, open,
navigate, navigate_back, screenshot, snapshot, click, type, eval, evaluate,
resize, console_messages, handle_dialog, file_upload, fill_form, install,
press_key, network_requests, run_code, drag, hover, select_option, tabs,
wait_for, pdf, close. Uses refs from snapshot for ref-based actions.
"""

import asyncio
import atexit
import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...config import (
    get_playwright_chromium_executable_path,
    get_system_default_browser,
    is_running_in_container,
)

from ...constant import get_request_user_id

from .browser_snapshot import build_role_snapshot_from_aria

logger = logging.getLogger(__name__)

# Hybrid mode detection: Windows + Uvicorn reload mode requires sync Playwright
# to avoid NotImplementedError with asyncio.create_subprocess_exec.
# On other platforms or without reload, use async Playwright for better performance.
_USE_SYNC_PLAYWRIGHT = (
    sys.platform == "win32" and os.environ.get("COPAW_RELOAD_MODE") == "1"
)

if _USE_SYNC_PLAYWRIGHT:
    _executor: Optional[ThreadPoolExecutor] = None

    def _get_executor() -> ThreadPoolExecutor:
        global _executor
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="playwright",
            )
        return _executor

    async def _run_sync(func, *args, **kwargs):
        """Run a sync function in the thread pool and await the result."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _get_executor(),
            lambda: func(*args, **kwargs),
        )

else:

    async def _run_sync(func, *args, **kwargs):
        """Fallback: directly call async function (should not be used in async mode)."""
        return await func(*args, **kwargs)


@dataclass
class UserBrowserState:
    """Per-user browser state for complete isolation between users.

    Each user gets their own browser instance, context, and pages.
    This ensures cookie/session data, localStorage, and caches are isolated.
    """

    playwright: Any = None
    browser: Any = None
    context: Any = None
    pages: dict = field(default_factory=dict)
    refs: dict = field(default_factory=dict)
    refs_frame: dict = field(default_factory=dict)
    console_logs: dict = field(default_factory=dict)
    network_requests: dict = field(default_factory=dict)
    pending_dialogs: dict = field(default_factory=dict)
    pending_file_choosers: dict = field(default_factory=dict)
    headless: bool = True
    current_page_id: str | None = None
    page_counter: int = 0
    last_activity_time: float = 0.0
    _idle_task: Any = None
    _last_browser_error: str | None = None
    # Sync mode handles
    _sync_playwright: Any = None
    _sync_browser: Any = None
    _sync_context: Any = None
    _sync_headless: bool = True


# Maximum pages per user to prevent resource exhaustion
_MAX_PAGES_PER_USER = 10

# Global state: user_id -> UserBrowserState
_state: dict[str, Any] = {"users": {}}

# Stop the browser after this many seconds of inactivity (default 30 minutes).
_BROWSER_IDLE_TIMEOUT = 1800.0


def _get_current_user_id() -> str:
    """Get the current user ID from request context or return 'default'."""
    return get_request_user_id() or "default"


def _get_user_state() -> UserBrowserState:
    """Get or create browser state for the current user."""
    user_id = _get_current_user_id()
    if user_id not in _state["users"]:
        _state["users"][user_id] = UserBrowserState()
    return _state["users"][user_id]


def _is_browser_running_for_user(user_id: str | None = None) -> bool:
    """Check if browser is running for a specific user (or current user)."""
    if user_id is None:
        user_id = _get_current_user_id()
    user_state = _state["users"].get(user_id)
    if not user_state:
        return False
    if _USE_SYNC_PLAYWRIGHT:
        return user_state._sync_browser is not None
    return user_state.browser is not None


def _touch_activity_user(user_id: str | None = None) -> None:
    """Record activity timestamp for a specific user (or current user)."""
    if user_id is None:
        user_state = _get_user_state()
    else:
        user_state = _state["users"].get(user_id)
    if user_state:
        user_state.last_activity_time = time.monotonic()


def _reset_browser_state_user(user_id: str | None = None) -> None:
    """Reset browser state for a specific user (or current user)."""
    if user_id is None:
        user_id = _get_current_user_id()
    user_state = _state["users"].get(user_id)
    if not user_state:
        return

    # Clear sync/async specific state
    user_state.playwright = None
    user_state.browser = None
    user_state.context = None
    user_state._sync_playwright = None
    user_state._sync_browser = None
    user_state._sync_context = None

    # Clear shared state
    user_state.pages.clear()
    user_state.refs.clear()
    user_state.refs_frame.clear()
    user_state.console_logs.clear()
    user_state.network_requests.clear()
    user_state.pending_dialogs.clear()
    user_state.pending_file_choosers.clear()
    user_state.current_page_id = None
    user_state.page_counter = 0
    user_state.last_activity_time = 0.0
    user_state.headless = True
    user_state._idle_task = None
    user_state._last_browser_error = None


def _get_page(page_id: str, user_id: str | None = None) -> Any:
    """Return page for page_id or None if not found."""
    if user_id is None:
        user_state = _get_user_state()
    else:
        user_state = _state["users"].get(user_id)
    if not user_state:
        return None
    return user_state.pages.get(page_id)


def _get_refs(page_id: str, user_id: str | None = None) -> dict[str, dict]:
    """Return refs map for page_id (ref -> {role, name?, nth?})."""
    if user_id is None:
        user_state = _get_user_state()
    else:
        user_state = _state["users"].get(user_id)
    if not user_state:
        return {}
    return user_state.refs.setdefault(page_id, {})


async def _idle_watchdog_user(
    user_id: str,
    idle_seconds: float = _BROWSER_IDLE_TIMEOUT,
) -> None:
    """Background task: stop the browser for a specific user after idle period.

    Each user has their own watchdog that monitors only their browser activity.
    """
    try:
        while True:
            await asyncio.sleep(60)  # check every minute
            user_state = _state["users"].get(user_id)
            if not user_state:
                return  # User state cleaned up
            if not _is_browser_running_for_user(user_id):
                return  # Browser already stopped
            idle = time.monotonic() - user_state.last_activity_time
            if idle >= idle_seconds:
                logger.info(
                    "User %s browser idle for %.0fs (limit %.0fs), stopping to release resources",
                    user_id,
                    idle,
                    idle_seconds,
                )
                await _action_stop_user(user_id)
                return
    except asyncio.CancelledError:
        pass


def _start_idle_watchdog_user(user_id: str | None = None) -> None:
    """Start idle watchdog for a specific user (or current user)."""
    if user_id is None:
        user_id = _get_current_user_id()
    user_state = _state["users"].get(user_id)
    if not user_state:
        return

    # Cancel any existing watchdog for this user
    old_task = user_state._idle_task
    if old_task and not old_task.done():
        old_task.cancel()

    # Start new watchdog
    user_state._idle_task = asyncio.ensure_future(_idle_watchdog_user(user_id))


def _cancel_idle_watchdog_user(user_id: str | None = None) -> None:
    """Cancel the idle watchdog for a specific user (or current user)."""
    if user_id is None:
        user_id = _get_current_user_id()
    user_state = _state["users"].get(user_id)
    if not user_state:
        return
    task = user_state._idle_task
    if task and not task.done():
        task.cancel()
    user_state._idle_task = None


async def _cleanup_all_user_browsers() -> None:
    """Clean up all user browsers on shutdown."""
    user_ids = list(_state["users"].keys())
    for user_id in user_ids:
        try:
            await _action_stop_user(user_id)
        except Exception:
            pass


def _atexit_cleanup() -> None:
    """Best-effort browser cleanup registered with :func:`atexit`.

    Playwright child processes are cleaned up by the OS when the parent
    exits, but this gives Playwright a chance to flush any pending I/O and
    close Chrome gracefully before the process disappears.
    """
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running() and not loop.is_closed():
            loop.run_until_complete(_cleanup_all_user_browsers())
    except Exception:
        pass


atexit.register(_atexit_cleanup)


def _tool_response(text: str) -> ToolResponse:
    """Wrap text for agentscope Toolkit (return ToolResponse)."""
    return ToolResponse(
        content=[TextBlock(type="text", text=text)],
    )


def _chromium_launch_args() -> list[str]:
    """Extra args for Chromium when running in container."""
    if is_running_in_container():
        return ["--no-sandbox", "--disable-dev-shm-usage"]
    return []


def _chromium_executable_path() -> str | None:
    """Chromium executable path when set (e.g. container); else None."""
    return get_playwright_chromium_executable_path()


def _use_webkit_fallback() -> bool:
    """True only on macOS when no system Chrome/Edge/Chromium found.
    Use WebKit (Safari) to avoid downloading Chromium. Windows has no system
    WebKit, so we never use webkit there.
    """
    return sys.platform == "darwin" and _chromium_executable_path() is None


def _ensure_playwright_async():
    """Import async_playwright; raise ImportError with hint if missing."""
    try:
        from playwright.async_api import async_playwright

        return async_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright not installed. Use the same Python that runs CoPaw (e.g. "
            "activate your venv or use 'uv run'): "
            f"'{sys.executable}' -m pip install playwright && "
            f"'{sys.executable}' -m playwright install",
        ) from exc


def _ensure_playwright_sync():
    """Import sync_playwright; raise ImportError with hint if missing."""
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright not installed. Use the same Python that runs CoPaw (e.g. "
            "activate your venv or use 'uv run'): "
            f"'{sys.executable}' -m pip install playwright && "
            f"'{sys.executable}' -m playwright install",
        ) from exc


def _sync_browser_launch(headless: bool):
    """Launch browser using sync Playwright (for hybrid mode)."""
    sync_playwright = _ensure_playwright_sync()
    pw = sync_playwright().start()  # Start without context manager
    use_default = not is_running_in_container() and os.environ.get(
        "COPAW_BROWSER_USE_DEFAULT",
        "1",
    ).strip().lower() in ("1", "true", "yes")
    default_kind, default_path = (
        get_system_default_browser() if use_default else (None, None)
    )
    exe: Optional[str] = None
    if default_kind == "chromium" and default_path:
        exe = default_path
    elif default_kind != "webkit":
        exe = _chromium_executable_path()

    if exe:
        launch_kwargs = {"headless": headless}
        extra_args = _chromium_launch_args()
        if extra_args:
            launch_kwargs["args"] = extra_args
        launch_kwargs["executable_path"] = exe
        browser = pw.chromium.launch(**launch_kwargs)
    elif default_kind == "webkit" or sys.platform == "darwin":
        browser = pw.webkit.launch(headless=headless)
    else:
        launch_kwargs = {"headless": headless}
        extra_args = _chromium_launch_args()
        if extra_args:
            launch_kwargs["args"] = extra_args
        browser = pw.chromium.launch(**launch_kwargs)

    context = browser.new_context()
    _attach_context_listeners(context)
    return pw, browser, context


def _sync_browser_close_user(user_state: UserBrowserState) -> None:
    """Close browser for a specific user using sync Playwright (for hybrid mode)."""
    if user_state._sync_browser is not None:
        try:
            user_state._sync_browser.close()
        except Exception:
            pass
    if user_state._sync_playwright is not None:
        try:
            user_state._sync_playwright.stop()
        except Exception:
            pass


def _parse_json_param(value: str, default: Any = None):
    """Parse optional JSON string param (e.g. fields, paths, values)."""
    if not value or not isinstance(value, str):
        return default
    value = value.strip()
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if "," in value:
            return [x.strip() for x in value.split(",")]
        return default


async def browser_use(  # pylint: disable=R0911,R0912
    action: str,
    url: str = "",
    page_id: str = "default",
    selector: str = "",
    text: str = "",
    code: str = "",
    path: str = "",
    wait: int = 0,
    full_page: bool = False,
    width: int = 0,
    height: int = 0,
    level: str = "info",
    filename: str = "",
    accept: bool = True,
    prompt_text: str = "",
    ref: str = "",
    element: str = "",
    paths_json: str = "",
    fields_json: str = "",
    key: str = "",
    submit: bool = False,
    slowly: bool = False,
    include_static: bool = False,
    screenshot_type: str = "png",
    snapshot_filename: str = "",
    double_click: bool = False,
    button: str = "left",
    modifiers_json: str = "",
    start_ref: str = "",
    end_ref: str = "",
    start_selector: str = "",
    end_selector: str = "",
    start_element: str = "",
    end_element: str = "",
    values_json: str = "",
    tab_action: str = "",
    index: int = -1,
    wait_time: float = 0,
    text_gone: str = "",
    frame_selector: str = "",
    headed: bool = False,
) -> ToolResponse:
    """Control browser (Playwright). Default is headless. Use headed=True with
    action=start to open a visible browser window. Flow: start, open(url),
    snapshot to get refs, then click/type etc. with ref or selector. Use
    page_id for multiple tabs.

    Args:
        action (str):
            Required. Action type. Values: start, stop, open, navigate,
            navigate_back, snapshot, screenshot, click, type, eval, evaluate,
            resize, console_messages, network_requests, handle_dialog,
            file_upload, fill_form, install, press_key, run_code, drag, hover,
            select_option, tabs, wait_for, pdf, close.
        url (str):
            URL to open. Required for action=open or navigate.
        page_id (str):
            Page/tab identifier, default "default". Use different page_id for
            multiple tabs.
        selector (str):
            CSS selector to locate element for click/type/hover etc. Prefer
            ref when available.
        text (str):
            Text to type. Required for action=type.
        code (str):
            JavaScript code. Required for action=eval, evaluate, or run_code.
        path (str):
            File path for screenshot save or PDF export.
        wait (int):
            Milliseconds to wait after click. Used with action=click.
        full_page (bool):
            Whether to capture full page. Used with action=screenshot.
        width (int):
            Viewport width in pixels. Used with action=resize.
        height (int):
            Viewport height in pixels. Used with action=resize.
        level (str):
            Console log level filter, e.g. "info" or "error". Used with
            action=console_messages.
        filename (str):
            Filename for saving logs or screenshot. Used with
            console_messages, network_requests, screenshot.
        accept (bool):
            Whether to accept dialog (true) or dismiss (false). Used with
            action=handle_dialog.
        prompt_text (str):
            Input for prompt dialog. Used with action=handle_dialog when
            dialog is prompt.
        ref (str):
            Element ref from snapshot output; use for stable targeting. Prefer
            ref for click/type/hover/screenshot/evaluate/select_option.
        element (str):
            Element description for evaluate etc. Prefer ref when available.
        paths_json (str):
            JSON array string of file paths. Used with action=file_upload.
        fields_json (str):
            JSON object string of form field name to value. Used with
            action=fill_form.
        key (str):
            Key name, e.g. "Enter", "Control+a". Required for
            action=press_key.
        submit (bool):
            Whether to submit (press Enter) after typing. Used with
            action=type.
        slowly (bool):
            Whether to type character by character. Used with action=type.
        include_static (bool):
            Whether to include static resource requests. Used with
            action=network_requests.
        screenshot_type (str):
            Screenshot format, "png" or "jpeg". Used with action=screenshot.
        snapshot_filename (str):
            File path to save snapshot output. Used with action=snapshot.
        double_click (bool):
            Whether to double-click. Used with action=click.
        button (str):
            Mouse button: "left", "right", or "middle". Used with
            action=click.
        modifiers_json (str):
            JSON array of modifier keys, e.g. ["Shift","Control"]. Used with
            action=click.
        start_ref (str):
            Drag start element ref. Used with action=drag.
        end_ref (str):
            Drag end element ref. Used with action=drag.
        start_selector (str):
            Drag start CSS selector. Used with action=drag.
        end_selector (str):
            Drag end CSS selector. Used with action=drag.
        start_element (str):
            Drag start element description. Used with action=drag.
        end_element (str):
            Drag end element description. Used with action=drag.
        values_json (str):
            JSON of option value(s) for select. Used with
            action=select_option.
        tab_action (str):
            Tab action: list, new, close, or select. Required for
            action=tabs.
        index (int):
            Tab index for tabs select, zero-based. Used with action=tabs.
        wait_time (float):
            Seconds to wait. Used with action=wait_for.
        text_gone (str):
            Wait until this text disappears from page. Used with
            action=wait_for.
        frame_selector (str):
            iframe selector, e.g. "iframe#main". Set when operating inside
            that iframe in snapshot/click/type etc.
        headed (bool):
            When True with action=start, launch a visible browser window
            (non-headless). User can see the real browser. Default False.
    """
    action = (action or "").strip().lower()
    if not action:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "action required"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    # Get current user state for this request
    user_id = _get_current_user_id()
    user_state = _get_user_state()

    page_id = (page_id or "default").strip() or "default"
    current = user_state.current_page_id
    pages = user_state.pages
    if page_id == "default" and current and current in pages:
        page_id = current

    try:
        if action == "start":
            return await _action_start_user(user_id=user_id, headed=headed)
        if action == "stop":
            return await _action_stop_user(user_id=user_id)
        if action == "open":
            return await _action_open(url, page_id, user_id=user_id)
        if action == "navigate":
            return await _action_navigate(url, page_id, user_id=user_id)
        if action == "navigate_back":
            return await _action_navigate_back(page_id, user_id=user_id)
        if action in ("screenshot", "take_screenshot"):
            return await _action_screenshot(
                page_id,
                path or filename,
                full_page,
                screenshot_type,
                ref,
                element,
                frame_selector,
                user_id=user_id,
            )
        if action == "snapshot":
            return await _action_snapshot(
                page_id,
                snapshot_filename or filename,
                frame_selector,
                user_id=user_id,
            )
        if action == "click":
            return await _action_click(
                page_id,
                selector,
                ref,
                element,
                wait,
                double_click,
                button,
                modifiers_json,
                frame_selector,
                user_id=user_id,
            )
        if action == "type":
            return await _action_type(
                page_id,
                selector,
                ref,
                element,
                text,
                submit,
                slowly,
                frame_selector,
                user_id=user_id,
            )
        if action == "eval":
            return await _action_eval(page_id, code, user_id=user_id)
        if action == "evaluate":
            return await _action_evaluate(
                page_id,
                code,
                ref,
                element,
                frame_selector,
                user_id=user_id,
            )
        if action == "resize":
            return await _action_resize(
                page_id,
                width,
                height,
                user_id=user_id,
            )
        if action == "console_messages":
            return await _action_console_messages(
                page_id,
                level,
                filename or path,
                user_id=user_id,
            )
        if action == "handle_dialog":
            return await _action_handle_dialog(
                page_id,
                accept,
                prompt_text,
                user_id=user_id,
            )
        if action == "file_upload":
            return await _action_file_upload(
                page_id,
                paths_json,
                user_id=user_id,
            )
        if action == "fill_form":
            return await _action_fill_form(
                page_id,
                fields_json,
                user_id=user_id,
            )
        if action == "install":
            return await _action_install()
        if action == "press_key":
            return await _action_press_key(page_id, key, user_id=user_id)
        if action == "network_requests":
            return await _action_network_requests(
                page_id,
                include_static,
                filename or path,
                user_id=user_id,
            )
        if action == "run_code":
            return await _action_run_code(page_id, code, user_id=user_id)
        if action == "drag":
            return await _action_drag(
                page_id,
                start_ref,
                end_ref,
                start_selector,
                end_selector,
                start_element,
                end_element,
                frame_selector,
                user_id=user_id,
            )
        if action == "hover":
            return await _action_hover(
                page_id,
                ref,
                element,
                selector,
                frame_selector,
                user_id=user_id,
            )
        if action == "select_option":
            return await _action_select_option(
                page_id,
                ref,
                element,
                values_json,
                frame_selector,
                user_id=user_id,
            )
        if action == "tabs":
            return await _action_tabs(
                page_id,
                tab_action,
                index,
                user_id=user_id,
            )
        if action == "wait_for":
            return await _action_wait_for(
                page_id,
                wait_time,
                text,
                text_gone,
                user_id=user_id,
            )
        if action == "pdf":
            return await _action_pdf(page_id, path, user_id=user_id)
        if action == "close":
            return await _action_close(page_id, user_id=user_id)
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Unknown action: {action}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        logger.error("Browser tool error: %s", e, exc_info=True)
        return _tool_response(
            json.dumps(
                {"ok": False, "error": str(e)},
                ensure_ascii=False,
                indent=2,
            ),
        )


def _get_root(page, _page_id: str, frame_selector: str = ""):
    """Return page or frame for frame_selector (ref/selector)."""
    if not (frame_selector and frame_selector.strip()):
        return page
    return page.frame_locator(frame_selector.strip())


def _get_locator_by_ref(
    page,
    page_id: str,
    ref: str,
    frame_selector: str = "",
    user_id: str | None = None,
):
    """Resolve snapshot ref to locator; frame_selector for iframe."""
    refs = _get_refs(page_id, user_id)
    info = refs.get(ref)
    if not info:
        return None
    role = info.get("role", "generic")
    name = info.get("name")
    nth = info.get("nth", 0)
    root = _get_root(page, page_id, frame_selector)
    locator = root.get_by_role(role, name=name or None)
    if nth is not None and nth > 0:
        locator = locator.nth(nth)
    return locator


def _attach_page_listeners(
    page,
    page_id: str,
    user_state: UserBrowserState,
) -> None:
    """Attach console and request listeners for a page."""
    logs = user_state.console_logs.setdefault(page_id, [])

    def on_console(msg):
        logs.append({"level": msg.type, "text": msg.text})

    page.on("console", on_console)
    requests_list = user_state.network_requests.setdefault(page_id, [])

    def on_request(req):
        requests_list.append(
            {
                "url": req.url,
                "method": req.method,
                "resourceType": getattr(req, "resource_type", None),
            },
        )

    def on_response(res):
        for r in requests_list:
            if r.get("url") == res.url and "status" not in r:
                r["status"] = res.status
                break

    page.on("request", on_request)
    page.on("response", on_response)
    dialogs = user_state.pending_dialogs.setdefault(page_id, [])

    def on_dialog(dialog):
        dialogs.append(dialog)

    page.on("dialog", on_dialog)
    choosers = user_state.pending_file_choosers.setdefault(page_id, [])

    def on_filechooser(chooser):
        choosers.append(chooser)

    page.on("filechooser", on_filechooser)


def _next_page_id(user_state: UserBrowserState) -> str:
    """Return a unique page_id (page_N) for the user.
    Uses monotonic counter so IDs are not reused after close."""
    user_state.page_counter += 1
    return f"page_{user_state.page_counter}"


def _attach_context_listeners(context, user_state: UserBrowserState) -> None:
    """When the page opens a new tab (e.g. target=_blank, window.open),
    register it and set as current."""

    def on_page(page):
        new_id = _next_page_id(user_state)
        user_state.refs[new_id] = {}
        user_state.console_logs[new_id] = []
        user_state.network_requests[new_id] = []
        user_state.pending_dialogs[new_id] = []
        user_state.pending_file_choosers[new_id] = []
        _attach_page_listeners(page, new_id, user_state)
        user_state.pages[new_id] = page
        user_state.current_page_id = new_id
        logger.debug(
            "New tab opened by page, registered as page_id=%s for user",
            new_id,
        )

    context.on("page", on_page)


async def _ensure_browser_for_user(
    user_id: str | None = None,
) -> bool:  # pylint: disable=too-many-branches
    """Start browser for a specific user if not running. Return True if ready."""
    if user_id is None:
        user_id = _get_current_user_id()

    user_state = _state["users"].get(user_id)
    if not user_state:
        user_state = UserBrowserState()
        _state["users"][user_id] = user_state

    # Check browser state based on mode
    if _USE_SYNC_PLAYWRIGHT:
        if (
            user_state._sync_browser is not None
            and user_state._sync_context is not None
        ):
            _touch_activity_user(user_id)
            return True
    else:
        if user_state.browser is not None and user_state.context is not None:
            _touch_activity_user(user_id)
            return True

    try:
        if _USE_SYNC_PLAYWRIGHT:
            # Hybrid mode: use sync Playwright in thread pool
            loop = asyncio.get_event_loop()
            pw, browser, context = await loop.run_in_executor(
                _get_executor(),
                lambda: _sync_browser_launch(user_state.headless),
            )
            user_state._sync_playwright = pw
            user_state._sync_browser = browser
            user_state._sync_context = context
        else:
            # Standard mode: use async Playwright
            async_playwright = _ensure_playwright_async()
            pw = await async_playwright().start()
            # Prefer OS default browser when available (e.g. user's default Chrome/Safari).
            use_default = not is_running_in_container() and os.environ.get(
                "COPAW_BROWSER_USE_DEFAULT",
                "1",
            ).strip().lower() in ("1", "true", "yes")
            default_kind, default_path = (
                get_system_default_browser() if use_default else (None, None)
            )
            exe: Optional[str] = None
            if default_kind == "chromium" and default_path:
                exe = default_path
            elif default_kind != "webkit":
                exe = _chromium_executable_path()
            if exe:
                # System Chrome/Edge/Chromium (default or discovered)
                launch_kwargs: dict[str, Any] = {
                    "headless": user_state.headless,
                }
                extra_args = _chromium_launch_args()
                if extra_args:
                    launch_kwargs["args"] = extra_args
                launch_kwargs["executable_path"] = exe
                pw_browser = await pw.chromium.launch(**launch_kwargs)
            elif default_kind == "webkit" or sys.platform == "darwin":
                # macOS: default Safari or no Chromium → use WebKit (Safari)
                pw_browser = await pw.webkit.launch(
                    headless=user_state.headless,
                )
            else:
                # Windows/Linux without system Chromium → Playwright's Chromium
                launch_kwargs = {"headless": user_state.headless}
                extra_args = _chromium_launch_args()
                if extra_args:
                    launch_kwargs["args"] = extra_args
                pw_browser = await pw.chromium.launch(**launch_kwargs)
            context = await pw_browser.new_context()
            _attach_context_listeners(context, user_state)
            user_state.playwright = pw
            user_state.browser = pw_browser
            user_state.context = context
        user_state._last_browser_error = None
        _touch_activity_user(user_id)
        _start_idle_watchdog_user(user_id)
        return True
    except Exception as e:
        user_state._last_browser_error = str(e)
        return False


# pylint: disable=R0912,R0915
async def _action_start_user(
    user_id: str | None = None,
    headed: bool = False,
) -> ToolResponse:
    """Start browser for a specific user."""
    if user_id is None:
        user_id = _get_current_user_id()

    user_state = _state["users"].get(user_id)
    if not user_state:
        user_state = UserBrowserState()
        _state["users"][user_id] = user_state

    # Check browser state based on mode
    if _USE_SYNC_PLAYWRIGHT:
        browser_exists = user_state._sync_browser is not None
        current_headless = not user_state._sync_headless
    else:
        browser_exists = user_state.browser is not None
        current_headless = user_state.headless

    # If user asks for visible window (headed=True)
    # but browser is already running headless, restart with headed
    if browser_exists:
        if headed and current_headless:
            _cancel_idle_watchdog_user(user_id)
            try:
                await _action_stop_user(user_id)
            except Exception:
                pass
        else:
            return _tool_response(
                json.dumps(
                    {"ok": True, "message": "Browser already running"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    # Default: headless (background). Only headed=True shows window.
    user_state.headless = not headed
    if _USE_SYNC_PLAYWRIGHT:
        user_state._sync_headless = not headed

    try:
        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            pw, browser, context = await loop.run_in_executor(
                _get_executor(),
                lambda: _sync_browser_launch(user_state.headless),
            )
            user_state._sync_playwright = pw
            user_state._sync_browser = browser
            user_state._sync_context = context
            user_state._sync_headless = not headed
        else:
            async_playwright = _ensure_playwright_async()
            pw = await async_playwright().start()
            use_default = not is_running_in_container() and os.environ.get(
                "COPAW_BROWSER_USE_DEFAULT",
                "1",
            ).strip().lower() in ("1", "true", "yes")
            default_kind, default_path = (
                get_system_default_browser() if use_default else (None, None)
            )
            exe: Optional[str] = None
            if default_kind == "chromium" and default_path:
                exe = default_path
            elif default_kind != "webkit":
                exe = _chromium_executable_path()
            if exe:
                launch_kwargs = {"headless": user_state.headless}
                extra_args = _chromium_launch_args()
                if extra_args:
                    launch_kwargs["args"] = extra_args
                launch_kwargs["executable_path"] = exe
                pw_browser = await pw.chromium.launch(**launch_kwargs)
            elif default_kind == "webkit" or sys.platform == "darwin":
                pw_browser = await pw.webkit.launch(
                    headless=user_state.headless,
                )
            else:
                launch_kwargs = {"headless": user_state.headless}
                extra_args = _chromium_launch_args()
                if extra_args:
                    launch_kwargs["args"] = extra_args
                pw_browser = await pw.chromium.launch(**launch_kwargs)
            context = await pw_browser.new_context()
            _attach_context_listeners(context, user_state)
            user_state.playwright = pw
            user_state.browser = pw_browser
            user_state.context = context
        _touch_activity_user(user_id)
        _start_idle_watchdog_user(user_id)
        msg = (
            "Browser started (visible window)"
            if not user_state.headless
            else "Browser started"
        )
        return _tool_response(
            json.dumps(
                {"ok": True, "message": msg},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Browser start failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_stop_user(user_id: str | None = None) -> ToolResponse:
    """Stop browser for a specific user."""
    if user_id is None:
        user_id = _get_current_user_id()

    _cancel_idle_watchdog_user(user_id)

    user_state = _state["users"].get(user_id)
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Browser not running"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    # Check browser state based on mode
    if _USE_SYNC_PLAYWRIGHT:
        browser_exists = user_state._sync_browser is not None
    else:
        browser_exists = user_state.browser is not None

    if not browser_exists:
        _reset_browser_state_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Browser not running"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    if _USE_SYNC_PLAYWRIGHT:
        # Close sync browser in thread pool
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                _get_executor(),
                lambda: _sync_browser_close_user(user_state),
            )
        except Exception as e:
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": f"Browser stop failed: {e!s}"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        finally:
            _reset_browser_state_user(user_id)
    else:
        # Standard async mode
        try:
            if user_state.browser:
                await user_state.browser.close()
            if user_state.playwright is not None:
                await user_state.playwright.stop()
        except Exception as e:
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": f"Browser stop failed: {e!s}"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        finally:
            _reset_browser_state_user(user_id)

    return _tool_response(
        json.dumps(
            {"ok": True, "message": "Browser stopped"},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_open(
    url: str,
    page_id: str,
    user_id: str | None = None,
) -> ToolResponse:
    """Open a URL in a new page for a specific user."""
    url = (url or "").strip()
    if not url:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "url required for open"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    if user_id is None:
        user_id = _get_current_user_id()

    if not await _ensure_browser_for_user(user_id):
        user_state = _state["users"].get(user_id)
        err = (
            user_state._last_browser_error if user_state else None
        ) or "Browser not started"
        return _tool_response(
            json.dumps(
                {"ok": False, "error": err},
                ensure_ascii=False,
                indent=2,
            ),
        )

    user_state = _state["users"][user_id]

    # Check page limit for this user
    if len(user_state.pages) >= _MAX_PAGES_PER_USER:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Maximum page limit reached ({_MAX_PAGES_PER_USER}). Close some pages first.",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    try:
        if _USE_SYNC_PLAYWRIGHT:
            # Hybrid mode: create page in thread pool
            loop = asyncio.get_event_loop()
            # pylint: disable=unnecessary-lambda
            page = await loop.run_in_executor(
                _get_executor(),
                lambda: user_state._sync_context.new_page(),
            )
        else:
            # Standard async mode
            page = await user_state.context.new_page()

        user_state.refs[page_id] = {}
        user_state.console_logs[page_id] = []
        user_state.network_requests[page_id] = []
        user_state.pending_dialogs[page_id] = []
        user_state.pending_file_choosers[page_id] = []
        _attach_page_listeners(page, page_id, user_state)

        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _get_executor(),
                lambda: page.goto(url),
            )
        else:
            await page.goto(url)

        user_state.pages[page_id] = page
        user_state.current_page_id = page_id
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Opened {url}",
                    "page_id": page_id,
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Open failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_navigate(
    url: str,
    page_id: str,
    user_id: str | None = None,
) -> ToolResponse:
    """Navigate to a URL in an existing page for a specific user."""
    url = (url or "").strip()
    if not url:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "url required for navigate"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    if user_id is None:
        user_id = _get_current_user_id()

    user_state = _state["users"].get(user_id)
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    page = user_state.pages.get(page_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _get_executor(),
                lambda: page.goto(url),
            )
        else:
            await page.goto(url)
        user_state.current_page_id = page_id
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Navigated to {url}",
                    "url": page.url,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Navigate failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_screenshot(
    page_id: str,
    path: str,
    full_page: bool,
    screenshot_type: str = "png",
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    path = (path or "").strip()
    if not path:
        ext = "jpeg" if screenshot_type == "jpeg" else "png"
        path = f"page-{int(time.time())}.{ext}"
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref and ref.strip():
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref.strip(),
                frame_selector,
                user_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(
                    locator.screenshot,
                    path=path,
                    type=screenshot_type
                    if screenshot_type == "jpeg"
                    else "png",
                )
            else:
                await locator.screenshot(
                    path=path,
                    type=screenshot_type
                    if screenshot_type == "jpeg"
                    else "png",
                )
        else:
            if frame_selector and frame_selector.strip():
                root = _get_root(page, page_id, frame_selector)
                locator = root.locator("body").first
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        locator.screenshot,
                        path=path,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
                else:
                    await locator.screenshot(
                        path=path,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        page.screenshot,
                        path=path,
                        full_page=full_page,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
                else:
                    await page.screenshot(
                        path=path,
                        full_page=full_page,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Screenshot saved to {path}",
                    "path": path,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Screenshot failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_click(  # pylint: disable=too-many-branches
    page_id: str,
    selector: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    wait: int = 0,
    double_click: bool = False,
    button: str = "left",
    modifiers_json: str = "",
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "selector or ref required for click"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if wait > 0:
            await asyncio.sleep(wait / 1000.0)
        mods = _parse_json_param(modifiers_json, [])
        if not isinstance(mods, list):
            mods = []
        kwargs = {
            "button": button
            if button in ("left", "right", "middle")
            else "left",
        }
        if mods:
            kwargs["modifiers"] = [
                m
                for m in mods
                if m in ("Alt", "Control", "ControlOrMeta", "Meta", "Shift")
            ]

        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            if ref:
                locator = _get_locator_by_ref(
                    page,
                    page_id,
                    ref,
                    frame_selector,
                )
                if locator is None:
                    return _tool_response(
                        json.dumps(
                            {"ok": False, "error": f"Unknown ref: {ref}"},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                if double_click:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.dblclick(**kwargs),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.click(**kwargs),
                    )
            else:
                root = _get_root(page, page_id, frame_selector)
                locator = root.locator(selector).first
                if double_click:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.dblclick(**kwargs),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.click(**kwargs),
                    )
        else:
            # Standard async mode
            if ref:
                locator = _get_locator_by_ref(
                    page,
                    page_id,
                    ref,
                    frame_selector,
                )
                if locator is None:
                    return _tool_response(
                        json.dumps(
                            {"ok": False, "error": f"Unknown ref: {ref}"},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                if double_click:
                    await locator.dblclick(**kwargs)
                else:
                    await locator.click(**kwargs)
            else:
                root = _get_root(page, page_id, frame_selector)
                locator = root.locator(selector).first
                if double_click:
                    await locator.dblclick(**kwargs)
                else:
                    await locator.click(**kwargs)

        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Clicked {ref or selector}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Click failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_type(
    page_id: str,
    selector: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    text: str = "",
    submit: bool = False,
    slowly: bool = False,
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "selector or ref required for type"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref:
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref,
                frame_selector,
                user_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            if _USE_SYNC_PLAYWRIGHT:
                loop = asyncio.get_event_loop()
                if slowly:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.press_sequentially(text or ""),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.fill(text or ""),
                    )
                if submit:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.press("Enter"),
                    )
            else:
                if slowly:
                    await locator.press_sequentially(text or "")
                else:
                    await locator.fill(text or "")
                if submit:
                    await locator.press("Enter")
        else:
            root = _get_root(page, page_id, frame_selector)
            loc = root.locator(selector).first
            if _USE_SYNC_PLAYWRIGHT:
                loop = asyncio.get_event_loop()
                if slowly:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: loc.press_sequentially(text or ""),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: loc.fill(text or ""),
                    )
                if submit:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: loc.press("Enter"),
                    )
            else:
                if slowly:
                    await loc.press_sequentially(text or "")
                else:
                    await loc.fill(text or "")
                if submit:
                    await loc.press("Enter")
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Typed into {ref or selector}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Type failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_eval(
    page_id: str,
    code: str,
    user_id: str | None = None,
) -> ToolResponse:
    code = (code or "").strip()
    if not code:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "code required for eval"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if code.strip().startswith("(") or code.strip().startswith("function"):
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(page.evaluate, code)
            else:
                result = await page.evaluate(code)
        else:
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(
                    page.evaluate,
                    f"() => {{ return ({code}); }}",
                )
            else:
                result = await page.evaluate(f"() => {{ return ({code}); }}")
        try:
            out = json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            out = json.dumps(
                {"ok": True, "result": str(result)},
                ensure_ascii=False,
                indent=2,
            )
        _touch_activity_user(user_id)
        return _tool_response(out)
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Eval failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_pdf(
    page_id: str,
    path: str,
    user_id: str | None = None,
) -> ToolResponse:
    path = (path or "page.pdf").strip() or "page.pdf"
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.pdf, path=path)
        else:
            await page.pdf(path=path)
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"PDF saved to {path}", "path": path},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"PDF failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_close(
    page_id: str,
    user_id: str | None = None,
) -> ToolResponse:
    """Close a page for a specific user."""
    if user_id is None:
        user_id = _get_current_user_id()

    user_state = _state["users"].get(user_id)
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    page = user_state.pages.get(page_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.close)
        else:
            await page.close()
        del user_state.pages[page_id]
        for key in (
            "refs",
            "refs_frame",
            "console_logs",
            "network_requests",
            "pending_dialogs",
            "pending_file_choosers",
        ):
            getattr(user_state, key).pop(page_id, None)
        if user_state.current_page_id == page_id:
            remaining = list(user_state.pages.keys())
            user_state.current_page_id = remaining[0] if remaining else None
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Closed page '{page_id}'"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Close failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_snapshot(
    page_id: str,
    filename: str,
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    user_state = (
        _get_user_state() if user_id is None else _state["users"].get(user_id)
    )
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            # Hybrid mode: execute in thread pool
            loop = asyncio.get_event_loop()
            root = _get_root(page, page_id, frame_selector)
            locator = root.locator(":root")
            raw = await loop.run_in_executor(
                _get_executor(),
                lambda: locator.aria_snapshot(),  # pylint: disable=unnecessary-lambda
            )
        else:
            root = _get_root(page, page_id, frame_selector)
            locator = root.locator(":root")
            raw = await locator.aria_snapshot()

        raw_str = str(raw) if raw is not None else ""
        snapshot, refs = build_role_snapshot_from_aria(
            raw_str,
            interactive=False,
            compact=False,
        )
        user_state.refs[page_id] = refs
        user_state.refs_frame[page_id] = (
            frame_selector.strip() if frame_selector else ""
        )
        out = {
            "ok": True,
            "snapshot": snapshot,
            "refs": list(refs.keys()),
            "url": page.url,
        }
        if frame_selector and frame_selector.strip():
            out["frame_selector"] = frame_selector.strip()
        if filename and filename.strip():
            with open(filename.strip(), "w", encoding="utf-8") as f:
                f.write(snapshot)
            out["filename"] = filename.strip()
        _touch_activity_user(user_id)
        return _tool_response(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Snapshot failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_navigate_back(
    page_id: str,
    user_id: str | None = None,
) -> ToolResponse:
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.go_back)
        else:
            await page.go_back()
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Navigated back", "url": page.url},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Navigate back failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_evaluate(
    page_id: str,
    code: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    code = (code or "").strip()
    if not code:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "code required for evaluate"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref and ref.strip():
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref.strip(),
                frame_selector,
                user_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(locator.evaluate, code)
            else:
                result = await locator.evaluate(code)
        else:
            if code.strip().startswith("(") or code.strip().startswith(
                "function",
            ):
                if _USE_SYNC_PLAYWRIGHT:
                    result = await _run_sync(page.evaluate, code)
                else:
                    result = await page.evaluate(code)
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    result = await _run_sync(
                        page.evaluate,
                        f"() => {{ return ({code}); }}",
                    )
                else:
                    result = await page.evaluate(
                        f"() => {{ return ({code}); }}",
                    )
        try:
            out = json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            out = json.dumps(
                {"ok": True, "result": str(result)},
                ensure_ascii=False,
                indent=2,
            )
        _touch_activity_user(user_id)
        return _tool_response(out)
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Evaluate failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_resize(
    page_id: str,
    width: int,
    height: int,
    user_id: str | None = None,
) -> ToolResponse:
    if width <= 0 or height <= 0:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "width and height must be positive"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(
                page.set_viewport_size,
                {"width": width, "height": height},
            )
        else:
            await page.set_viewport_size({"width": width, "height": height})
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Resized to {width}x{height}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Resize failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_console_messages(
    page_id: str,
    level: str,
    filename: str,
    user_id: str | None = None,
) -> ToolResponse:
    user_state = (
        _get_user_state() if user_id is None else _state["users"].get(user_id)
    )
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    level = (level or "info").strip().lower()
    order = ("error", "warning", "info", "debug")
    idx = order.index(level) if level in order else 2
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    logs = user_state.console_logs.get(page_id, [])
    filtered = (
        [m for m in logs if order.index(m["level"]) <= idx]
        if level in order
        else logs
    )
    lines = [f"[{m['level']}] {m['text']}" for m in filtered]
    text = "\n".join(lines)
    if filename and filename.strip():
        with open(filename.strip(), "w", encoding="utf-8") as f:
            f.write(text)
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Console messages saved to {filename}",
                    "filename": filename.strip(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    _touch_activity_user(user_id)
    return _tool_response(
        json.dumps(
            {"ok": True, "messages": filtered, "text": text},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_handle_dialog(
    page_id: str,
    accept: bool,
    prompt_text: str,
    user_id: str | None = None,
) -> ToolResponse:
    user_state = (
        _get_user_state() if user_id is None else _state["users"].get(user_id)
    )
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    dialogs = user_state.pending_dialogs.get(page_id, [])
    if not dialogs:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "No pending dialog"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        dialog = dialogs.pop(0)
        if accept:
            if prompt_text and hasattr(dialog, "accept"):
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(dialog.accept, prompt_text)
                else:
                    await dialog.accept(prompt_text)
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(dialog.accept)
                else:
                    await dialog.accept()
        else:
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(dialog.dismiss)
            else:
                await dialog.dismiss()
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Dialog handled"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Handle dialog failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_file_upload(
    page_id: str,
    paths_json: str,
    user_id: str | None = None,
) -> ToolResponse:
    user_state = (
        _get_user_state() if user_id is None else _state["users"].get(user_id)
    )
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    paths = _parse_json_param(paths_json, [])
    if not isinstance(paths, list):
        paths = []
    try:
        choosers = user_state.pending_file_choosers.get(page_id, [])
        if not choosers:
            return _tool_response(
                json.dumps(
                    {
                        "ok": False,
                        "error": "No chooser. Click upload then file_upload.",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        chooser = choosers.pop(0)
        if paths:
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(chooser.set_files, paths)
            else:
                await chooser.set_files(paths)
            _touch_activity_user(user_id)
            return _tool_response(
                json.dumps(
                    {"ok": True, "message": f"Uploaded {len(paths)} file(s)"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(chooser.set_files, [])
        else:
            await chooser.set_files([])
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "File chooser cancelled"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"File upload failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_fill_form(
    page_id: str,
    fields_json: str,
    user_id: str | None = None,
) -> ToolResponse:
    user_state = (
        _get_user_state() if user_id is None else _state["users"].get(user_id)
    )
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    fields = _parse_json_param(fields_json, [])
    if not isinstance(fields, list) or not fields:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "fields required (JSON array)"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    refs = _get_refs(page_id, user_id)
    # Use last snapshot's frame so fill_form works after iframe snapshot
    frame = user_state.refs_frame.get(page_id, "")
    try:
        for f in fields:
            ref = (f.get("ref") or "").strip()
            if not ref or ref not in refs:
                continue
            locator = _get_locator_by_ref(page, page_id, ref, frame)
            if locator is None:
                continue
            field_type = (f.get("type") or "textbox").lower()
            value = f.get("value")
            if field_type == "checkbox":
                if isinstance(value, str):
                    value = value.strip().lower() in ("true", "1", "yes")
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(locator.set_checked, bool(value))
                else:
                    await locator.set_checked(bool(value))
            elif field_type == "radio":
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(locator.set_checked, True)
                else:
                    await locator.set_checked(True)
            elif field_type == "combobox":
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        locator.select_option,
                        label=value if isinstance(value, str) else None,
                        value=value,
                    )
                else:
                    await locator.select_option(
                        label=value if isinstance(value, str) else None,
                        value=value,
                    )
            elif field_type == "slider":
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(locator.fill, str(value))
                else:
                    await locator.fill(str(value))
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        locator.fill,
                        str(value) if value is not None else "",
                    )
                else:
                    await locator.fill(str(value) if value is not None else "")
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Filled {len(fields)} field(s)"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Fill form failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


def _run_playwright_install() -> None:
    """Run playwright install in a blocking way (for use in thread)."""
    subprocess.run(
        [sys.executable, "-m", "playwright", "install"],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minutes max
    )


async def _action_install() -> ToolResponse:
    """Install Playwright browsers. If a system Chrome/Chromium/Edge is found,
    use it and skip download. On macOS with no Chromium, use Safari (WebKit)
    so no download is needed. Only run playwright install when necessary.
    """
    exe = _chromium_executable_path()
    if exe:
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Using system browser (no download): {exe}",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    if _use_webkit_fallback():
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": "On macOS using Safari (WebKit); no browser download needed.",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        await asyncio.to_thread(_run_playwright_install)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Browser installed"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except subprocess.TimeoutExpired:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": "Browser install timed out (10 min). Run manually in terminal: "
                    f"{sys.executable!s} -m playwright install",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Install failed: {e!s}. Install manually: "
                    f"{sys.executable!s} -m pip install playwright && "
                    f"{sys.executable!s} -m playwright install",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_press_key(
    page_id: str,
    key: str,
    user_id: str | None = None,
) -> ToolResponse:
    key = (key or "").strip()
    if not key:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "key required for press_key"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.keyboard.press, key)
        else:
            await page.keyboard.press(key)
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Pressed key {key}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Press key failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_network_requests(
    page_id: str,
    include_static: bool,
    filename: str,
    user_id: str | None = None,
) -> ToolResponse:
    user_state = (
        _get_user_state() if user_id is None else _state["users"].get(user_id)
    )
    if not user_state:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    requests = user_state.network_requests.get(page_id, [])
    if not include_static:
        static = ("image", "stylesheet", "font", "media")
        requests = [r for r in requests if r.get("resourceType") not in static]
    lines = [
        f"{r.get('method', '')} {r.get('url', '')} {r.get('status', '')}"
        for r in requests
    ]
    text = "\n".join(lines)
    if filename and filename.strip():
        with open(filename.strip(), "w", encoding="utf-8") as f:
            f.write(text)
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Network requests saved to {filename}",
                    "filename": filename.strip(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    _touch_activity_user(user_id)
    return _tool_response(
        json.dumps(
            {"ok": True, "requests": requests, "text": text},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_run_code(
    page_id: str,
    code: str,
    user_id: str | None = None,
) -> ToolResponse:
    """Run JS in page (like eval). Use evaluate for element (ref)."""
    code = (code or "").strip()
    if not code:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "code required for run_code"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if code.strip().startswith("(") or code.strip().startswith("function"):
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(page.evaluate, code)
            else:
                result = await page.evaluate(code)
        else:
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(
                    page.evaluate,
                    f"() => {{ return ({code}); }}",
                )
            else:
                result = await page.evaluate(f"() => {{ return ({code}); }}")
        try:
            out = json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            out = json.dumps(
                {"ok": True, "result": str(result)},
                ensure_ascii=False,
                indent=2,
            )
        _touch_activity_user(user_id)
        return _tool_response(out)
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Run code failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_drag(
    page_id: str,
    start_ref: str,
    end_ref: str,
    start_selector: str = "",
    end_selector: str = "",
    start_element: str = "",  # pylint: disable=unused-argument
    end_element: str = "",  # pylint: disable=unused-argument
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    start_ref = (start_ref or "").strip()
    end_ref = (end_ref or "").strip()
    start_selector = (start_selector or "").strip()
    end_selector = (end_selector or "").strip()
    use_refs = bool(start_ref and end_ref)
    use_selectors = bool(start_selector and end_selector)
    if not use_refs and not use_selectors:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "drag needs (start_ref,end_ref) or (start_sel,end_sel)"
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        root = _get_root(page, page_id, frame_selector)
        if use_refs:
            start_locator = _get_locator_by_ref(
                page,
                page_id,
                start_ref,
                frame_selector,
                user_id,
            )
            end_locator = _get_locator_by_ref(
                page,
                page_id,
                end_ref,
                frame_selector,
                user_id,
            )
            if start_locator is None or end_locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": "Unknown ref for drag"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
        else:
            start_locator = root.locator(start_selector).first
            end_locator = root.locator(end_selector).first
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(start_locator.drag_to, end_locator)
        else:
            await start_locator.drag_to(end_locator)
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Drag completed"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Drag failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_hover(
    page_id: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    selector: str = "",
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "hover requires ref or selector"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref:
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref,
                frame_selector,
                user_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
        else:
            root = _get_root(page, page_id, frame_selector)
            locator = root.locator(selector).first
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(locator.hover)
        else:
            await locator.hover()
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Hovered {ref or selector}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Hover failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_select_option(
    page_id: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    values_json: str = "",
    frame_selector: str = "",
    user_id: str | None = None,
) -> ToolResponse:
    ref = (ref or "").strip()
    values = _parse_json_param(values_json, [])
    if not isinstance(values, list):
        values = [values] if values is not None else []
    if not ref:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "ref required for select_option"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    if not values:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": "values required (JSON array or comma-separated)",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        locator = _get_locator_by_ref(page, page_id, ref, frame_selector)
        if locator is None:
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": f"Unknown ref: {ref}"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(locator.select_option, value=values)
        else:
            await locator.select_option(value=values)
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Selected {values}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Select option failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_tabs(  # pylint: disable=too-many-return-statements
    page_id: str,
    tab_action: str,
    index: int,
    user_id: str | None = None,
) -> ToolResponse:
    """Manage tabs for a specific user."""
    if user_id is None:
        user_id = _get_current_user_id()

    user_state = _state["users"].get(user_id)
    if not user_state:
        if tab_action == "list":
            return _tool_response(
                json.dumps(
                    {"ok": True, "tabs": [], "count": 0},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "Browser not started"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    tab_action = (tab_action or "").strip().lower()
    if not tab_action:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": "tab_action required (list, new, close, select)",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    pages = user_state.pages
    page_ids = list(pages.keys())
    if tab_action == "list":
        return _tool_response(
            json.dumps(
                {"ok": True, "tabs": page_ids, "count": len(page_ids)},
                ensure_ascii=False,
                indent=2,
            ),
        )
    if tab_action == "new":
        # Check page limit for this user
        if len(user_state.pages) >= _MAX_PAGES_PER_USER:
            return _tool_response(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"Maximum page limit reached ({_MAX_PAGES_PER_USER}). Close some pages first.",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if _USE_SYNC_PLAYWRIGHT:
            if not user_state._sync_context:
                ok = await _ensure_browser_for_user(user_id)
                if not ok:
                    err = (
                        user_state._last_browser_error or "Browser not started"
                    )
                    return _tool_response(
                        json.dumps(
                            {"ok": False, "error": err},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
        else:
            if not user_state.context:
                ok = await _ensure_browser_for_user(user_id)
                if not ok:
                    err = (
                        user_state._last_browser_error or "Browser not started"
                    )
                    return _tool_response(
                        json.dumps(
                            {"ok": False, "error": err},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
        try:
            if _USE_SYNC_PLAYWRIGHT:
                page = await _run_sync(user_state._sync_context.new_page)
            else:
                page = await user_state.context.new_page()
            new_id = _next_page_id(user_state)
            user_state.refs[new_id] = {}
            user_state.console_logs[new_id] = []
            user_state.network_requests[new_id] = []
            user_state.pending_dialogs[new_id] = []
            _attach_page_listeners(page, new_id, user_state)
            user_state.pages[new_id] = page
            user_state.current_page_id = new_id
            _touch_activity_user(user_id)
            return _tool_response(
                json.dumps(
                    {
                        "ok": True,
                        "page_id": new_id,
                        "tabs": list(user_state.pages.keys()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception as e:
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": f"New tab failed: {e!s}"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    if tab_action == "close":
        target_id = page_ids[index] if 0 <= index < len(page_ids) else page_id
        return await _action_close(target_id, user_id=user_id)
    if tab_action == "select":
        target_id = page_ids[index] if 0 <= index < len(page_ids) else page_id
        user_state.current_page_id = target_id
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Use page_id={target_id} for later actions",
                    "page_id": target_id,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return _tool_response(
        json.dumps(
            {"ok": False, "error": f"Unknown tab_action: {tab_action}"},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_wait_for(
    page_id: str,
    wait_time: float,
    text: str,
    text_gone: str,
    user_id: str | None = None,
) -> ToolResponse:
    page = _get_page(page_id, user_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if wait_time and wait_time > 0:
            await asyncio.sleep(wait_time)
        text = (text or "").strip()
        text_gone = (text_gone or "").strip()
        if text:
            locator = page.get_by_text(text)
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(
                    locator.wait_for,
                    state="visible",
                    timeout=30000,
                )
            else:
                await locator.wait_for(
                    state="visible",
                    timeout=30000,
                )
        if text_gone:
            locator = page.get_by_text(text_gone)
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(
                    locator.wait_for,
                    state="hidden",
                    timeout=30000,
                )
            else:
                await locator.wait_for(
                    state="hidden",
                    timeout=30000,
                )
        _touch_activity_user(user_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Wait completed"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Wait failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
