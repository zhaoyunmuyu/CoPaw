# -*- coding: utf-8 -*-
"""Context management for tenant model configuration.

This module provides context variables to manage tenant-specific model configurations,
enabling multi-tenant isolation in model selection and routing.
"""

from contextvars import ContextVar, Token
from typing import Optional

from copaw.config.context import TenantContextError
from copaw.tenant_models.models import TenantModelConfig

# Context variable to store the current tenant's model configuration
_current_model_config: ContextVar[Optional[TenantModelConfig]] = ContextVar(
    "current_model_config",
    default=None,
)


class TenantModelContext:
    """Context manager for tenant model configuration.

    This class provides methods to set, get, and reset tenant model configurations
    within a context scope, supporting nested contexts through token-based reset.

    Example:
        config = TenantModelConfig(...)
        token = TenantModelContext.set_config(config)
        try:
            # Code here has access to the config
            current_config = TenantModelContext.get_config_strict()
        finally:
            TenantModelContext.reset_config(token)
    """

    @staticmethod
    def set_config(config: TenantModelConfig) -> Token:
        """Set the current tenant model configuration in context.

        Args:
            config: The TenantModelConfig to set in context.

        Returns:
            Token for resetting the context variable to its previous state.
        """
        return _current_model_config.set(config)

    @staticmethod
    def get_config() -> Optional[TenantModelConfig]:
        """Get the current tenant model configuration from context.

        Returns:
            The current TenantModelConfig, or None if not set.
        """
        return _current_model_config.get()

    @staticmethod
    def get_config_strict() -> TenantModelConfig:
        """Get the current tenant model configuration, raising if not set.

        Returns:
            The current TenantModelConfig.

        Raises:
            TenantContextError: If model configuration is not set in context.
        """
        config = _current_model_config.get()
        if config is None:
            raise TenantContextError(
                "TenantModelConfig is not set in context. "
                "Ensure this code runs within a tenant-scoped request or context.",
            )
        return config

    @staticmethod
    def reset_config(token: Token) -> None:
        """Reset the tenant model configuration using a token.

        This restores the context variable to its previous state before
        the corresponding set_config call.

        Args:
            token: The token returned by set_config.
        """
        _current_model_config.reset(token)
