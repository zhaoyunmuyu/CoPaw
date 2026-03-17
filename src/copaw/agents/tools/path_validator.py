# -*- coding: utf-8 -*-
"""Path validator for user permission isolation.

This module provides path validation to ensure users can only access
files within their own directory.
"""

import logging
from pathlib import Path
from typing import Union

from ...constant import get_request_working_dir

logger = logging.getLogger(__name__)


class PathValidator:
    """路径验证器，确保用户只能访问自己的目录。"""

    @staticmethod
    def get_user_dir() -> Path:
        """获取当前请求用户的目录。

        Returns:
            Path: 用户工作目录的绝对路径
        """
        return get_request_working_dir()

    @staticmethod
    def validate_path(path: Union[str, Path]) -> tuple[bool, Path, str]:
        """验证路径是否在用户目录内。

        Args:
            path: 待验证的路径（绝对或相对）

        Returns:
            tuple[bool, Path, str]: (是否有效, 解析后的路径, 错误信息)
        """
        if not path:
            return False, Path(), "Invalid path: empty path"

        user_dir = PathValidator.get_user_dir()

        try:
            input_path = Path(path)

            # 解析路径：相对路径基于用户目录解析
            if input_path.is_absolute():
                resolved = input_path.resolve()
            else:
                resolved = (user_dir / input_path).resolve()

            # 检查是否在用户目录内
            if resolved.is_relative_to(user_dir):
                return True, resolved, ""
            else:
                logger.warning(
                    "Path validation failed: path outside user directory"
                )
                return (
                    False,
                    resolved,
                    "Permission denied: path is outside allowed directory",
                )

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False, Path(), f"Invalid path: {e}"

    @staticmethod
    def resolve_and_validate(path: Union[str, Path]) -> Path:
        """解析并验证路径，失败时抛出 PermissionError。

        用于简化调用代码，当只需要成功情况时使用。

        Args:
            path: 待验证的路径

        Returns:
            Path: 解析后的绝对路径

        Raises:
            PermissionError: 当路径在用户目录外时
        """
        is_valid, resolved, error = PathValidator.validate_path(path)
        if not is_valid:
            raise PermissionError(error)
        return resolved