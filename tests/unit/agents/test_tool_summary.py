# -*- coding: utf-8 -*-
import pytest

from swe.agents.utils import tool_summary


def test_tool_display_name_returns_chinese_label() -> None:
    assert tool_summary.get_tool_display_name("grep_search") == "内容搜索"


def test_rule_call_summary_hides_shell_details() -> None:
    summary = tool_summary.generate_tool_call_summary(
        tool_name="execute_shell_command",
        arguments='{"command": "rm -rf /tmp/demo"}',
    )

    assert summary == "开始执行操作"


def test_rule_call_summary_keeps_browser_search_target() -> None:
    summary = tool_summary.generate_tool_call_summary(
        tool_name="browser_use",
        arguments=(
            '{"action": "open", "url": '
            '"https://github.com/search?q=copaw&type=repositories"}'
        ),
    )

    assert summary == "正在 GitHub 搜索 copaw"


def test_rule_call_summary_describes_file_read_action() -> None:
    summary = tool_summary.generate_tool_call_summary(
        tool_name="read_file",
        arguments='{"file_path": "/tmp/demo.txt"}',
    )

    assert summary == "正在读取 demo.txt"


@pytest.mark.asyncio
async def test_async_call_summary_uses_model_for_all_tools(
    monkeypatch,
) -> None:
    async def fake_run_summary_model(prompt: str) -> str:
        assert "读取文件" in prompt
        return "查看资料内容"

    monkeypatch.setattr(
        tool_summary,
        "_run_summary_model",
        fake_run_summary_model,
    )
    monkeypatch.setattr(
        tool_summary,
        "_model_summary_cache",
        {},
    )

    summary = await tool_summary.async_generate_tool_call_summary(
        tool_name="read_file",
        arguments='{"file_path": "/tmp/demo.txt"}',
    )

    assert summary == "查看资料内容"


@pytest.mark.asyncio
async def test_async_call_summary_guides_model_to_keep_object(
    monkeypatch,
) -> None:
    captured = {}

    async def fake_run_summary_model(prompt: str) -> str:
        captured["prompt"] = prompt
        return "正在 GitHub 搜索 copaw"

    monkeypatch.setattr(
        tool_summary,
        "_run_summary_model",
        fake_run_summary_model,
    )
    monkeypatch.setattr(
        tool_summary,
        "_model_summary_cache",
        {},
    )

    summary = await tool_summary.async_generate_tool_call_summary(
        tool_name="browser_use",
        arguments=(
            '{"action": "open", "url": '
            '"https://github.com/search?q=copaw&type=repositories"}'
        ),
    )

    assert summary == "正在 GitHub 搜索 copaw"
    assert "建议保留的操作对象: GitHub 搜索 copaw" in captured["prompt"]
    assert "建议动作表达: 正在 GitHub 搜索 copaw" in captured["prompt"]


@pytest.mark.asyncio
async def test_async_call_summary_redacts_shell_command(
    monkeypatch,
) -> None:
    captured = {}

    async def fake_run_summary_model(prompt: str) -> str:
        captured["prompt"] = prompt
        return "处理系统中的一项操作"

    monkeypatch.setattr(
        tool_summary,
        "_run_summary_model",
        fake_run_summary_model,
    )
    monkeypatch.setattr(
        tool_summary,
        "_model_summary_cache",
        {},
    )

    summary = await tool_summary.async_generate_tool_call_summary(
        tool_name="execute_shell_command",
        arguments='{"command": "cat /etc/passwd"}',
    )

    assert summary == "处理系统中的一项操作"
    assert "cat /etc/passwd" not in captured["prompt"]
    assert "执行了一项系统操作" in captured["prompt"]


@pytest.mark.asyncio
async def test_async_output_summary_falls_back_on_model_error(
    monkeypatch,
) -> None:
    async def boom(_prompt: str) -> str:
        raise RuntimeError("llm timeout")

    monkeypatch.setattr(
        tool_summary,
        "_run_summary_model",
        boom,
    )
    monkeypatch.setattr(
        tool_summary,
        "_model_summary_cache",
        {},
    )

    summary = await tool_summary.async_generate_tool_output_summary(
        tool_name="glob_search",
        output='{"files": ["a.py", "b.py"]}',
        arguments='{"pattern": "**/*.py"}',
    )

    assert summary == "找到了 2 项相关内容"


@pytest.mark.asyncio
async def test_async_output_summary_preserves_empty_result_message(
    monkeypatch,
) -> None:
    async def fake_run_summary_model(_prompt: str) -> str:
        return "没有找到相关内容"

    monkeypatch.setattr(
        tool_summary,
        "_run_summary_model",
        fake_run_summary_model,
    )
    monkeypatch.setattr(
        tool_summary,
        "_model_summary_cache",
        {},
    )

    summary = await tool_summary.async_generate_tool_output_summary(
        tool_name="memory_search",
        output="[]",
        arguments='{"query": "tenant provider"}',
    )

    assert summary == "没有找到相关内容"


@pytest.mark.asyncio
async def test_async_output_summary_hides_shell_output_details(
    monkeypatch,
) -> None:
    captured = {}

    async def fake_run_summary_model(prompt: str) -> str:
        captured["prompt"] = prompt
        return "这项操作已经完成"

    monkeypatch.setattr(
        tool_summary,
        "_run_summary_model",
        fake_run_summary_model,
    )
    monkeypatch.setattr(
        tool_summary,
        "_model_summary_cache",
        {},
    )

    summary = await tool_summary.async_generate_tool_output_summary(
        tool_name="execute_shell_command",
        output="very technical stdout details",
        arguments='{"command": "pwd"}',
    )

    assert summary == "这项操作已经完成"
    assert "very technical stdout details" not in captured["prompt"]
