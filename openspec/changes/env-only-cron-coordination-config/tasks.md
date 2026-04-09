## 1. Remove `config.json` as a cron coordination source

- [x] 1.1 Remove `cron_coordination` from the root `Config` schema and any config serialization paths that currently persist it.
- [x] 1.2 Ensure legacy root `config.json` files with `cron_coordination` still load successfully but the field is ignored and dropped on the next save/bootstrap rewrite.
- [x] 1.3 Add or update config load/save tests to cover legacy input containing `cron_coordination` and saved output that omits it.

## 2. Switch runtime loading to environment-derived values

- [x] 2.1 Refactor `Workspace._get_cron_coordination_config()` to build `CoordinationConfig` from env-backed cron constants instead of `load_config()`.
- [x] 2.2 Add or update runtime tests to verify cron coordination behavior is driven by environment-derived values and cannot be overridden by tenant `config.json`.
- [x] 2.3 Verify missing cron coordination env values still fall back to the existing hardcoded defaults.

## 3. Clean up examples and rollout guidance

- [x] 3.1 Remove `config.json`-based cron coordination examples from `openspec/changes/redis-coordinated-cron-leadership/CONFIG_EXAMPLES.md` and replace them with env-only guidance.
- [x] 3.2 Update any related docs or templates that still describe `cron_coordination` as a supported root-config section.
- [x] 3.3 Run focused verification covering config persistence and cron coordination loading behavior, and record the commands/results in the implementation notes.
