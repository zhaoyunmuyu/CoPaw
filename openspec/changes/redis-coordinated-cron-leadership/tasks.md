## 1. Add Redis cron coordination primitives

- [x] 1.1 Introduce a Redis-backed coordination module for tenant-agent cron lease acquisition, renewal, release, and reload pub/sub
- [x] 1.2 Add timed job execution lock support for scheduler-originated cron triggers with TTL derived from cron timeout configuration
- [x] 1.3 Add configuration plumbing and dependency wiring for Redis cron coordination without changing non-cron runtime ownership

## 2. Refactor cron lifecycle around active leadership

- [x] 2.1 Refactor `CronManager` to support passive initialization plus explicit activate, deactivate, and reload-from-repo transitions
- [x] 2.2 Add a workspace-scoped cron leadership controller that elects leadership per `tenant + agent` and drives `CronManager` activation state
- [x] 2.3 Ensure heartbeat scheduling is owned by the active leader only and stops promptly when lease ownership is lost

## 3. Wire cron mutation and execution semantics

- [x] 3.1 Update cron mutation paths to publish Redis reload signals only after successful `jobs.json` writes
- [x] 3.2 Route timed scheduler callbacks through the execution lock while preserving manual `run_job` as an explicit extra execution
- [x] 3.3 Add logging and state handling for lease loss, follower passivity, skipped duplicate timed runs, and leader-triggered reloads

## 4. Verify multi-instance cron behavior

- [x] 4.1 Add unit tests for lease election, renewal failure, activation/deactivation, and reload debounce behavior
- [x] 4.2 Add unit tests for timed execution lock semantics and manual `run_job` bypass behavior
- [x] 4.3 Add integration tests covering two-instance leadership, failover, timed de-duplication, and reload propagation from a follower mutation
