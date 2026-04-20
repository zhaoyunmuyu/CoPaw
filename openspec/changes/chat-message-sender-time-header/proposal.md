## Why

The chat page currently renders message bubbles without a visible sender label or message time, which makes multi-turn conversations harder to scan and weakens the relationship between the selected Agent and the messages it produces. We need a consistent message header treatment so users can immediately identify who spoke and when, without changing the underlying chat flow.

## What Changes

- Add a message header row above chat message content that displays sender name and a formatted time value in `MM-dd HH:mm`
- Render the header row immediately above the message body, aligned with the message side: user messages on the right, non-user messages on the left
- Display the fixed label `我` for all `user` messages
- Display the fixed label `小助 Claw` for all non-user messages
- Add a canonical time field to the existing chat detail/message payload so the frontend can render message time from backend-provided values
- Extend chat session-to-card conversion so request and response cards carry header metadata derived from the backend time field

## Capabilities

### New Capabilities
- `chat-message-header-meta`: Display sender name and time above chat messages with role-specific alignment and agent-aware naming rules

### Modified Capabilities
<!-- No existing spec-level requirements are changing -->

## Impact

- `console/src/pages/Chat/index.tsx` — register page-local message card renderers
- `console/src/pages/Chat/sessionApi/index.ts` — attach timestamp metadata to request/response cards during session conversion
- `console/src/pages/Chat/messageMeta.ts` — resolve message timestamps
- `console/src/pages/Chat/components/ChatMessageMeta/` — new compact header row UI for sender name and time
- `console/src/pages/Chat/components/RuntimeRequestCard/` and `console/src/pages/Chat/components/RuntimeResponseCard/` — page-local wrappers for request/response card rendering
- Existing chat detail payload for `/api/chats/<id>` — add canonical message time field consumed by the frontend
