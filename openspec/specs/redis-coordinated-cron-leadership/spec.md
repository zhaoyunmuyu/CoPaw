# redis-coordinated-cron-leadership Specification

## Purpose
TBD - created by archiving change redis-coordinated-cron-leadership. Update Purpose after archive.

## MODIFIED Requirements

### Requirement: Cron scheduling ownership is single-active per tenant-agent workspace
The backend SHALL coordinate cron scheduling through Redis so that, in steady state, at most one instance at a time actively schedules cron and heartbeat jobs for a given tenant-agent workspace.

#### Scenario: Only the leader activates scheduling
- **WHEN** multiple backend instances load the same tenant-agent workspace
- **THEN** the backend SHALL allow only the instance holding the Redis agent lease to activate local cron scheduling for that workspace

#### Scenario: Followers stay passive
- **WHEN** an instance does not hold the Redis agent lease for a tenant-agent workspace
- **THEN** the backend SHALL keep that workspace's cron subsystem passive and MUST NOT run scheduled cron or heartbeat callbacks for that workspace

#### Scenario: Leadership failover re-establishes scheduling
- **WHEN** the current leader loses its Redis lease or exits and another instance acquires the lease
- **THEN** the new leader SHALL rebuild local scheduling state from the shared cron definition store and resume future scheduled execution for that workspace

### Requirement: Timed cron execution is de-duplicated across instances
This requirement is replaced for the default execution mode. The backend SHALL NOT require a Redis execution lock as the default correctness mechanism for scheduler-originated timed cron or heartbeat triggers. Instead, the backend SHALL use lease ownership plus execution-time preflight validation, and duplicate execution MAY still occur at failover boundaries.

#### Scenario: Stale leader skips instead of relying on timed execution lock
- **WHEN** a scheduler-originated timed callback is about to start on an instance that has already lost the tenant-agent lease
- **THEN** the backend SHALL skip the workload instead of depending on a Redis timed execution lock to suppress it

#### Scenario: Failover boundary may still duplicate a timed run
- **WHEN** ownership changes after one instance has validated the lease but before its side effects are fully completed
- **THEN** another leader MAY execute the same timed workload again
- **AND** correctness SHALL rely on handler idempotency rather than platform-level exactly-once de-duplication

### Requirement: Manual job execution remains an explicit extra run
The backend SHALL preserve manual `run_job` behavior as an explicit one-shot execution outside scheduler-originated ownership enforcement.

#### Scenario: Manual run bypasses scheduler ownership enforcement
- **WHEN** an operator manually triggers `run_job` for a cron job
- **THEN** the backend SHALL execute that manual run without requiring the scheduler-originated lease preflight path

#### Scenario: Manual run may overlap with a scheduled run
- **WHEN** a manual `run_job` request occurs while the same job is already executing from a scheduled trigger
- **THEN** the backend SHALL treat the manual run as a separate explicit execution rather than suppressing it as a duplicate timed run

### Requirement: Cron mutations notify the active leader to reload
The backend SHALL serialize durable `jobs.json` mutations per tenant-agent workspace, advance a monotonic definition version after each successful serialized mutation, and ensure the active leader converges to that latest version even if Redis pub/sub delivery is missed.

#### Scenario: Successful cron mutation advances definition version and notifies reload
- **WHEN** any backend instance successfully creates, updates, pauses, resumes, deletes, or otherwise durably rewrites a cron definition in the shared cron definition store for a tenant-agent workspace
- **THEN** the backend SHALL advance the tenant-agent cron definition version
- **AND** the backend SHALL publish a reload signal for that tenant-agent workspace so the active leader refreshes its local schedule

#### Scenario: Failed cron mutation does not publish reload or advance version
- **WHEN** a cron definition mutation fails before it is durably written to the shared cron definition store
- **THEN** the backend SHALL NOT publish a reload signal for that failed mutation
- **AND** the backend SHALL NOT advance the tenant-agent cron definition version

#### Scenario: Missed reload delivery is recovered by reconcile
- **WHEN** a cron definition mutation succeeds but the corresponding reload pub/sub message is not delivered to the active leader
- **THEN** the active leader SHALL still reload to the latest definition version via reconciliation

## ADDED Requirements

### Requirement: Scheduler-originated execution SHALL re-validate ownership before work starts
The system SHALL perform a preflight ownership validation immediately before scheduler-originated cron or heartbeat work starts. If the local instance no longer owns the tenant-agent lease, the work MUST be skipped.

#### Scenario: Stale leader skips work after lease loss
- **WHEN** a scheduler callback is about to start work on an instance that has lost the tenant-agent lease
- **THEN** the callback MUST skip execution instead of starting the workload

### Requirement: Default failover semantics SHALL be at-least-once and require idempotent handlers
The system SHALL treat scheduler-originated workloads as operating under at-least-once semantics at failover boundaries. Cron and heartbeat handlers MUST therefore be safe to re-run without causing incorrect business effects.

#### Scenario: Failover boundary allows safe duplicate execution
- **WHEN** ownership changes after one instance has validated the lease but before its side effects are fully completed
- **THEN** the system MAY execute the same workload again on the new leader, and correctness MUST rely on handler idempotency rather than strict platform-level uniqueness

### Requirement: Cron definition mutation SHALL be serialized per tenant-agent while jobs.json remains authoritative
The system SHALL serialize every durable `jobs.json` mutation for the same tenant-agent workspace before updating `jobs.json`. Concurrent mutations from different backend instances, including manager-internal corrective writes, MUST NOT overwrite one another while file-backed cron definitions remain the source of truth.

#### Scenario: Concurrent create operations preserve both jobs
- **WHEN** two instances concurrently create different cron jobs for the same tenant-agent workspace
- **THEN** the resulting authoritative cron definition set MUST contain both jobs after both operations complete

#### Scenario: Concurrent update and delete operations do not silently drop unrelated changes
- **WHEN** one instance updates a cron job while another instance deletes a different cron job in the same tenant-agent workspace
- **THEN** the final authoritative cron definition set MUST reflect both mutations without restoring stale content from an earlier file snapshot

### Requirement: Redis coordination failures fail safe for scheduling
The backend SHALL stop active scheduling when leadership can no longer be renewed safely rather than continuing unsafely without confirmed lease ownership.

#### Scenario: Lease renewal failure deactivates scheduling
- **WHEN** the active leader cannot renew its Redis agent lease within the configured failure threshold
- **THEN** the backend SHALL deactivate local cron scheduling for that tenant-agent workspace

#### Scenario: Redis outage does not promote a follower without a lease
- **WHEN** a follower instance cannot reach Redis to establish confirmed lease ownership
- **THEN** the backend SHALL keep cron scheduling inactive for that tenant-agent workspace

### Requirement: Support Redis Cluster mode for high availability
The backend SHALL support Redis Cluster mode as an alternative to standalone Redis for cron coordination, enabling high-availability deployments.

#### Scenario: Redis Cluster mode configuration
- **WHEN** cron coordination is configured with `cluster_mode: true`
- **THEN** the backend SHALL connect to a Redis Cluster using the configured cluster nodes
- **AND** all coordination operations (lease acquisition, execution locks, pub/sub) SHALL work with the cluster

#### Scenario: Cluster node failover
- **WHEN** the connected Redis Cluster node becomes unavailable
- **THEN** the Redis client library SHALL automatically failover to another available node in the cluster
- **AND** cron coordination SHALL continue operating without interruption (may experience brief delays during failover)

#### Scenario: Standalone Redis backward compatibility
- **WHEN** cron coordination is configured with `cluster_mode: false` (default)
- **THEN** the backend SHALL connect to a standalone Redis instance using the configured `redis_url`
- **AND** existing deployments without cluster support SHALL continue to work
