# -*- coding: utf-8 -*-
"""Tenant-scoped skill pool router tests."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.agents.skills_manager import get_skill_pool_dir, reconcile_pool_manifest
from swe.app.routers import skills as skills_router


def _request(tenant_id: str | None = "tenant-a") -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(tenant_id=tenant_id))


def _write_skill(skill_dir: Path, description: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            f"---\nname: {skill_dir.name}\n"
            f"description: {description}\n---\n"
        ),
        encoding="utf-8",
    )


def test_list_pool_skills_passes_tenant_working_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_dir = tmp_path / "tenant-a"
    observed: dict[str, Path] = {}

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tenant_dir,
    )

    def fake_build_pool_skill_specs(*, working_dir: Path) -> list[object]:
        observed["working_dir"] = working_dir
        return []

    monkeypatch.setattr(
        skills_router,
        "_build_pool_skill_specs",
        fake_build_pool_skill_specs,
    )

    result = asyncio.run(skills_router.list_pool_skills(_request()))

    assert result == []
    assert observed["working_dir"] == tenant_dir


def test_list_pool_skills_returns_tenant_local_results(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_a_dir = tmp_path / "tenant-a"
    tenant_b_dir = tmp_path / "tenant-b"
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_a_dir) / "alpha",
        "tenant-a skill",
    )
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_b_dir) / "beta",
        "tenant-b skill",
    )
    reconcile_pool_manifest(working_dir=tenant_a_dir)
    reconcile_pool_manifest(working_dir=tenant_b_dir)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    tenant_a = asyncio.run(skills_router.list_pool_skills(_request("tenant-a")))
    tenant_b = asyncio.run(skills_router.list_pool_skills(_request("tenant-b")))

    assert [skill.name for skill in tenant_a] == ["alpha"]
    assert [skill.name for skill in tenant_b] == ["beta"]


def test_update_pool_skill_config_uses_tenant_manifest_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_dir = tmp_path / "tenant-a"
    observed: dict[str, Path] = {}

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tenant_dir,
    )

    def fake_get_pool_skill_manifest_path(
        *,
        working_dir: Path,
    ) -> Path:
        observed["working_dir"] = working_dir
        return tenant_dir / "skill_pool" / "skill.json"

    monkeypatch.setattr(
        skills_router,
        "get_pool_skill_manifest_path",
        fake_get_pool_skill_manifest_path,
    )
    monkeypatch.setattr(
        skills_router,
        "_mutate_json",
        lambda path, default, mutator: True,
    )

    result = asyncio.run(
        skills_router.update_pool_skill_config(
            "demo",
            skills_router.SkillConfigRequest(config={"x": 1}),
            _request(),
        ),
    )

    assert result == {"updated": True}
    assert observed["working_dir"] == tenant_dir


def test_update_pool_skill_config_only_mutates_current_tenant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tenant_a_dir = tmp_path / "tenant-a"
    tenant_b_dir = tmp_path / "tenant-b"
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_a_dir) / "shared",
        "tenant-a skill",
    )
    _write_skill(
        get_skill_pool_dir(working_dir=tenant_b_dir) / "shared",
        "tenant-b skill",
    )
    reconcile_pool_manifest(working_dir=tenant_a_dir)
    reconcile_pool_manifest(working_dir=tenant_b_dir)

    monkeypatch.setattr(
        skills_router,
        "get_tenant_working_dir_strict",
        lambda tenant_id=None: tmp_path / str(tenant_id),
    )

    updated = asyncio.run(
        skills_router.update_pool_skill_config(
            "shared",
            skills_router.SkillConfigRequest(config={"tenant": "a"}),
            _request("tenant-a"),
        ),
    )
    tenant_a_config = asyncio.run(
        skills_router.get_pool_skill_config("shared", _request("tenant-a")),
    )
    tenant_b_config = asyncio.run(
        skills_router.get_pool_skill_config("shared", _request("tenant-b")),
    )

    assert updated == {"updated": True}
    assert tenant_a_config == {"config": {"tenant": "a"}}
    assert tenant_b_config == {"config": {}}
