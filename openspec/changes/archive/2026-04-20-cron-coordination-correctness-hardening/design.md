## Context

The repository already contains a completed `redis-coordinated-cron-leadership` change. That change introduced:

- a Redis lease keyed by `tenant + agent` so only one instance activates scheduling
- reload pub/sub so the active leader can rebuild local schedules after cron definition changes

That foundation is directionally correct, but the current implementation still falls short of strict correctness for multi-tenant, multi-instance cron execution:

- the default execution semantics at failover boundaries are not explicit
- the prior capability contract still describes Redis execution-lock de-duplication as the default timed execution guarantee, which no longer matches the intended hardening direction
- cron execution does not yet have a standard preflight lease validation step immediately before work performs side effects
- `jobs.json` mutations still use shared file replacement without cross-instance serialization
- reload propagation is not self-healing when pub/sub delivery fails

This change keeps the current stage-one architecture: Redis for coordination and `jobs.json` for durable cron definitions. The goal is to make the default execution model explicit, reduce obvious stale-leader executions, and fix definition consistency without folding in the larger MySQL migration planned in `mysql-cron-definition-storage`.

## Goals / Non-Goals

**Goals:**
- Ensure exactly one instance at a time owns cron scheduling for a given `tenant + agent` in steady state.
- Ensure timed cron and heartbeat execution re-validates lease ownership immediately before work performs side effects.
- Make the default multi-instance execution semantics explicit: steady-state single leader and at-least-once behavior at failover boundaries.
- Require cron handlers to remain safe under that default model by treating idempotency as part of the contract.
- Ensure concurrent cron definition mutations across instances do not overwrite one another while `jobs.json` remains authoritative.
- Ensure the active leader eventually converges to the latest cron definition state even if Redis reload pub/sub delivery fails.
- Preserve current manual `run_job` behavior as an explicit extra execution outside timed scheduler ownership.

**Non-Goals:**
- Migrating cron definitions from `jobs.json` to MySQL in this change.
- Redesigning the broader runtime state model outside cron and heartbeat.
- Making in-memory job execution state globally authoritative across pods.
- Changing operator-visible semantics of manual `run_job`.
- Providing strict exactly-once or per-tick unique execution guarantees for every scheduled workload in this change.

## Decisions

### Decision 1: `tenant + agent` lease remains the default coordination boundary

**Choice:** Keep Redis cron leadership at the `tenant + agent` level and treat that lease as the default ownership mechanism for all scheduled workloads in that workspace.

**Rationale:**
- The current scheduler lifecycle is already organized around a workspace/agent-level manager.
- A single leader per tenant-agent is enough to prevent duplicate hot schedulers in steady state.
- This keeps cron coordination independent of schedule type, so ordinary cron and interval-style workloads share the same ownership model.

**Alternatives considered:**
- Move ownership to per-job or per-tick leader election: stronger isolation, but much more complex and unnecessary for the default stage-one model.

### Decision 2: Timed execution SHALL perform lease preflight validation immediately before work starts

**Choice:** Every scheduler-originated cron or heartbeat execution re-checks that the local instance still owns the tenant-agent lease immediately before starting the actual unit of work.

**Rationale:**
- The scheduler callback may already be queued locally even after ownership has changed.
- A preflight check reduces obvious stale-leader executions without introducing schedule-type-specific tick identity machinery.
- This applies equally to ordinary cron and interval workloads.

**Alternatives considered:**
- Rely on scheduler ownership only with no execution-time validation: simpler, but allows more stale-leader work to continue after ownership has changed.

### Decision 3: Default failover semantics are at-least-once, so handlers MUST be idempotent

**Choice:** Define the default multi-instance execution contract as:

- one active leader in steady state
- execution preflight before work starts
- possible duplicate execution at failover boundaries
- handler idempotency required for scheduler-originated workloads

Stronger guarantees such as per-tick de-duplication or fencing are follow-up extensions for high-risk tasks rather than the default platform contract.

This decision explicitly replaces the earlier execution-lock-centric default contract in `redis-coordinated-cron-leadership`. Existing config descriptions, comments, and tests must therefore stop describing Redis timed execution locks as the default correctness mechanism.

**Rationale:**
- Lease preflight reduces but does not eliminate the window between ownership validation and actual external side effects.
- Idempotent handlers are the simplest and most robust default safety mechanism across both cron and interval scheduling.
- This keeps the platform contract honest instead of implying exactly-once semantics it does not provide.

**Alternatives considered:**
- Attempt to guarantee strict once-per-tick execution for all schedules now: possible, but significantly more complex and not required for the default stage-one model.

### Decision 4: `jobs.json` mutations need Redis-backed definition serialization

**Choice:** Add a Redis definition lock keyed by `tenant + agent` around cron definition mutations while `jobs.json` remains authoritative.

**Rationale:**
- Current `load -> modify -> save` mutation semantics are not cross-instance safe.
- Serializing mutations at the tenant-agent definition boundary avoids overwrite races without forcing an immediate database migration.
- The lock scope matches the ownership scope of the cron definition file.

**Alternatives considered:**
- Keep file writes unlocked and accept overwrite risk until MySQL migration: too risky for multi-instance correctness claims.
- Introduce per-job file-level locking only: insufficient because the file is mutated as one aggregate document.

### Decision 5: Definition convergence requires both pub/sub and version-based reconciliation

**Choice:** Maintain a Redis-backed definition version per `tenant + agent`, increment it after successful mutations, include it in reload signaling, and let the leader periodically reconcile observed version against local version.

**Rationale:**
- Pub/sub is useful for low-latency propagation but is not sufficient as the only convergence path.
- A monotonically increasing version gives the leader a cheap way to detect missed reloads and self-heal.
- This preserves the current stage-one architecture while removing the permanent stale-schedule failure mode.

**Alternatives considered:**
- Keep pub/sub only: simplest, but a failed publish can leave the leader stale indefinitely.
- Poll `jobs.json` mtimes from every instance: weaker semantics and more filesystem coupling than a Redis version.

### Decision 6: Manual `run_job` remains outside timed scheduler ownership

**Choice:** Preserve current manual execution behavior and document that the leader lease and preflight rules apply to scheduler-originated runs, not to explicit operator-triggered manual runs.

**Rationale:**
- Manual run is an operator command meaning "run now in addition to schedule".
- Forcing manual runs into lease-governed scheduler semantics changes behavior and could silently drop requested executions.
- This change is about correctness of scheduled execution, not redefining manual operations.

**Alternatives considered:**
- Route manual runs through scheduler ownership controls: would change semantics and reduce operator control.

## Key Design Elements

### Redis key model

Leader lease:

```text
swe:cron:lease:{tenant}:{agent}
```

Definition mutation lock:

```text
swe:cron:deflock:{tenant}:{agent}
```

Definition version:

```text
swe:cron:defver:{tenant}:{agent}
```

### Timed execution flow

1. Scheduler fires a timed cron callback on the current leader.
2. The callback performs a preflight lease validation against the `tenant + agent` ownership key.
3. If lease ownership is no longer valid, the callback skips execution immediately.
4. If lease ownership is still valid, the callback starts the actual unit of work.

This does not make execution strictly unique at failover boundaries, but it narrows the stale-leader window and makes ownership validation explicit.

### Heartbeat execution flow

1. Heartbeat scheduling remains leader-owned.
2. Heartbeat callback performs the same preflight lease validation immediately before starting work.
3. If ownership is lost, heartbeat is skipped.
4. If ownership is still valid, heartbeat runs normally.

Heartbeat and ordinary cron jobs therefore share the same default ownership semantics regardless of whether their schedule is cron-like or interval-like.

Heartbeat configuration convergence is a separate concern from `jobs.json` definition convergence. Heartbeat settings currently live in agent config rather than `jobs.json`, so heartbeat config changes continue to rely primarily on the existing agent-config watcher and reschedule flow, while this change's definition version/reconcile path covers `jobs.json`-backed cron definitions.

### Idempotent handler contract

Scheduler-originated handlers MUST be safe under at-least-once execution semantics.

In practice, that means:

- external writes should be naturally idempotent or keyed by a stable business identifier
- state refresh tasks should overwrite or reconcile rather than append blindly
- notification-like tasks should either tolerate duplicates or use downstream deduplication keys

This contract is part of the runtime model, not just an implementation detail.

### Definition mutation flow

Every code path that durably mutates `jobs.json` for a tenant-agent workspace MUST use the same serialized flow, not just HTTP API mutation handlers.

Covered write paths include:

- API-driven create, replace, delete, pause, and resume operations
- manager-internal corrective writes such as auto-disabling invalid jobs discovered during startup or reload

Serialized mutation sequence:

1. Acquire Redis definition lock for `tenant + agent`.
2. Load and mutate `jobs.json`.
3. Save the updated file.
4. Increment the Redis definition version.
5. Release the definition lock.
6. Publish a reload signal that includes the new version.

This preserves file-backed definitions but removes cross-instance mutation races.

### Leader reload convergence

The active leader tracks the latest applied definition version.

- On reload signal: compare the signaled or observed Redis version against local applied version and reload when newer.
- On periodic reconcile: compare Redis definition version against local applied version and reload when newer even if pub/sub delivery was missed.

This makes reload propagation eventually consistent with self-healing behavior.

## Risks / Trade-offs

- [Failover boundary duplicates remain possible] -> Lease preflight reduces but does not eliminate the possibility of duplicate side effects if ownership changes after validation.
- [Idempotency burden moves to handlers] -> The platform contract becomes simpler, but task authors must understand and respect at-least-once execution semantics.
- [More Redis primitives] -> The change adds more coordination state in Redis, but each key has a narrow, auditable responsibility.
- [`jobs.json` remains stage-one authority] -> This still leaves file-backed definitions as a temporary architecture choice, but now with mutation serialization and reload convergence guarantees.
- [Local job state remains in-memory] -> Cross-instance execution history is still not a durable global truth; this change is limited to execution correctness and definition consistency.

## Migration Plan

1. Add explicit lease preflight validation for scheduler-originated cron and heartbeat execution.
2. Remove or bypass the current timeout-based execution lock from the default timed execution path.
3. Update config descriptions, implementation comments, and tests so execution locking no longer describes the default timed execution contract.
4. Add Redis definition lock and version support for cron definition mutations.
5. Update every `jobs.json` mutation path, including API mutations and manager-internal corrective writes, to use serialized mutation + version bump + reload publish.
6. Add leader-side version reconcile so reload convergence does not depend solely on pub/sub.
7. Expand tests to cover stale-leader preflight skips, failover behavior under idempotent semantics, concurrent mutation, missed reload recovery, tenant isolation, and any retained execution-lock legacy behavior if it remains exposed.

## Open Questions

- Should definition version reconcile run only on leaders, or also on followers for faster takeovers after leadership acquisition?
- Should we introduce an explicit task-level execution mode later (`default`, `dedup`, `fenced`) for high-risk non-idempotent workloads?
- Do we want new observability counters for stale-leader skips, definition reconcile reloads, and lease-loss-induced heartbeat skips in this change or a follow-up?
