## ADDED Requirements

### Requirement: Cron coordination runtime config SHALL ignore `config.json`
The backend SHALL derive the effective cron coordination configuration
only from environment-derived values and hardcoded code defaults, and it
MUST NOT read root `config.json.cron_coordination` to determine runtime
behavior.

#### Scenario: Environment-derived values enable coordination
- **WHEN** cron coordination environment values are set for a process
- **THEN** the backend SHALL build the effective cron coordination
  runtime config from those environment-derived values
- **AND** it SHALL start cron coordination behavior consistent with those
  values

#### Scenario: Missing environment values fall back to code defaults
- **WHEN** a cron coordination setting is not provided through the
  supported environment-derived sources
- **THEN** the backend SHALL use the hardcoded default for that setting

#### Scenario: Legacy config entry cannot override runtime config
- **WHEN** a tenant `config.json` contains a legacy
  `cron_coordination` section
- **THEN** the backend SHALL ignore that section when constructing the
  runtime cron coordination config

### Requirement: Root config persistence SHALL not retain `cron_coordination`
The backend SHALL treat `cron_coordination` as a removed root-config
field and MUST NOT persist it in generated or rewritten `config.json`
files.

#### Scenario: New config output excludes cron coordination
- **WHEN** the backend creates or saves a root `config.json`
- **THEN** the serialized output SHALL NOT contain a
  `cron_coordination` section

#### Scenario: Legacy config is rewritten without cron coordination
- **WHEN** the backend loads a root `config.json` that still contains a
  legacy `cron_coordination` section and later saves that config
- **THEN** the saved `config.json` SHALL omit the legacy
  `cron_coordination` section

### Requirement: Cron coordination documentation SHALL use env-only examples
The backend project SHALL document Redis cron coordination configuration
through environment variables and packaged env presets, not through root
`config.json`.

#### Scenario: Environment examples are provided
- **WHEN** operators consult cron coordination configuration examples
- **THEN** the documented examples SHALL show `.env`, process
  environment, or packaged `envs/{dev|prd}.json` based configuration

#### Scenario: Config.json examples are removed
- **WHEN** operators consult cron coordination configuration examples
- **THEN** the documentation SHALL NOT present `config.json` as a
  supported source for cron coordination settings
