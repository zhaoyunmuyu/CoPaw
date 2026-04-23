## 1. Session Identity Model

- [x] 1.1 Audit Chat frontend paths that read or write `currentSessionId`, `chat.id`, and logical `session_id`
- [x] 1.2 Introduce an explicit mapping model that keeps logical `session_id` separate from `chat.id`
- [x] 1.3 Update new-chat bootstrap and session resolution logic so resolving `chat.id` does not overwrite logical `session_id`
- [x] 1.4 Fix refresh hydration so a stale temporary URL ID cannot be restored as a new empty conversation when a real `chat.id` already exists

## 2. Request Ownership Guard

- [x] 2.1 Add request-level ownership metadata for submit and reconnect flows
- [x] 2.2 Guard SSE chunk application so stale events cannot update the active response container for another request
- [x] 2.3 Bind completion-time sync to the originating conversation instead of the currently selected session

## 3. Follow-up and Navigation Coordination

- [x] 3.1 Update follow-up auto-interrupt flow to reuse the interrupted chat's logical `session_id`
- [x] 3.2 Fix `onSessionIdResolved` callback usage and align URL synchronization with `chat.id` semantics
- [x] 3.3 Verify stop, reconnect, polling, history loading, and initial session selection each use the correct identity field

## 4. Verification

- [x] 4.1 Add or update tests for first-reply resolution followed by immediate follow-up submit
- [x] 4.2 Add or update tests for first-reply resolution followed by page refresh so the existing conversation is restored instead of a new empty one
- [x] 4.3 Add or update tests for switching chats while an old SSE stream still has delayed events
- [x] 4.4 Add or update tests for reconnect and completion sync so one chat cannot mutate another chat's history
