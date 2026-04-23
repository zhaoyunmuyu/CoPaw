## Context

Cron coordination was introduced as deployment-level runtime
configuration, but the current code still models it as part of root
`config.json` and `Workspace._get_cron_coordination_config()` reads that
tenant-local file on startup. At the same time, every cron coordination
field already has an environment-backed default in `src/swe/constant.py`,
and the repository also ships `src/swe/config/envs/dev.json` and
`src/swe/config/envs/prd.json` presets.

That leaves two competing configuration paths for the same concern:
environment-derived runtime values and persisted tenant config. The
result is avoidable ambiguity in multi-instance deployments, where Redis
leadership settings are operational concerns and should not vary with a
workspace `config.json`.

## Goals / Non-Goals

**Goals:**
- Make cron coordination an environment-only runtime concern.
- Define a single effective loading chain for cron coordination values:
  environment-derived values first, hardcoded defaults last.
- Remove `cron_coordination` from root config schema and persistence so
  `config.json` stops advertising or storing those settings.
- Keep legacy `config.json` files readable during rollout without
  requiring a one-off migration command.
- Update examples and docs so operators configure cron coordination only
  through env mechanisms.

**Non-Goals:**
- Redesigning cron leadership, Redis lease semantics, or APScheduler
  behavior.
- Changing unrelated `config.json` sections or the general env bootstrap
  architecture.
- Introducing a new tenant-scoped override mechanism for cron
  coordination.
- Backfilling automatic edits into every historical `config.json` file
  outside the normal read/save flows.

## Decisions

### Decision 1: Effective cron coordination config is built from env-backed constants only

**Choice:** The runtime will construct `CoordinationConfig` from the
cron coordination constants in `src/swe/constant.py`, and those constants
remain the only source of truth for effective values.

**Rationale:**
- The constants already encode validation-friendly defaults and env
  parsing behavior.
- Redis coordination settings are deployment-level operational config,
  not tenant preferences.
- This removes a second read path that can diverge from the process
  environment and makes startup behavior deterministic.

**Alternatives considered:**
- Keep `config.json` as a lower-priority fallback: rejected because it
  preserves the ambiguity this change is trying to remove.
- Move settings to another persisted JSON file: rejected because the user
  request is to keep cron coordination on environment-derived sources and
  code defaults only.

### Decision 2: Cron coordination consumes the resolved environment pipeline, without adding a new config layer

**Choice:** Reuse the existing environment bootstrap pipeline instead of
inventing a cron-specific loader. Cron coordination will consume the
final env-backed constants exposed by `src/swe/constant.py`, with
`config.json` removed from the decision path. Supported source families
remain explicit process environment, `.env`, packaged
`src/swe/config/envs/{dev|prd}.json`, and hardcoded defaults.

**Rationale:**
- This matches the current architecture closely enough to avoid hidden
  side effects.
- Explicit runtime environment remains authoritative under the current
  bootstrap behavior.
- The change stays small: remove `config.json` from the chain rather than
  redesign the chain itself.

**Alternatives considered:**
- Reorder all env sources as part of this change: rejected because it
  widens scope beyond removing `config.json`.
- Load `envs/{dev|prd}.json` again inside cron startup: rejected because
  it duplicates bootstrap logic and risks divergence.

### Decision 3: Legacy `cron_coordination` data is tolerated on read and dropped on write

**Choice:** Remove `cron_coordination` from the `Config` model. Existing
`config.json` files may still contain that key, but `load_config()` will
ignore it and runtime code will no longer read it. Any subsequent
`save_config()` or tenant-seeding flow will serialize without the field.

**Rationale:**
- This gives backward-compatible reads during rollout.
- The cleanup becomes incremental and automatic instead of requiring a
  one-time migration tool.
- It avoids special-case migration code for a section that is being
  removed entirely.

**Alternatives considered:**
- Fail validation when legacy files still contain the field: rejected
  because it would create unnecessary rollout friction.
- Add a dedicated cleanup command: rejected because normal config writes
  already provide a safe convergence path.

### Decision 4: Workspace startup stops depending on root config for cron coordination

**Choice:** Replace the `load_config()`-based mapping in
`Workspace._get_cron_coordination_config()` with an env-only helper that
translates the constant values into `CoordinationConfig`.

**Rationale:**
- This is the narrowest code change that enforces the new source-of-truth
  rule at runtime.
- It keeps cron startup logic explicit and easy to test.
- It avoids accidental reintroduction of `config.json` dependency through
  unrelated root-config changes.

**Alternatives considered:**
- Keep the method name but internally call `load_config()`: rejected
  because it leaves the wrong dependency in place.
- Build the coordination config inline at each call site: rejected
  because a helper is easier to test and maintain.

## Risks / Trade-offs

- [Existing deployments rely on `config.json.cron_coordination`] →
  Document the removal as breaking, ignore legacy keys safely on read,
  and require operators to move values into env configuration.
- [Source precedence is misunderstood during rollout] → Document the
  environment-only chain in the spec and config examples, and remove old
  `config.json` examples.
- [A partial refactor leaves old docs or serializers behind] → Include
  documentation/example cleanup and config persistence checks in the task
  list and verification scope.
- [Tests only cover constants but not persistence cleanup] → Add tests for
  workspace startup, `load_config()` tolerance, and `save_config()`
  output that omits the legacy field.

## Migration Plan

1. Remove `cron_coordination` from the root config schema and any code
   path that maps it from `load_config()` into runtime coordination
   objects.
2. Introduce or refactor a single helper that builds
   `CoordinationConfig` from cron environment constants.
3. Update config load/save tests so legacy `cron_coordination` input is
   ignored and rewritten away on save.
4. Update environment docs and old examples to show env-only
   configuration for Redis cron coordination.
5. Deploy with cron coordination values present in env configuration for
   any cluster that previously relied on `config.json`.
6. Roll back by restoring the removed config model field and workspace
   mapping if production behavior depends on tenant-local overrides.

## Open Questions

- Should `reload_channel_prefix`, `cluster_max_connections`, and
  `cluster_skip_full_coverage_check` also gain first-class env vars in
  this change, or should they remain code defaults until a follow-up?
- Do we want a startup warning when a legacy `cron_coordination` key is
  detected in `config.json`, or is silent ignore sufficient?
