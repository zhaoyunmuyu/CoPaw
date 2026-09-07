# -*- coding: utf-8 -*-
"""Tests for per-model Provider runtime configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swe.providers.openai_provider import OpenAIProvider
from swe.providers.provider import ModelRuntimeConfig


def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        id="openai",
        name="OpenAI",
        base_url="https://api.example.test/v1",
        api_key="sk-test",
        models=[],
    )


def test_model_runtime_config_validates_and_deduplicates_efforts() -> None:
    config = ModelRuntimeConfig(
        temperature=0.7,
        top_p=0.9,
        top_k=20,
        max_input_length=128_000,
        max_output_length=8_192,
        supports_enable_thinking=True,
        supported_reasoning_efforts=["high", "low", "high"],
        enable_thinking=True,
        reasoning_effort="high",
    )

    assert config.supported_reasoning_efforts == ["high", "low"]
    assert config.reasoning_effort == "high"


@pytest.mark.parametrize(
    "payload",
    [
        {"temperature": -0.1},
        {"top_p": 1.1},
        {"top_k": -1},
        {"max_input_length": 0},
        {"max_output_length": 0},
        {"supported_reasoning_efforts": ["medium"]},
        {
            "supported_reasoning_efforts": ["low"],
            "reasoning_effort": "high",
        },
    ],
)
def test_model_runtime_config_rejects_invalid_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ModelRuntimeConfig(**payload)


def test_provider_updates_one_model_config_without_legacy_generate_kwargs() -> (
    None
):
    provider = _provider()

    updated = provider.update_model_config(
        "gpt-5",
        {"temperature": 0.2, "max_output_length": 4_096},
    )

    assert updated.temperature == 0.2
    assert updated.max_output_length == 4_096
    assert provider.model_configs["gpt-5"] == updated
    assert "generate_kwargs" not in provider.model_dump()


def test_provider_deleting_model_config_removes_only_target() -> None:
    provider = _provider()
    provider.update_model_config("gpt-5", {"temperature": 0.2})
    provider.update_model_config("gpt-5-mini", {"temperature": 0.7})

    provider.delete_model_config("gpt-5")

    assert "gpt-5" not in provider.model_configs
    assert provider.model_configs["gpt-5-mini"].temperature == 0.7


def test_chat_model_instance_uses_only_explicit_generation_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    created: list[dict] = []

    class FakeChatModel:
        def __init__(self, **kwargs) -> None:
            created.append(kwargs)

    monkeypatch.setattr(
        "swe.providers.openai_chat_model_compat.OpenAIChatModelCompat",
        FakeChatModel,
    )

    provider.get_chat_model_instance(
        "gpt-5",
        generation_kwargs={"temperature": 0.2, "max_tokens": 4_096},
    )

    assert created[0]["generate_kwargs"] == {
        "temperature": 0.2,
        "max_tokens": 4_096,
    }
