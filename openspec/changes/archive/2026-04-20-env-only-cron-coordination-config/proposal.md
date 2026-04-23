## Why

Cron coordination already has import-time defaults in
`src/swe/constant.py`, but the runtime still exposes and reads a second
source from `config.json.cron_coordination`. That split makes the loading
path harder to reason about and leaves deployment-wide Redis settings in
tenant-local config files even though they are operational configuration.

## What Changes

- Remove `cron_coordination` from the root `config.json` schema and stop
  reading cron coordination settings from `config.json`.
- Treat cron coordination as environment-derived runtime configuration
  only: `.env`, process environment, packaged `envs/{dev|prd}.json`
  defaults, and hardcoded defaults in code.
- Refactor workspace cron startup so effective coordination settings are
  built directly from environment-backed constants instead of
  `load_config()`.
- Ignore legacy `cron_coordination` keys when loading existing
  `config.json` files and stop writing that section back on save or tenant
  bootstrap flows.
- Update documentation and examples so Redis cron coordination is
  configured only through environment variables.
- **BREAKING**: existing `config.json.cron_coordination` values will no
  longer affect runtime behavior after this change.

## Capabilities

### New Capabilities
- `cron-coordination-config-loading`: Define the effective loading rules
  for cron coordination so the runtime uses only environment-derived
  values and hardcoded defaults, and never `config.json`.

### Modified Capabilities

## Impact

- Affected configuration schema and persistence:
  `src/swe/config/config.py`, `src/swe/config/utils.py`
- Affected cron startup wiring:
  `src/swe/app/workspace/workspace.py`
- Affected configuration bootstrap and copy flows:
  `src/swe/cli/init_cmd.py`, `src/swe/app/workspace/tenant_initializer.py`
- Affected docs/spec examples:
  `openspec/changes/redis-coordinated-cron-leadership/CONFIG_EXAMPLES.md`
  and related runtime configuration docs
- Affected tests for config loading, workspace startup, and config
  serialization/migration
