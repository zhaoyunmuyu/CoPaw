## Context

SWE uses `contextvars` for request-scoped user isolation. The key components are:

- `src/swe/constant.py`: Contains `contextvars` for `request_user_id`, `request_workspace`, and directory getters
- `AgentRunner.query_handler()`: Sets up request context per query with `set_request_user_id(user_id)`
- Channel layer: Each message carries `sender_id` which becomes `request.user_id`
- Data directories: Each user has isolated directories under `~/.swe/<user_id>/`

Current implementation relies on Python's `contextvars` for async-safe request isolation, but lacks comprehensive testing to verify complete isolation.

## Goals / Non-Goals

**Goals:**
- Verify `contextvars` correctly isolate tenant data across concurrent requests
- Confirm directory getters return user-specific paths
- Test that memory, sessions, skills, and config remain isolated between tenants
- Identify any code paths that bypass tenant isolation
- Document findings and fix any discovered vulnerabilities

**Non-Goals:**
- Refactoring the multi-tenant architecture (unless bugs found)
- Adding new multi-tenant features
- Performance benchmarking of isolation mechanisms

## Decisions

### Use pytest with asyncio support for concurrent testing
- **Rationale**: Need to simulate concurrent requests from different tenants
- **Alternatives considered**: Threading-based tests (rejected - doesn't match async architecture)

### Create isolated test fixtures that mock user directories
- **Rationale**: Avoid polluting real `~/.swe/` during tests
- **Alternatives considered**: Using temporary directories with monkeypatch

### Test both happy path and attack scenarios
- **Rationale**: Security verification requires testing malicious attempts at data access
- **Attack vectors**: Direct file path manipulation, context var manipulation, race conditions

## Risks / Trade-offs

- [Risk] Tests may pass but real-world edge cases exist → Mitigation: Code audit alongside testing
- [Risk] Mocking may hide real isolation issues → Mitigation: Include integration tests with real directories
- [Risk] Concurrent test flakiness → Mitigation: Use proper async synchronization primitives

## Migration Plan

N/A - This is a verification effort, not a deployment change.

## Open Questions

1. Should we test channel-level isolation (DingTalk, Feishu, etc.) or just the core mechanism?
Should test channel-level
2. Do we need to verify database-level isolation if using shared MySQL/Redis?
Non
