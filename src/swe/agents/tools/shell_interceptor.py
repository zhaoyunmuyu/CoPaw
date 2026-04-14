# -*- coding: utf-8 -*-
"""Shell command interceptor for tenant isolation.

This module provides command interception mechanism that automatically
injects tenant isolation parameters (--tenant-id, --target-user, etc.)
from ContextVar into specific commands like 'cron' and 'swe'.
"""
from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from typing import List, Tuple

from ...config.context import (
    get_current_tenant_id,
    get_current_user_id,
)

logger = logging.getLogger(__name__)


@dataclass
class InterceptRule:
    """Rule for intercepting and modifying shell commands."""

    command_prefix: str  # 匹配的命令前缀，如 "cron" 或 "swe cron"
    inject_params: List[str]  # 需注入的参数名，如 ["--tenant-id"]
    # 注入位置："after_subcommand" 或 "at_end"
    inject_position: str = "after_subcommand"


# 拦截规则定义 - 按优先级排序（更具体的规则在前）
INTERCEPT_RULES: List[InterceptRule] = [
    # swe cron create 需要注入 tenant-id 和 target-user
    InterceptRule(
        command_prefix="swe cron create",
        inject_params=["--tenant-id", "--target-user"],
        inject_position="at_end",
    ),
    # swe cron 其他子命令只需注入 tenant-id
    InterceptRule(
        command_prefix="swe cron",
        inject_params=["--tenant-id"],
        inject_position="at_end",
    ),
]


def _has_param(tokens: List[str], param_name: str) -> bool:
    """Check if command already has the parameter.

    Handles both formats:
    - --tenant-id value (param at index i, value at i+1)
    - --tenant-id=value (param with embedded value)

    Args:
        tokens: List of command tokens
        param_name: Parameter name to check (e.g., "--tenant-id")

    Returns:
        True if parameter already exists in command
    """
    for token in tokens:
        # Check --param=value format
        if token.startswith(f"{param_name}="):
            return True
        # Check --param format (standalone parameter)
        if token == param_name:
            return True
    return False


def intercept_command(command: str) -> Tuple[str, bool]:
    """Intercept and modify command with tenant isolation params.

    Automatically injects --tenant-id and --target-user/--user-id from
    ContextVar for commands matching INTERCEPT_RULES. Skips injection
    if the parameter already exists in the original command.

    Args:
        command: Original shell command string

    Returns:
        Tuple of (modified_command, was_intercepted)
    """
    tenant_id = get_current_tenant_id()
    user_id = get_current_user_id()

    # 如果没有用户上下文，不修改命令
    if tenant_id is None and user_id is None:
        return command, False

    # 解析命令
    try:
        tokens = shlex.split(command)
    except ValueError:
        # shlex 解析失败时返回原命令
        return command, False

    if not tokens:
        return command, False

    # 匹配拦截规则（按优先级顺序）
    for rule in INTERCEPT_RULES:
        prefix_tokens = rule.command_prefix.split()
        if tokens[: len(prefix_tokens)] != prefix_tokens:
            continue

        # 构建注入参数（跳过已存在的参数）
        inject_parts = []
        for param in rule.inject_params:
            # 检查参数是否已存在，避免重复添加
            if _has_param(tokens, param):
                logger.debug(
                    "Shell interceptor: skipping %s, "
                    "already exists in command",
                    param,
                )
                continue

            # 根据参数类型获取值
            if param == "--tenant-id" and tenant_id:
                inject_parts.append(f"{param} {tenant_id}")
            elif param == "--target-user" and user_id:
                inject_parts.append(f"{param} {user_id}")
            elif param == "--user-id" and user_id:
                inject_parts.append(f"{param} {user_id}")

        # 如果没有需要注入的参数，返回原命令
        if not inject_parts:
            return command, False

        # 根据位置注入
        if rule.inject_position == "at_end":
            # 直接追加到命令末尾，保留原始格式
            modified_command = command.rstrip() + " " + " ".join(inject_parts)
        else:  # after_subcommand
            # 在子命令后插入（需要重新组装）
            insert_pos = len(prefix_tokens)
            # 注入参数值作为单独的 tokens
            inject_tokens = []
            for param in rule.inject_params:
                if _has_param(tokens, param):
                    continue
                if param == "--tenant-id" and tenant_id:
                    inject_tokens.extend([param, tenant_id])
                elif param == "--target-user" and user_id:
                    inject_tokens.extend([param, user_id])
                elif param == "--user-id" and user_id:
                    inject_tokens.extend([param, user_id])
            if inject_tokens:
                tokens = tokens[:insert_pos] + inject_tokens + tokens[insert_pos:]
            modified_command = shlex.join(tokens)

        logger.info(
            "Shell command intercepted: %s -> %s",
            command,
            modified_command,
        )
        return modified_command, True

    return command, False
