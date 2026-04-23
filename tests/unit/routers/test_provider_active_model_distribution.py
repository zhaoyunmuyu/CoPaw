# -*- coding: utf-8 -*-
"""Active-model distribution router tests."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from swe.app.routers import providers as providers_router
from swe.providers.models import ModelSlotConfig


def _request(
    tenant_id: str = "tenant-source",
    source_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(tenant_id=tenant_id, source_id=source_id),
    )


@dataclass
class FakeProvider:
    id: str
    models: list[dict[str, Any]] = field(default_factory=list)
    extra_models: list[dict[str, Any]] = field(default_factory=list)
    is_custom: bool = False
    name: str = ""
    api_key: str = ""
    base_url: str = ""
    chat_model: str = "OpenAIChatModel"
    generate_kwargs: dict[str, Any] = field(default_factory=dict)

    def has_model(self, model_id: str) -> bool:
        return any(
            item["id"] == model_id
            for item in [*self.models, *self.extra_models]
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name or self.id,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "chat_model": self.chat_model,
            "models": self.models,
            "extra_models": self.extra_models,
            "is_custom": self.is_custom,
            "generate_kwargs": self.generate_kwargs,
        }


class FakeManager:
    def __init__(
        self,
        *,
        active_model: ModelSlotConfig | None = None,
        providers: dict[str, FakeProvider] | None = None,
        fail_on_overwrite: str | None = None,
        fail_on_activate: str | None = None,
    ) -> None:
        self._active_model = active_model
        self._providers = providers or {}
        self.fail_on_overwrite = fail_on_overwrite
        self.fail_on_activate = fail_on_activate
        self.overwritten_payloads: list[dict[str, Any]] = []
        self.activated: list[tuple[str, str]] = []

    def get_active_model(self) -> ModelSlotConfig | None:
        return self._active_model

    def get_provider(self, provider_id: str) -> FakeProvider | None:
        return self._providers.get(provider_id)

    def overwrite_provider_payload(self, payload: dict[str, Any]) -> None:
        if self.fail_on_overwrite:
            raise RuntimeError(self.fail_on_overwrite)
        self.overwritten_payloads.append(payload)
        provider = FakeProvider(
            id=str(payload["id"]),
            name=str(payload.get("name") or payload["id"]),
            base_url=str(payload.get("base_url") or ""),
            api_key=str(payload.get("api_key") or ""),
            chat_model=str(payload.get("chat_model") or "OpenAIChatModel"),
            models=list(payload.get("models") or []),
            extra_models=list(payload.get("extra_models") or []),
            is_custom=bool(payload.get("is_custom")),
            generate_kwargs=dict(payload.get("generate_kwargs") or {}),
        )
        self._providers[provider.id] = provider

    async def activate_model(self, provider_id: str, model_id: str) -> None:
        if self.fail_on_activate:
            raise RuntimeError(self.fail_on_activate)
        self.activated.append((provider_id, model_id))
        self._active_model = ModelSlotConfig(
            provider_id=provider_id,
            model=model_id,
        )


def _manager_factory(manager: FakeManager):
    def get_instance(tenant_id=None):  # noqa: ANN001
        del tenant_id
        return manager

    return staticmethod(get_instance)


def _working_dir_factory(tmp_path: Path):
    def get_working_dir(tenant_id=None):  # noqa: ANN001
        return tmp_path / str(tenant_id)

    return get_working_dir


def _storage_recorder(calls: list[str | None]):
    def ensure_storage(tenant_id: str | None) -> None:
        calls.append(tenant_id)

    return staticmethod(ensure_storage)


def test_list_active_model_distribution_tenants_returns_discovered_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_logical_tenant_ids(
        _source_id=None,
        *,
        _source_filter=False,
    ):
        return ["default", "tenant-a", "tenant-b"]

    monkeypatch.setattr(
        providers_router,
        "list_logical_tenant_ids",
        fake_list_logical_tenant_ids,
    )

    result = asyncio.run(
        providers_router.list_active_model_distribution_tenants(_request()),
    )

    assert result.tenant_ids == ["default", "tenant-a", "tenant-b"]


def test_list_active_model_distribution_tenants_maps_source_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str | None] = []

    async def fake_list_logical_tenant_ids(
        source_id: str | None = None,
        *,
        _source_filter: bool = False,
    ) -> list[str]:
        observed.append(source_id)
        return ["default", "tenant-a"]

    monkeypatch.setattr(
        providers_router,
        "list_logical_tenant_ids",
        fake_list_logical_tenant_ids,
    )

    result = asyncio.run(
        providers_router.list_active_model_distribution_tenants(
            _request(source_id="ruice"),
        ),
    )

    assert observed == ["ruice"]
    assert result.tenant_ids == ["default", "tenant-a"]


def test_distribute_active_model_to_bootstrapped_tenant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_manager = FakeManager(
        active_model=ModelSlotConfig(provider_id="openai", model="gpt-5.4"),
        providers={
            "openai": FakeProvider(
                id="openai",
                name="OpenAI",
                api_key="sk-source",
                base_url="https://api.openai.com/v1",
                models=[{"id": "gpt-5.4", "name": "GPT-5.4"}],
                extra_models=[{"id": "gpt-5.4-mini", "name": "GPT-5.4 mini"}],
                generate_kwargs={"temperature": 0.2},
            ),
        },
    )
    target_manager = FakeManager()
    ensured: list[str | None] = []

    monkeypatch.setattr(
        providers_router,
        "get_tenant_working_dir_strict",
        _working_dir_factory(tmp_path),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "ensure_tenant_provider_storage",
        _storage_recorder(ensured),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "get_instance",
        _manager_factory(target_manager),
    )

    class FakeInitializer:
        def __init__(
            self,
            base_working_dir: Path,
            tenant_id: str,
            source_id: str | None = None,
        ):
            assert base_working_dir == tmp_path
            self.tenant_id = tenant_id
            self.source_id = source_id

        def has_seeded_bootstrap(self) -> bool:
            return True

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            raise AssertionError("should not bootstrap an existing tenant")

    monkeypatch.setattr(providers_router, "TenantInitializer", FakeInitializer)

    result = asyncio.run(
        providers_router.distribute_active_model(
            _request(),
            providers_router.ActiveModelDistributionRequest(
                target_tenant_ids=["tenant-existing"],
                overwrite=True,
            ),
            manager=source_manager,
        ),
    )

    assert result.source_active_llm == ModelSlotConfig(
        provider_id="openai",
        model="gpt-5.4",
    )
    assert len(result.results) == 1
    tenant_result = result.results[0]
    assert tenant_result.success is True
    assert tenant_result.bootstrapped is False
    assert tenant_result.provider_updated == "openai"
    assert tenant_result.active_llm_updated == ModelSlotConfig(
        provider_id="openai",
        model="gpt-5.4",
    )
    assert ensured == ["tenant-existing"]
    assert target_manager.overwritten_payloads[0]["api_key"] == "sk-source"
    assert target_manager.activated == [("openai", "gpt-5.4")]


def test_distribute_active_model_bootstraps_missing_tenant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_manager = FakeManager(
        active_model=ModelSlotConfig(provider_id="openai", model="gpt-5.4"),
        providers={
            "openai": FakeProvider(
                id="openai",
                models=[{"id": "gpt-5.4", "name": "GPT-5.4"}],
            ),
        },
    )
    target_manager = FakeManager()
    bootstrap_calls: list[str] = []

    monkeypatch.setattr(
        providers_router,
        "get_tenant_working_dir_strict",
        _working_dir_factory(tmp_path),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "ensure_tenant_provider_storage",
        staticmethod(lambda tenant_id: None),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "get_instance",
        staticmethod(lambda tenant_id=None: target_manager),
    )

    class FakeInitializer:
        def __init__(
            self,
            _base_working_dir: Path,
            tenant_id: str,
            source_id: str | None = None,
        ):
            self.tenant_id = tenant_id
            self.source_id = source_id

        def has_seeded_bootstrap(self) -> bool:
            return False

        def ensure_seeded_bootstrap(self) -> dict[str, object]:
            assert self.source_id == "ruice"
            bootstrap_calls.append(self.tenant_id)
            return {"minimal": True}

    monkeypatch.setattr(providers_router, "TenantInitializer", FakeInitializer)

    result = asyncio.run(
        providers_router.distribute_active_model(
            _request(source_id="ruice"),
            providers_router.ActiveModelDistributionRequest(
                target_tenant_ids=["tenant-new"],
                overwrite=True,
            ),
            manager=source_manager,
        ),
    )

    assert bootstrap_calls == ["tenant-new"]
    assert result.results[0].success is True
    assert result.results[0].bootstrapped is True


def test_distribute_active_model_overwrites_builtin_provider_and_switches_active_slot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_manager = FakeManager(
        active_model=ModelSlotConfig(provider_id="openai", model="gpt-5.4"),
        providers={
            "openai": FakeProvider(
                id="openai",
                name="OpenAI",
                api_key="sk-new",
                base_url="https://api.openai.com/v1",
                models=[{"id": "gpt-4.1", "name": "GPT-4.1"}],
                extra_models=[{"id": "gpt-5.4", "name": "GPT-5.4"}],
                generate_kwargs={"temperature": 0.3},
            ),
        },
    )
    target_manager = FakeManager(
        active_model=ModelSlotConfig(provider_id="openai", model="gpt-4.1"),
        providers={
            "openai": FakeProvider(
                id="openai",
                api_key="sk-old",
                base_url="https://old.example/v1",
                models=[{"id": "gpt-4.1", "name": "GPT-4.1"}],
            ),
        },
    )

    monkeypatch.setattr(
        providers_router,
        "get_tenant_working_dir_strict",
        _working_dir_factory(tmp_path),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "ensure_tenant_provider_storage",
        staticmethod(lambda tenant_id: None),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "get_instance",
        staticmethod(lambda tenant_id=None: target_manager),
    )
    monkeypatch.setattr(
        providers_router,
        "TenantInitializer",
        lambda base_working_dir, tenant_id, source_id=None: SimpleNamespace(
            has_seeded_bootstrap=lambda: True,
            ensure_seeded_bootstrap=lambda: {"minimal": True},
        ),
    )

    result = asyncio.run(
        providers_router.distribute_active_model(
            _request(),
            providers_router.ActiveModelDistributionRequest(
                target_tenant_ids=["tenant-builtin"],
                overwrite=True,
            ),
            manager=source_manager,
        ),
    )

    overwritten = target_manager.get_provider("openai")
    assert overwritten is not None
    assert overwritten.api_key == "sk-new"
    assert overwritten.base_url == "https://api.openai.com/v1"
    assert overwritten.has_model("gpt-5.4") is True
    assert result.results[0].active_llm_updated == ModelSlotConfig(
        provider_id="openai",
        model="gpt-5.4",
    )


def test_distribute_active_model_overwrites_custom_provider_and_switches_active_slot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_manager = FakeManager(
        active_model=ModelSlotConfig(
            provider_id="corp-gateway",
            model="claude-enterprise",
        ),
        providers={
            "corp-gateway": FakeProvider(
                id="corp-gateway",
                name="Corp Gateway",
                is_custom=True,
                api_key="secret-token",
                base_url="https://corp.example/v1",
                models=[
                    {"id": "claude-enterprise", "name": "Claude Enterprise"},
                ],
                generate_kwargs={"top_p": 0.9},
            ),
        },
    )
    target_manager = FakeManager()

    monkeypatch.setattr(
        providers_router,
        "get_tenant_working_dir_strict",
        _working_dir_factory(tmp_path),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "ensure_tenant_provider_storage",
        staticmethod(lambda tenant_id: None),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "get_instance",
        staticmethod(lambda tenant_id=None: target_manager),
    )
    monkeypatch.setattr(
        providers_router,
        "TenantInitializer",
        lambda base_working_dir, tenant_id, source_id=None: SimpleNamespace(
            has_seeded_bootstrap=lambda: True,
            ensure_seeded_bootstrap=lambda: {"minimal": True},
        ),
    )

    result = asyncio.run(
        providers_router.distribute_active_model(
            _request(),
            providers_router.ActiveModelDistributionRequest(
                target_tenant_ids=["tenant-custom"],
                overwrite=True,
            ),
            manager=source_manager,
        ),
    )

    overwritten = target_manager.get_provider("corp-gateway")
    assert overwritten is not None
    assert overwritten.is_custom is True
    assert overwritten.api_key == "secret-token"
    assert overwritten.base_url == "https://corp.example/v1"
    assert result.results[0].provider_updated == "corp-gateway"
    assert result.results[0].active_llm_updated == ModelSlotConfig(
        provider_id="corp-gateway",
        model="claude-enterprise",
    )


def test_distribute_active_model_reports_partial_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_manager = FakeManager(
        active_model=ModelSlotConfig(provider_id="openai", model="gpt-5.4"),
        providers={
            "openai": FakeProvider(
                id="openai",
                models=[{"id": "gpt-5.4", "name": "GPT-5.4"}],
            ),
        },
    )
    managers = {
        "tenant-ok": FakeManager(),
        "tenant-fail": FakeManager(fail_on_overwrite="write failed"),
    }

    monkeypatch.setattr(
        providers_router,
        "get_tenant_working_dir_strict",
        _working_dir_factory(tmp_path),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "ensure_tenant_provider_storage",
        staticmethod(lambda tenant_id: None),
    )
    monkeypatch.setattr(
        providers_router.ProviderManager,
        "get_instance",
        staticmethod(lambda tenant_id=None: managers[str(tenant_id)]),
    )
    monkeypatch.setattr(
        providers_router,
        "TenantInitializer",
        lambda base_working_dir, tenant_id, source_id=None: SimpleNamespace(
            has_seeded_bootstrap=lambda: True,
            ensure_seeded_bootstrap=lambda: {"minimal": True},
        ),
    )

    result = asyncio.run(
        providers_router.distribute_active_model(
            _request(),
            providers_router.ActiveModelDistributionRequest(
                target_tenant_ids=["tenant-ok", "tenant-fail"],
                overwrite=True,
            ),
            manager=source_manager,
        ),
    )

    assert [item.tenant_id for item in result.results] == [
        "tenant-ok",
        "tenant-fail",
    ]
    assert result.results[0].success is True
    assert result.results[1].success is False
    assert "write failed" in str(result.results[1].error)
    assert managers["tenant-ok"].activated == [("openai", "gpt-5.4")]


def test_distribute_active_model_rejects_missing_overwrite() -> None:
    source_manager = FakeManager(
        active_model=ModelSlotConfig(provider_id="openai", model="gpt-5.4"),
        providers={
            "openai": FakeProvider(
                id="openai",
                models=[{"id": "gpt-5.4", "name": "GPT-5.4"}],
            ),
        },
    )

    with pytest.raises(providers_router.HTTPException) as exc_info:
        asyncio.run(
            providers_router.distribute_active_model(
                _request(),
                providers_router.ActiveModelDistributionRequest(
                    target_tenant_ids=["tenant-a"],
                    overwrite=False,
                ),
                manager=source_manager,
            ),
        )

    assert exc_info.value.status_code == 400
    assert "overwrite=true" in str(exc_info.value.detail)
