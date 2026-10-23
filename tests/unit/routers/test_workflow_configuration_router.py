# -*- coding: utf-8 -*-
"""Workflow 配置可独立提供，不要求挂载旧任务管理接口。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_standalone_workflow_configuration_keeps_existing_path():
    from swe.app.crons.workflow.api import router, get_workflow_binding
    from swe.app.crons.workflow.models import WorkflowConfig

    paths = {
        (route.path, tuple(sorted(route.methods))) for route in router.routes
    }
    assert ("/cron/workflow-bindings/{skill_id}", ("GET",)) in paths
    assert ("/cron/workflow-bindings/{skill_id}", ("PUT",)) in paths
    store = SimpleNamespace(
        resolve_first_skill=AsyncMock(side_effect=ValueError("missing")),
    )
    request = SimpleNamespace(
        headers={"X-User-Role": "manager"},
        state=SimpleNamespace(source_id="bank"),
        app=SimpleNamespace(
            state=SimpleNamespace(workflow_config_store=store),
        ),
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as failure:
        await get_workflow_binding("skill", request)
    assert failure.value.status_code == 404
