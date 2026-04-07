# Tenant Initialization Specification

## Overview

CoPaw supports multi-tenant isolation where each tenant has completely separated configuration, skills, and data. This specification describes the tenant initialization flow, including directory structure, configuration templates, and skill seeding.

## Directory Structure

### Working Directory

```
~/.copaw/                              # WORKING_DIR
├── default/                           # Default tenant
│   ├── config.json                    # Tenant config (channels, MCP, agents)
│   ├── HEARTBEAT.md                   # Heartbeat query template
│   ├── workspaces/                    # Agent workspaces
│   │   └── default/                   # Default agent workspace
│   │       ├── skills/                # Enabled skills
│   │       │   └── skill_manifest.json
│   │       └── *.md                   # Agent persona files
│   ├── skill_pool/                    # Shared skill pool
│   │   └── pool_manifest.json
│   └── media/                         # Media files
├── {tenant_id}/                       # Other tenant directories
│   └── ... (same structure as default)
└── ...
```

### Secret Directory

```
~/.copaw.secret/                       # SECRET_DIR
├── default/                           # Default tenant secrets
│   └── providers.json                 # LLM provider config
├── {tenant_id}/                       # Other tenant secrets
│   └── providers.json
└── ...
```

## Template Files

Template files are stored in the package and copied during initialization:

```
src/copaw/agents/md_files/
├── config.json                        # Default tenant config template
├── providers.json                     # Default provider config template
├── zh/                                # Chinese persona files
│   ├── AGENTS.md
│   ├── PROFILE.md
│   └── ...
├── en/                                # English persona files
└── ru/                                # Russian persona files
```

## Initialization Modes

### 1. Minimal Initialization (`initialize_minimal`)

Used for runtime lazy bootstrap. Creates only the essential directory structure.

**Operations:**
1. Create tenant directory structure
2. Create default agent declaration

**Does NOT:**
- Copy configuration templates
- Initialize skills
- Create QA agent

**Trigger:** Runtime request to uninitialized tenant

### 2. Full Initialization (`initialize_full`)

Used by CLI `copaw init`. Performs complete tenant setup.

**Operations:**
1. Copy configuration templates (config.json, providers.json) - **MUST BE FIRST**
2. Run minimal initialization
3. Seed skill pool from default tenant (or builtin)
4. Seed default workspace skills from default tenant
5. Create QA agent workspace

**Trigger:** CLI command `copaw init --tenant-id <id>`

**Important:** Template files must be copied BEFORE `TenantInitializer.initialize_full()` because `ensure_default_agent()` creates/writes `config.json`. If templates are copied after, they would be overwritten or ignored.

## Initialization Flow

### CLI `copaw init` Flow

```
copaw init --tenant-id alice
│
├─ Security Warning (interactive or skip with --accept-security)
│
├─ Telemetry Collection (optional)
│
├─ copy_init_config_files()  ← MUST BE FIRST
│   ├─ Copy config.json template → ~/.copaw/{tenant_id}/config.json
│   └─ Copy providers.json template → ~/.copaw.secret/{tenant_id}/providers.json
│
├─ TenantInitializer.initialize_full()
│   │
│   ├─ initialize_minimal()
│   │   ├─ ensure_directory_structure()
│   │   │   └─ Create: tenant_dir/, workspaces/, media/, secrets/
│   │   └─ ensure_default_agent()
│   │       └─ Create: workspaces/default/agents.json
│   │       └─ Merge with existing config.json (preserves template)
│   │
│   ├─ seed_skill_pool_from_default()
│   │   ├─ Check if tenant has skill pool state
│   │   ├─ If default tenant exists with skills:
│   │   │   └─ Copy skill_pool/ from default tenant
│   │   └─ Else:
│   │       └─ Import builtin skills
│   │
│   ├─ seed_default_workspace_skills_from_default()
│   │   ├─ Check if workspace has skill state
│   │   ├─ If default tenant workspace exists with skills:
│   │   │   ├─ Copy skills/ directories
│   │   │   └─ Merge manifest state (enabled, channels, config)
│   │   └─ Else: skip
│   │
│   └─ ensure_qa_agent()
│       └─ Create QA agent workspace with skills
│
├─ Interactive Configuration (if not --defaults)
│   ├─ Heartbeat settings
│   ├─ Tool details display
│   ├─ Language selection
│   ├─ Audio mode
│   ├─ Channels configuration
│   └─ LLM provider configuration
│
├─ Skills Configuration
│   └─ Enable skills in default workspace
│
├─ MD Files Copy
│   └─ Copy persona files based on language
│
└─ HEARTBEAT.md Creation
```

### Execution Order Rationale

**Why `copy_init_config_files()` runs BEFORE `TenantInitializer.initialize_full()`:**

The `TenantInitializer.ensure_default_agent()` method calls `save_config()`, which creates or overwrites `config.json`. If template files were copied after initialization, they would be ignored because:

1. `ensure_default_agent()` loads existing config (or empty `Config()`)
2. Modifies agent profiles
3. Calls `save_config()` which writes the complete config

If the template `config.json` doesn't exist at step 1, the loaded config is empty, losing all pre-configured channels and MCP settings.

**Solution:** Copy templates FIRST, then `ensure_default_agent()` will merge its changes with the template content.

## Configuration Inheritance

### New Tenant from Default

When initializing a new tenant (not "default"):

1. **Skill Pool**: Copied from default tenant's skill pool if exists, otherwise use builtin skills
2. **Workspace Skills**: Copied from default tenant's default workspace
3. **Config Template**: Copied from package templates (md_files/config.json)
4. **Provider Template**: Copied from package templates (md_files/providers.json)

### Fallback Chain

```
New Tenant Initialization:
┌─────────────────────────────────────┐
│ 1. Try copy from default tenant     │
│    └─ ~/.copaw/default/...          │
└─────────────────┬───────────────────┘
                  │ (default not found)
                  ▼
┌─────────────────────────────────────┐
│ 2. Use package templates            │
│    └─ src/copaw/agents/md_files/... │
└─────────────────────────────────────┘
```

## Idempotency Rules

All initialization operations are idempotent:

| Check | Action |
|-------|--------|
| `config.json` exists | Skip copy (unless `--force`) |
| `providers.json` exists | Skip copy (unless `--force`) |
| Skill pool has state | Skip pool seeding |
| Workspace has skills | Skip workspace seeding |
| QA agent exists | Skip QA creation |

## CLI Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--tenant-id` | string | `default` | Tenant identifier |
| `--defaults` | flag | - | Non-interactive mode |
| `--accept-security` | flag | - | Skip security confirmation |
| `--force` | flag | - | Overwrite existing files |

## Key Components

### TenantInitializer

**Location:** `src/copaw/app/workspace/tenant_initializer.py`

**Methods:**
- `initialize_minimal()` - Create directory structure only
- `initialize_full()` - Complete initialization with skills
- `seed_skill_pool_from_default()` - Copy skill pool from default tenant
- `seed_default_workspace_skills_from_default()` - Copy workspace skills
- `ensure_qa_agent()` - Create QA agent workspace

### copy_init_config_files

**Location:** `src/copaw/agents/utils/setup_utils.py`

**Purpose:** Copy configuration templates to tenant directories

**Parameters:**
- `tenant_id` - Target tenant
- `force` - Overwrite existing
- `skip_existing` - Skip if exists

### copy_md_files

**Location:** `src/copaw/agents/utils/setup_utils.py`

**Purpose:** Copy persona MD files based on language

## Security Considerations

1. **Secret Directory Permissions**: Set to `0o700` (owner only)
2. **providers.json Permissions**: Set to `0o600` (owner read/write only)
3. **Tenant Isolation**: Each tenant's data is completely separated
4. **API Keys**: Stored in `~/.copaw.secret/{tenant_id}/providers.json`, not in working directory

## Error Handling

| Error | Recovery |
|-------|----------|
| Default tenant not found | Use package templates |
| Template file missing | Create empty default |
| Copy failure | Log error, continue |
| Permission denied | Skip permission setting, warn |

## Testing Considerations

1. Test minimal initialization creates correct structure
2. Test full initialization copies all components
3. Test idempotency (re-run doesn't change state)
4. Test fallback when default tenant absent
5. Test tenant isolation (configs don't leak)
6. Test `--force` overwrites correctly
7. Test `--defaults` skips all prompts
