## Why

SWE already has a `redis-coordinated-cron-leadership` change that makes cron scheduling single-active at the `tenant + agent` level. That solves duplicate scheduler ownership, but the current implementation still has correctness gaps:

- the current cron coordination story does not clearly define the default execution semantics at leader failover boundaries
- the implementation lacks a standard preflight ownership validation step before cron work actually performs side effects
- cron definition writes still use shared `jobs.json` replacement semantics without cross-instance mutation serialization
- reload propagation is still best-effort pub/sub only, so a failed publish can leave the active leader running stale schedule state

These gaps mean the current system is only partially specified for multi-tenant, multi-instance cron execution. We need a hardening change that preserves the current Redis + `jobs.json` stage-one architecture while making the default execution model explicit and improving definition consistency.

## What Changes

- Keep cron ownership at the `tenant + agent` level and make that lease the default coordination boundary for all scheduled workloads in the workspace.
- Add a standard execution preflight that re-validates lease ownership immediately before timed cron or heartbeat work performs side effects.
- Define the default multi-instance execution semantics as steady-state single leader with at-least-once behavior at failover boundaries, and require cron handlers to be idempotent under that model.
- Explicitly modify the prior capability contract so Redis execution-lock de-duplication is no longer described as the default timed execution guarantee.
- Add Redis-backed definition mutation coordination for `jobs.json` writes so concurrent API mutations and manager-internal corrective writes cannot overwrite one another.
- Add a definition version signal and leader-side reconcile loop so schedule state converges even if Redis reload pub/sub delivery fails.
- Preserve current manual `run_job` semantics as an explicit extra execution outside the timed scheduler ownership path.
- Keep `jobs.json` as the authoritative cron definition store in this stage; database-backed cron definition storage remains a separate follow-up change.
- Explicitly leave stronger execution guarantees such as per-tick de-duplication or fencing as follow-up work for high-risk non-idempotent tasks.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `redis-coordinated-cron-leadership`: Change the default cron coordination contract from Redis execution-lock de-duplication to lease preflight plus at-least-once/idempotent semantics, while adding serialized definition mutation and reload convergence under multi-instance operation.

## Impact

- Affected cron coordination paths: `src/swe/app/crons/coordination.py`, `src/swe/app/crons/manager.py`
- Affected cron API mutation paths: `src/swe/app/crons/api.py`
- Affected verification scope: cron coordination tests, tenant cron isolation tests, heartbeat coordination tests, idempotent failover behavior tests
- Redis remains required for coordinated cron deployments; `jobs.json` remains the durable definition store in this stage
- This change complements but does not replace future MySQL-backed cron definition storage work
