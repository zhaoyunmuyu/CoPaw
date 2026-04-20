## 1. Message Metadata Model

- [x] 1.1 Define and document the canonical backend message time field for the existing `/api/chats/<id>` payload
- [x] 1.2 Keep non-user sender labels fixed as `小助 Claw`
- [x] 1.3 Extend chat card data types so request and response cards can carry `headerMeta.timestamp`

## 2. Chat Page Rendering

- [x] 2.1 Create a compact message metadata component that renders sender name and time with left/right alignment variants
- [x] 2.2 Create page-local request and response card wrappers that render the metadata row above the existing runtime card bodies
- [x] 2.3 Update `pages/Chat/index.tsx` and the runtime response wrapper so non-user messages always show `小助 Claw`

## 3. Session Conversion

- [x] 3.1 Update the chat detail/session conversion pipeline to read the canonical backend time field into user request card `headerMeta.timestamp`
- [x] 3.2 Update the grouped response conversion pipeline to read the canonical backend time field into non-user response card `headerMeta.timestamp`
- [x] 3.3 Update live request/response card creation so active streaming turns keep a stable `headerMeta.timestamp` before history reload

## 4. Verification

- [x] 4.1 Verify user messages render `我` with right-aligned header metadata above the message body
- [x] 4.2 Verify non-user messages render `小助 Claw` with left-aligned header metadata above the message body
- [x] 4.3 Verify timestamp formatting uses the backend-provided time field from `/api/chats/<id>` once it is returned
- [x] 4.4 Verify live request/response cards keep a stable header timestamp while streaming
