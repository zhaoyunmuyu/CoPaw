## Why

The SWE project implements multi-tenant support through `contextvars`-based request isolation, but there is no comprehensive verification that the implementation actually guarantees complete tenant isolation. We need to verify that user data (config, memory, sessions, skills) is properly isolated between tenants and that there are no data leakage vulnerabilities.

## What Changes

- Create comprehensive test suite to verify multi-tenant isolation at all data boundaries
- Audit existing multi-tenant implementation for potential isolation gaps
- Verify that request-scoped working directories are correctly isolated per user
- Ensure memory, sessions, and skill directories maintain strict tenant boundaries
- Document any findings and fix identified isolation issues

## Capabilities

### New Capabilities
- `tenant-isolation-verification`: Comprehensive testing framework for validating complete tenant data isolation across all system components

### Modified Capabilities
- None (this is a verification/audit effort, not a feature change)

## Impact

- Test coverage for `src/swe/constant.py` (request isolation utilities)
- Verification of `AgentRunner.query_handler()` tenant context setup
- Validation of all directory getters: `get_request_working_dir()`, `get_request_secret_dir()`, `get_active_skills_dir()`, `get_memory_dir()`, `get_models_dir()`
- Channel request isolation verification across all platform connectors
