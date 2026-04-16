# Cron Cluster Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Patch the recent cron coordination commit so cluster URL parsing, cluster reload publishing, and failover takeover all behave safely at runtime.

**Architecture:** Keep the existing cron coordination design, but tighten the runtime edges. The hotfix stays local to `CronCoordination` and `CronManager`, with regression tests added in the existing cron unit suites. No structural refactor, no retry system, and no cluster strategy changes.

**Tech Stack:** Python 3.12, pytest, redis.asyncio, APScheduler

---

## File Structure

- Modify: `src/swe/app/crons/coordination.py`
  - Narrow Redis URL parsing to shared auth/SSL fields
  - Route reload publishing through `_pubsub_client`
- Modify: `src/swe/app/crons/manager.py`
  - Wrap follower takeover startup in a guarded async path
- Modify: `tests/unit/test_cron_coordination.py`
  - Add regression tests for multi-node cluster URL parsing and cluster publish path
- Modify: `tests/unit/test_cron_manager_coordination.py`
  - Add regression test for takeover startup failure cleanup

### Task 1: Add Coordination Regression Tests

**Files:**
- Modify: `tests/unit/test_cron_coordination.py`
- Test: `tests/unit/test_cron_coordination.py`

- [ ] **Step 1: Write the failing multi-node auth parsing test**

```python
    def test_cluster_url_with_auth_and_multiple_nodes(self):
        """Test auth parsing for multi-node cluster URLs."""
        from swe.app.crons.coordination import (
            CoordinationConfig,
            CronCoordination,
        )

        config = CoordinationConfig(
            enabled=True,
            cluster_mode=True,
            redis_url="rediss://user:pass@host1:6379,host2:6380",
        )

        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=config,
        )

        params = coord._parse_redis_url()
        assert params["username"] == "user"
        assert params["password"] == "pass"
        assert params["ssl"] is True
```

- [ ] **Step 2: Run the parsing test to verify it fails on the current code**

Run: `venv/bin/python -m pytest tests/unit/test_cron_coordination.py::TestCronCoordinationClusterMode::test_cluster_url_with_auth_and_multiple_nodes -v`

Expected: `FAIL` with a `ValueError` raised from `urllib.parse` port parsing.

- [ ] **Step 3: Write the failing cluster publish-path test**

```python
    @pytest.mark.asyncio
    async def test_publish_reload_uses_pubsub_client_in_cluster_mode(self):
        """Cluster mode should publish via standalone pub/sub client."""
        from unittest.mock import AsyncMock
        from swe.app.crons.coordination import (
            CoordinationConfig,
            CronCoordination,
        )

        coord = CronCoordination(
            tenant_id="test",
            agent_id="test-agent",
            config=CoordinationConfig(
                enabled=True,
                cluster_mode=True,
                redis_url="redis://host1:6379,host2:6380",
            ),
        )

        coord._redis = AsyncMock()
        coord._pubsub_client = AsyncMock()

        assert await coord.publish_reload() is True
        coord._pubsub_client.publish.assert_awaited_once()
        coord._redis.publish.assert_not_called()
```

- [ ] **Step 4: Run the publish-path test to verify it fails on the current code**

Run: `venv/bin/python -m pytest tests/unit/test_cron_coordination.py::TestCronCoordinationClusterMode::test_publish_reload_uses_pubsub_client_in_cluster_mode -v`

Expected: `FAIL` because `publish_reload()` currently calls `_redis.publish(...)`.

- [ ] **Step 5: Commit the test additions**

```bash
git add tests/unit/test_cron_coordination.py
git commit -m "test(cron): add cluster coordination regressions"
```

### Task 2: Fix Cluster Coordination Runtime Paths

**Files:**
- Modify: `src/swe/app/crons/coordination.py`
- Test: `tests/unit/test_cron_coordination.py`

- [ ] **Step 1: Implement auth-only Redis URL parsing**

```python
    def _parse_redis_url(self) -> dict:
        """Parse redis_url to extract shared connection parameters."""
        import urllib.parse

        url = self._config.redis_url
        parsed = urllib.parse.urlparse(url)

        return {
            "username": parsed.username,
            "password": parsed.password,
            "ssl": parsed.scheme == "rediss",
            "db": 0,
        }
```

- [ ] **Step 2: Route reload publishing through the pub/sub client**

```python
    async def publish_reload(self) -> bool:
        """Publish a reload signal.

        Can be called from any instance (leader or follower).
        """
        client = self._pubsub_client or self._redis
        if client is None:
            return False

        publisher = ReloadPublisher(
            redis_client=client,
            config=self._config,
        )
        return await publisher.publish(self._tenant_id, self._agent_id)
```

- [ ] **Step 3: Run the focused coordination tests**

Run: `venv/bin/python -m pytest tests/unit/test_cron_coordination.py -q`

Expected: the new parsing and publish-path tests pass, and existing coordination tests remain green or skipped based on Redis availability.

- [ ] **Step 4: Commit the coordination hotfix**

```bash
git add src/swe/app/crons/coordination.py tests/unit/test_cron_coordination.py
git commit -m "fix(cron): harden cluster coordination hotfix"
```

### Task 3: Add Takeover Failure Regression Test

**Files:**
- Modify: `tests/unit/test_cron_manager_coordination.py`
- Test: `tests/unit/test_cron_manager_coordination.py`

- [ ] **Step 1: Write the failing follower takeover startup failure test**

```python
    @pytest.mark.asyncio
    async def test_become_leader_start_failure_triggers_deactivate(
        self,
        temp_jobs_file,
        mock_runner,
        mock_channel_manager,
    ):
        manager = CronManager(
            repo=JsonJobRepository(temp_jobs_file),
            runner=mock_runner,
            channel_manager=mock_channel_manager,
        )
        await manager.initialize()

        with patch.object(manager, "_do_start", AsyncMock(side_effect=RuntimeError("boom"))):
            with patch.object(manager, "deactivate", AsyncMock()) as mock_deactivate:
                manager._on_become_leader()
                await asyncio.sleep(0)
                await asyncio.sleep(0)

        mock_deactivate.assert_awaited_once()
```

- [ ] **Step 2: Run the takeover failure test to verify it fails on the current code**

Run: `venv/bin/python -m pytest tests/unit/test_cron_manager_coordination.py::TestCronManagerFailover::test_become_leader_start_failure_triggers_deactivate -v`

Expected: `FAIL` because the current callback lets `_do_start()` raise in a background task and never calls `deactivate()`.

- [ ] **Step 3: Commit the manager regression test**

```bash
git add tests/unit/test_cron_manager_coordination.py
git commit -m "test(cron): add failover startup regression"
```

### Task 4: Fix Takeover Startup Failure Handling

**Files:**
- Modify: `src/swe/app/crons/manager.py`
- Test: `tests/unit/test_cron_manager_coordination.py`

- [ ] **Step 1: Add a guarded async startup helper**

```python
    async def _start_after_leadership_change(self) -> None:
        """Start the scheduler after becoming leader via candidate loop."""
        try:
            await self._do_start()
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Failed to start after becoming leader: agent=%s",
                self._agent_id,
            )
            await self.deactivate()
```

- [ ] **Step 2: Switch the callback to the guarded helper**

```python
    def _on_become_leader(self) -> None:
        """Callback invoked when this instance becomes leader via candidate loop."""
        logger.info(
            "Become leader callback invoked, starting scheduler: agent=%s",
            self._agent_id,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._start_after_leadership_change())
        except RuntimeError:
            logger.warning(
                "Cannot schedule start: no event loop (agent=%s)",
                self._agent_id,
            )
```

- [ ] **Step 3: Run the focused manager tests**

Run: `venv/bin/python -m pytest tests/unit/test_cron_manager_coordination.py -q`

Expected: the new takeover failure test passes, and existing failover tests remain green or skipped based on Redis availability.

- [ ] **Step 4: Commit the manager hotfix**

```bash
git add src/swe/app/crons/manager.py tests/unit/test_cron_manager_coordination.py
git commit -m "fix(cron): release leadership on takeover start failure"
```

### Task 5: Full Verification

**Files:**
- Modify: `src/swe/app/crons/coordination.py`
- Modify: `src/swe/app/crons/manager.py`
- Modify: `tests/unit/test_cron_coordination.py`
- Modify: `tests/unit/test_cron_manager_coordination.py`

- [ ] **Step 1: Run the target cron unit suite**

Run: `venv/bin/python -m pytest tests/unit/test_cron_coordination.py tests/unit/test_cron_manager_coordination.py -q`

Expected: all non-Redis-dependent tests pass; Redis-dependent tests either pass or skip cleanly when Redis is unavailable.

- [ ] **Step 2: Inspect the final diff**

Run: `git diff --stat HEAD~4..HEAD`

Expected: only the cron coordination files and their matching tests are included.

- [ ] **Step 3: Create the final integration commit if the worker used fixup commits**

```bash
git add src/swe/app/crons/coordination.py src/swe/app/crons/manager.py tests/unit/test_cron_coordination.py tests/unit/test_cron_manager_coordination.py
git commit -m "fix(cron): close cluster coordination regressions"
```

## Self-Review

- Spec coverage: the plan includes one task for each reviewed regression and one final verification task.
- Placeholder scan: all code-touching steps include concrete snippets and exact commands.
- Type consistency: method names match the current codebase and the approved design:
  - `CronCoordination._parse_redis_url`
  - `CronCoordination.publish_reload`
  - `CronManager._on_become_leader`
  - `CronManager._start_after_leadership_change`
