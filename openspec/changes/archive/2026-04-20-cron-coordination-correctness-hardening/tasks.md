## 1. Make lease ownership the explicit default execution gate

- [x] 1.1 Add explicit lease preflight validation helpers in `src/swe/app/crons/coordination.py` for scheduler-originated work
- [x] 1.2 Update `src/swe/app/crons/manager.py` timed scheduler callbacks so cron jobs and heartbeat re-check lease ownership immediately before starting work
- [x] 1.3 Remove or bypass the current timeout-based execution lock from the default timed execution path, and update any remaining lock-related runtime surfaces so they are either removed or clearly marked non-default/legacy
- [x] 1.4 Preserve manual `run_job` as an explicit extra execution path outside scheduler ownership semantics

## 2. Establish the default at-least-once handler contract

- [x] 2.1 Document in code comments and implementation-facing docs that scheduler-originated handlers run under at-least-once failover semantics and therefore must be idempotent
- [x] 2.2 Ensure heartbeat and ordinary cron jobs share the same lease-preflight behavior regardless of schedule type
- [x] 2.3 Add logging and state handling for stale-leader preflight skips so failover behavior is observable

## 3. Serialize cron definition mutation while `jobs.json` remains authoritative

- [x] 3.1 Add Redis-backed definition lock and definition version helpers in `src/swe/app/crons/coordination.py`
- [x] 3.2 Refactor every `jobs.json` mutation path in `src/swe/app/crons/manager.py` and `src/swe/app/crons/api.py`, including manager-side auto-disable/corrective writes, so mutations execute under the definition lock, bump definition version after successful save, and publish reload after lock release
- [x] 3.3 Keep current file-backed repository boundaries intact in `src/swe/app/crons/repo/base.py` and `src/swe/app/crons/repo/json_repo.py`, with mutation coordination handled above the repository layer

## 4. Add reload self-healing and verification

- [x] 4.1 Add leader-side definition version tracking and periodic reconcile in `src/swe/app/crons/manager.py` or `src/swe/app/crons/coordination.py` so missed pub/sub reloads still converge
- [x] 4.2 Add tests covering stale-leader preflight skips, failover behavior under at-least-once semantics, concurrent definition mutation, missed reload recovery, and tenant isolation
- [x] 4.3 Update configuration descriptions, implementation-facing documentation/comments, and test names/assertions where needed so the default cron coordination model no longer advertises execution-lock de-duplication as the active contract
- [x] 4.4 Document in implementation-facing comments/docs that heartbeat config changes still converge via agent config watcher/reschedule flow rather than the `jobs.json` definition version path
