关于测试案例的运行，请使用项目中已经安装的虚拟环境，venv/bin/python

## 1. Test Setup and Fixtures

- [x] 1.1 Create test file `tests/test_tenant_isolation.py` with pytest-asyncio configuration
- [x] 1.2 Create fixture for temporary user directories (mock `~/.swe/`)
- [x] 1.3 Create fixture for concurrent request simulation with context reset
- [x] 1.4 Create helper function to simulate multiple concurrent users

## 2. Context-Scoped User Isolation Tests

- [x] 2.1 Test concurrent requests from different tenants see correct user IDs
- [x] 2.2 Test nested async operations maintain correct user context
- [x] 2.3 Test context is properly reset between different requests
- [x] 2.4 Test context isolation under high concurrency (10+ simultaneous users)

## 3. Directory Isolation Tests

- [x] 3.1 Test `get_request_working_dir()` returns user-specific path for "alice"
- [x] 3.2 Test `get_request_secret_dir()` returns user-specific path for "alice"
- [x] 3.3 Test `get_active_skills_dir()` returns user-specific path for "alice"
- [x] 3.4 Test `get_memory_dir()` returns user-specific path for "alice"
- [x] 3.5 Test `get_models_dir()` returns user-specific path for "alice"
- [x] 3.6 Test all directory getters return different paths for different users concurrently

## 4. Data Leakage Prevention Tests

- [x] 4.1 Test tenant "alice" cannot read tenant "bob"'s config.json via path manipulation
- [x] 4.2 Test tenant "alice" cannot read tenant "bob"'s memory files
- [x] 4.3 Test tenant "alice" cannot read tenant "bob"'s session files
- [x] 4.4 Test tenant "alice" cannot read tenant "bob"'s active skills
- [x] 4.5 Test concurrent file operations from multiple tenants don't leak data

## 5. AgentRunner Integration Tests

- [x] 5.1 Test `AgentRunner.query_handler()` sets correct user context during message processing
- [x] 5.2 Test context is properly cleaned up after query handler completes
- [x] 5.3 Test multiple concurrent queries from different users maintain isolation

## 6. Code Audit and Documentation

- [x] 6.1 Audit `src/swe/constant.py` for any isolation gaps
- [x] 6.2 Audit `src/swe/app/runner/` for context handling issues
- [x] 6.3 Document any identified vulnerabilities or weaknesses
- [x] 6.4 Create summary report of verification findings

## 7. Fix Identified Issues (if any)

- [x] 7.1 Fix any discovered isolation vulnerabilities
- [x] 7.2 Add regression tests for fixed issues
- [x] 7.3 Re-run full test suite to confirm fixes
