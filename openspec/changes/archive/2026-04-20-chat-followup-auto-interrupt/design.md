## Context

This change targets the current local single-instance runtime only. It does not depend on shared run coordination or cross-instance stop semantics.

The frontend currently uses a single shared current-turn reference for request, response, and abort controller state. Because of that, a new submit must not create a new request and response pair until the previous turn has fully stopped. Otherwise, stale stream events from the previous turn can update the new turn's UI state.

The current stop interaction is also not a true synchronous stop primitive. The visible stop button first marks the current response as interrupted, and the backend stop request is coupled to the stream-processing path. For hidden follow-up submit, the system needs an explicit interrupt orchestration path rather than simulated button-click behavior.

## Goals / Non-Goals

**Goals:**
- Let a user send a new message while the current chat is still generating
- Keep the stop-to-resend transition hidden from the visible message list
- Auto-submit only after the previous run is fully no longer generating
- Retain only the latest pending follow-up message
- Retry stop with a bounded retry budget before failing
- Restore pending input for manual resend if auto-submit cannot proceed

**Non-Goals:**
- Shared or cross-instance run coordination
- Reworking backend attach or reconnect semantics for multi-instance runtime
- Preserving multiple queued hidden follow-up submits
- Changing the visible chat transcript to show an intermediate switching state

## Decisions

### Decision 1: Follow-up submit is hidden until the previous run fully stops

A follow-up submit during generation is stored as a hidden pending submit and is not rendered immediately.

**Rationale:**
- The user explicitly does not want to see a switching message in the UI.
- Creating the next request and response UI too early would reuse shared current-turn state and risk stale stream writes crossing into the next turn.

### Decision 2: Only the latest pending follow-up submit is retained

If multiple follow-up submits occur while stop is still in progress, newer pending input replaces older pending input.

**Rationale:**
- The latest user intent should win.
- A hidden queue of multiple pending messages would make the eventual auto-submit behavior hard to predict.

### Decision 3: Stop completion is determined by generating state

The frontend treats stop as complete only after the current chat is no longer generating.

**Rationale:**
- The stop request result alone is not sufficient because cancellation settles asynchronously.
- Auto-submitting before generation fully ends risks attaching to the still-running previous turn.

### Decision 4: Stop uses bounded retry

The frontend retries stop with a small bounded retry budget before abandoning automatic follow-up submit.

**Rationale:**
- A single stop attempt may not immediately end generation.
- Bounded retry preserves responsiveness while giving cancellation enough time to converge.

### Decision 5: Retry exhaustion restores recoverability in the input box

If stop retry budget is exhausted, the frontend does not auto-submit the pending input and restores it to the input box for manual resend.

**Rationale:**
- The user should not lose the hidden follow-up message.
- Restoring the input box is more transparent and recoverable than leaving hidden state in memory only.

### Decision 6: Hidden follow-up orchestration uses an explicit stop path

The automatic follow-up flow uses direct stop orchestration logic rather than simulating a stop button click.

**Rationale:**
- The visible stop button is a UI interaction, not a stable internal boundary.
- Hidden orchestration should invoke explicit logic that can be retried and observed without depending on button-driven state transitions.

## Risks / Trade-offs

- A slow cancellation tail can delay automatic follow-up submit.
- Failure recovery requires input restoration plumbing through the runtime input reference.
- During retry, only the latest pending message is retained, so earlier hidden follow-up attempts are intentionally dropped.
- This change intentionally leaves backend same-chat attach semantics untouched and instead sequences around them from the frontend.

## Suggested Runtime Defaults

- `max_stop_retries = 3`
- backoff sequence around `300ms`, `600ms`, `1000ms`
- retry success determined by chat no longer being reported as generating
