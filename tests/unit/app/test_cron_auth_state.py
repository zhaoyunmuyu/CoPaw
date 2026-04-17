# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from swe.app.crons import auth_state
from swe.app.routers import auth as auth_router


@pytest.fixture
def workspace_dir(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_extract_access_token_from_cookie():
    cookie = "foo=bar; com.cmb.dw.rtl.sso.token=access-1; theme=dark"

    assert auth_state.extract_access_token_from_cookie(cookie) == "access-1"


def test_extract_access_token_from_cookie_raises_when_missing():
    with pytest.raises(
        ValueError,
        match=r"com\.cmb\.dw\.rtl\.sso\.token",
    ):
        auth_state.extract_access_token_from_cookie("foo=bar; theme=dark")


def test_merge_auth_token_into_cookie_replaces_existing_token():
    cookie = "foo=bar; com.cmb.dw.rtl.sso.token=old-token; theme=dark"

    assert auth_state.merge_auth_token_into_cookie(cookie, "new-token") == (
        "foo=bar; com.cmb.dw.rtl.sso.token=new-token; theme=dark"
    )


def test_merge_auth_token_into_cookie_appends_when_missing():
    cookie = "foo=bar; theme=dark"

    assert auth_state.merge_auth_token_into_cookie(cookie, "new-token") == (
        "foo=bar; theme=dark; com.cmb.dw.rtl.sso.token=new-token"
    )


def test_ensure_user_info_reuses_existing_state_when_not_near_expiry(
    monkeypatch,
    workspace_dir,
):
    state = auth_state.save_user_info_from_access_token(
        "access-1",
        cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=access-1",
        workspace_dir=workspace_dir,
    )
    original_refreshed_at = state.user_info_refreshed_at

    get_user_info_calls: list[str] = []

    def fake_get_user_info(access_token: str):
        get_user_info_calls.append(access_token)
        return {"userInfo": {"token": access_token}, "exp": 1776937265}

    monkeypatch.setattr(auth_state, "get_user_info", fake_get_user_info)

    reused = auth_state.ensure_user_info_from_access_token(
        "access-2",
        cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=access-2",
        workspace_dir=workspace_dir,
    )

    assert get_user_info_calls == []
    assert reused.reused is True
    assert reused.state.user_info == state.user_info
    assert reused.state.user_info_refreshed_at == original_refreshed_at
    assert reused.state.cookie_header == (
        "foo=bar; com.cmb.dw.rtl.sso.token=access-2"
    )


def test_ensure_user_info_refreshes_when_near_expiry(
    monkeypatch,
    workspace_dir,
):
    state = auth_state.save_user_info_from_access_token(
        "access-1",
        cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=access-1",
        workspace_dir=workspace_dir,
    )
    state.user_info_expires_at = auth_state.utc_now() + timedelta(hours=1)
    auth_state.save_cron_auth_state(state, workspace_dir=workspace_dir)

    get_user_info_calls: list[str] = []

    def fake_get_user_info(access_token: str):
        get_user_info_calls.append(access_token)
        return {
            "userInfo": {"token": access_token, "fresh": True},
            "exp": 1776937265,
        }

    monkeypatch.setattr(auth_state, "get_user_info", fake_get_user_info)

    refreshed = auth_state.ensure_user_info_from_access_token(
        "access-2",
        cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=access-2",
        workspace_dir=workspace_dir,
    )

    assert get_user_info_calls == ["access-2"]
    assert refreshed.reused is False
    assert refreshed.state.user_info == {
        "token": "access-2",
        "fresh": True,
    }
    assert refreshed.state.cookie_header == (
        "foo=bar; com.cmb.dw.rtl.sso.token=access-2"
    )


def test_issue_auth_token_fails_when_user_info_expired(workspace_dir):
    state = auth_state.save_user_info_from_access_token(
        "access-1",
        cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=access-1",
        workspace_dir=workspace_dir,
    )
    state.user_info_expires_at = auth_state.utc_now() - timedelta(seconds=1)
    auth_state.save_cron_auth_state(state, workspace_dir=workspace_dir)

    with pytest.raises(ValueError, match="expired"):
        auth_state.issue_auth_token(workspace_dir=workspace_dir)


def test_resolve_auth_token_for_execution_returns_empty_when_user_info_missing(
    workspace_dir,
):
    resolved = auth_state.resolve_auth_token_for_execution(
        workspace_dir=workspace_dir,
    )

    assert resolved.token is None
    assert resolved.cookie_header is None
    assert resolved.expires_at is None


def test_resolve_auth_token_for_execution_includes_cookie_header(
    monkeypatch,
    workspace_dir,
):
    auth_state.save_user_info_from_access_token(
        "access-1",
        cookie_header="foo=bar; com.cmb.dw.rtl.sso.token=access-1; theme=dark",
        workspace_dir=workspace_dir,
    )

    monkeypatch.setattr(
        auth_state,
        "get_auth_token",
        lambda _payload: "auth-123",
    )

    resolved = auth_state.resolve_auth_token_for_execution(
        workspace_dir=workspace_dir,
    )

    assert resolved.token == "auth-123"
    assert resolved.cookie_header == (
        "foo=bar; com.cmb.dw.rtl.sso.token=auth-123; theme=dark"
    )


@pytest.mark.asyncio
async def test_configure_cron_auth_returns_reused_status(monkeypatch):
    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(tenant_id="tenant-a", workspace_dir="/tmp/ws")

    ensured_args = {}

    monkeypatch.setattr(
        auth_router,
        "get_agent_for_request",
        fake_get_agent_for_request,
    )
    monkeypatch.setattr(
        auth_router,
        "extract_access_token_from_cookie",
        lambda cookie: "token-from-cookie",
    )

    def fake_ensure_user_info_from_access_token(*args, **kwargs):
        ensured_args["args"] = args
        ensured_args["kwargs"] = kwargs
        return auth_state.CronUserInfoEnsureResult(
            state=auth_state.CronAuthState(),
            reused=True,
        )

    monkeypatch.setattr(
        auth_router,
        "ensure_user_info_from_access_token",
        fake_ensure_user_info_from_access_token,
    )
    monkeypatch.setattr(
        auth_router,
        "get_auth_snapshot",
        lambda **kwargs: auth_state.CronAuthSnapshot(
            configured=True,
            user_info_expires_at=None,
            auth_token_expires_at=None,
            has_auth_token=False,
        ),
    )

    response = await auth_router.configure_cron_auth(
        auth_router.CronAuthConfigureRequest(
            cookie="foo=bar; com.cmb.dw.rtl.sso.token=token-from-cookie"
        ),
        request=SimpleNamespace(),
    )

    assert response["user_info_status"] == "reused"
    assert ensured_args["args"] == ("token-from-cookie",)
    assert ensured_args["kwargs"]["cookie_header"] == (
        "foo=bar; com.cmb.dw.rtl.sso.token=token-from-cookie"
    )


@pytest.mark.asyncio
async def test_configure_cron_auth_returns_refreshed_status(monkeypatch):
    async def fake_get_agent_for_request(_request):
        return SimpleNamespace(tenant_id="tenant-a", workspace_dir="/tmp/ws")

    monkeypatch.setattr(
        auth_router,
        "get_agent_for_request",
        fake_get_agent_for_request,
    )
    monkeypatch.setattr(
        auth_router,
        "extract_access_token_from_cookie",
        lambda cookie: "token-from-cookie",
    )
    monkeypatch.setattr(
        auth_router,
        "ensure_user_info_from_access_token",
        lambda *args, **kwargs: auth_state.CronUserInfoEnsureResult(
            state=auth_state.CronAuthState(),
            reused=False,
        ),
    )
    monkeypatch.setattr(
        auth_router,
        "get_auth_snapshot",
        lambda **kwargs: auth_state.CronAuthSnapshot(
            configured=True,
            user_info_expires_at=None,
            auth_token_expires_at=None,
            has_auth_token=False,
        ),
    )

    response = await auth_router.configure_cron_auth(
        auth_router.CronAuthConfigureRequest(
            cookie="foo=bar; com.cmb.dw.rtl.sso.token=token-from-cookie"
        ),
        request=SimpleNamespace(),
    )

    assert response["user_info_status"] == "refreshed"
