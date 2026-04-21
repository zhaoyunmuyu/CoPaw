## Why

When a user submits a new message while the current chat response is still generating, the system currently requires a manual stop action before the next turn can begin. This creates friction and does not match the expected chat interaction model.

In the current single-instance runtime, follow-up submit cannot be implemented as a simple frontend resend because:
- the frontend currently blocks submit while loading
- the stop flow is not immediate button-click semantics
- a new `/console/chat` request for the same chat can attach to the still-running previous turn instead of starting a new one

We need a local-runtime follow-up submit behavior that automatically interrupts the current turn in the background and only sends the latest pending message after the previous turn has fully stopped.

## What Changes

- Add frontend follow-up submit orchestration for chats that are still generating
- Store only the latest pending follow-up message while stop is in progress
- Stop the active run in the background without rendering an intermediate switching message
- Retry stop a bounded number of times before giving up
- Automatically submit the latest pending message only after the current chat is no longer generating
- Restore the pending message into the input box if automatic follow-up submit is abandoned

## Capabilities

### New Capabilities

- `chat-followup-auto-interrupt`: Automatically interrupt the active chat turn and submit the latest pending follow-up message after the previous turn has fully stopped in the current local runtime model.

### Modified Capabilities

- Console chat send and cancel interaction semantics
