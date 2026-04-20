# -*- coding: utf-8 -*-
"""猜你想问功能模块 - 异步生成用户可能想问的后续问题."""

from .service import generate_suggestions, SuggestionService
from .store import store_suggestions, take_suggestions, peek_suggestions

__all__ = [
    "generate_suggestions",
    "SuggestionService",
    "store_suggestions",
    "take_suggestions",
    "peek_suggestions",
]