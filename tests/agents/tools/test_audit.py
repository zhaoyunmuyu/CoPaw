# -*- coding: utf-8 -*-
"""Tests for audit logging module."""

import logging
from io import StringIO

from copaw.agents.tools.audit import AuditEvent, hash_command, log_audit


class TestAuditEvent:
    """Tests for AuditEvent constants."""

    def test_audit_event_constants_exist(self):
        """审计事件常量应存在"""
        assert hasattr(AuditEvent, "PATH_VALIDATION_FAILED")
        assert hasattr(AuditEvent, "SANDBOX_EXECUTE")
        assert hasattr(AuditEvent, "SANDBOX_UNAVAILABLE")
        assert hasattr(AuditEvent, "PERMISSION_DENIED")

    def test_audit_event_constant_values(self):
        """审计事件常量值应正确"""
        assert AuditEvent.PATH_VALIDATION_FAILED == "path_validation_failed"
        assert AuditEvent.SANDBOX_EXECUTE == "sandbox_execute"
        assert AuditEvent.SANDBOX_UNAVAILABLE == "sandbox_unavailable"
        assert AuditEvent.PERMISSION_DENIED == "permission_denied"


class TestLogAudit:
    """Tests for log_audit function."""

    def test_log_audit_path_validation_failed(self):
        """记录路径验证失败事件"""
        # Create a StringIO handler to capture logs
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Get the audit logger and add our handler
        from copaw.agents.tools.audit import audit_logger

        audit_logger.addHandler(handler)
        original_level = audit_logger.level
        audit_logger.setLevel(logging.INFO)

        try:
            log_audit(
                event=AuditEvent.PATH_VALIDATION_FAILED,
                user_id="test_user",
                details={"path_hint": "outside_user_dir"},
            )

            log_output = log_stream.getvalue()
            assert "test_user" in log_output
            assert "path_validation_failed" in log_output
        finally:
            audit_logger.removeHandler(handler)
            audit_logger.setLevel(original_level)

    def test_log_audit_sandbox_execute(self):
        """记录沙箱执行事件"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        from copaw.agents.tools.audit import audit_logger

        audit_logger.addHandler(handler)
        original_level = audit_logger.level
        audit_logger.setLevel(logging.INFO)

        try:
            log_audit(
                event=AuditEvent.SANDBOX_EXECUTE,
                user_id="test_user",
                details={"command_hash": "abc123", "returncode": 0},
            )

            log_output = log_stream.getvalue()
            assert "sandbox_execute" in log_output
            assert "test_user" in log_output
            assert "abc123" in log_output
        finally:
            audit_logger.removeHandler(handler)
            audit_logger.setLevel(original_level)

    def test_log_audit_does_not_leak_full_paths(self):
        """审计日志不应泄露完整路径"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        from copaw.agents.tools.audit import audit_logger

        audit_logger.addHandler(handler)
        original_level = audit_logger.level
        audit_logger.setLevel(logging.INFO)

        try:
            log_audit(
                event=AuditEvent.PATH_VALIDATION_FAILED,
                user_id="test_user",
                details={"path": "/etc/passwd"},
            )

            log_output = log_stream.getvalue()
            # The full path should not appear in the log
            assert "/etc/passwd" not in log_output
            # But a hint should be present
            assert "path_hint" in log_output
            assert "provided_but_redacted" in log_output
        finally:
            audit_logger.removeHandler(handler)
            audit_logger.setLevel(original_level)

    def test_log_audit_sanitizes_sensitive_keys(self):
        """审计日志应清理敏感键"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        from copaw.agents.tools.audit import audit_logger

        audit_logger.addHandler(handler)
        original_level = audit_logger.level
        audit_logger.setLevel(logging.INFO)

        try:
            log_audit(
                event=AuditEvent.PATH_VALIDATION_FAILED,
                user_id="test_user",
                details={
                    "file_path": "/secret/path",
                    "full_path": "/another/secret",
                    "safe_key": "safe_value",
                },
            )

            log_output = log_stream.getvalue()
            assert "/secret/path" not in log_output
            assert "/another/secret" not in log_output
            assert "safe_value" in log_output
        finally:
            audit_logger.removeHandler(handler)
            audit_logger.setLevel(original_level)

    def test_log_audit_truncates_long_strings(self):
        """审计日志应截断长字符串"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        from copaw.agents.tools.audit import audit_logger

        audit_logger.addHandler(handler)
        original_level = audit_logger.level
        audit_logger.setLevel(logging.INFO)

        try:
            long_value = "a" * 200
            log_audit(
                event=AuditEvent.SANDBOX_EXECUTE,
                user_id="test_user",
                details={"output": long_value},
            )

            log_output = log_stream.getvalue()
            assert long_value not in log_output
            assert "..." in log_output
        finally:
            audit_logger.removeHandler(handler)
            audit_logger.setLevel(original_level)


class TestHashCommand:
    """Tests for hash_command function."""

    def test_hash_command_returns_string(self):
        """hash_command应返回字符串"""
        result = hash_command("ls -la")
        assert isinstance(result, str)

    def test_hash_command_returns_16_chars(self):
        """hash_command应返回16字符"""
        result = hash_command("ls -la")
        assert len(result) == 16

    def test_hash_command_is_deterministic(self):
        """hash_command应是确定性的"""
        result1 = hash_command("ls -la")
        result2 = hash_command("ls -la")
        assert result1 == result2

    def test_hash_command_different_for_different_inputs(self):
        """不同命令应产生不同哈希"""
        result1 = hash_command("ls -la")
        result2 = hash_command("rm -rf")
        assert result1 != result2


class TestAuditEdgeCases:
    """Tests for edge cases in audit logging."""

    def test_sanitize_empty_details(self):
        """空详情字典应返回空"""
        from copaw.agents.tools.audit import _sanitize_details

        result = _sanitize_details({})
        assert result == {}

    def test_sanitize_none_values(self):
        """None 值应保留"""
        from copaw.agents.tools.audit import _sanitize_details

        result = _sanitize_details({"key": None})
        assert result == {"key": None}

    def test_sanitize_non_string_values(self):
        """非字符串值应保留"""
        from copaw.agents.tools.audit import _sanitize_details

        result = _sanitize_details(
            {"count": 42, "items": ["a", "b"], "config": {"nested": True}}
        )
        assert result["count"] == 42
        assert result["items"] == ["a", "b"]
        assert result["config"] == {"nested": True}
