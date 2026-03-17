# src/copaw/agents/tools/audit.py
# -*- coding: utf-8 -*-
"""Audit logging for security events."""

import hashlib
import logging
from typing import Any

audit_logger = logging.getLogger("copaw.audit")
# Ensure propagation to root logger for pytest caplog capture
audit_logger.propagate = True


class AuditEvent:
    """审计事件类型常量。"""

    PATH_VALIDATION_FAILED = "path_validation_failed"
    SANDBOX_EXECUTE = "sandbox_execute"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    PERMISSION_DENIED = "permission_denied"


def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    """清理详情字典，移除敏感信息。"""
    sanitized = {}
    sensitive_keys = {"path", "file_path", "full_path", "absolute_path"}

    for key, value in details.items():
        if key.lower() in sensitive_keys:
            sanitized[f"{key}_hint"] = "provided_but_redacted"
        elif isinstance(value, str) and len(value) > 100:
            sanitized[key] = value[:100] + "..."
        else:
            sanitized[key] = value

    return sanitized


def log_audit(event: str, user_id: str, details: dict[str, Any]) -> None:
    """记录审计日志。"""
    sanitized_details = _sanitize_details(details)
    audit_logger.info(
        f"event={event} user={user_id} details={sanitized_details}"
    )


def hash_command(command: str) -> str:
    """计算命令的哈希值用于审计日志。"""
    return hashlib.sha256(command.encode()).hexdigest()[:16]