## Context

The chat page is built on top of `AgentScopeRuntimeWebUI`, which renders request and response content through runtime cards such as `AgentScopeRuntimeRequestCard` and `AgentScopeRuntimeResponseCard`. The existing runtime cards render message bodies but do not provide a page-specific message header area for sender identity and time.

This change affects the Chat page in `console/src/pages/Chat/` and the existing chat detail payload returned for `/api/chats/<id>`. The user has already fixed the product rules:
- `user` messages always display `我`
- non-user messages always display `小助 Claw`
- name and time must sit tightly above the message
- user headers align to the right; non-user headers align to the left
- time is formatted as `MM-dd HH:mm`

Current backend message data does not expose a canonical timestamp field for every rendered card variant. The target behavior is to extend the existing message payload with a dedicated time field and have the frontend consume that backend value once available. During an active realtime turn, the page also needs a temporary local timestamp so the header is visible before the chat detail payload is reloaded.

## Goals / Non-Goals

**Goals:**
- Show a compact sender-and-time header directly above each rendered chat turn
- Use a page-local rendering path so the change is isolated to the Chat page
- Preserve existing request/response card body rendering and chat submission behavior
- Carry enough metadata through session conversion for the page renderer to format message headers
- Use a backend-provided canonical message time field instead of relying on inferred frontend timestamps
- Keep sender-and-time headers visible during live streaming before canonical history data is available

**Non-Goals:**
- Changing shared `agentscope-chat` bubble/card behavior for other pages
- Showing per-submessage headers inside a grouped assistant response card
- Reworking chat message grouping, sender roles, or response streaming semantics
- Introducing a brand-new endpoint for message headers; the existing chat detail interface is extended instead

## Decisions

### 1. Use page-local runtime card wrappers instead of modifying shared chat card components

**Decision**: Register custom `AgentScopeRuntimeRequestCard` and `AgentScopeRuntimeResponseCard` components from `pages/Chat/index.tsx`, and wrap the existing runtime card bodies with a lightweight message-meta header.

**Rationale**:
- The requirement is specific to the Chat page, not every consumer of `agentscope-chat`
- Reusing the existing runtime card body components keeps rendering risk low
- The wrapper pattern limits blast radius and makes the UI treatment easy to remove or evolve later

**Alternative considered**: Modify the shared runtime card implementation in `components/agentscope-chat/` to always render headers. Rejected because it would create cross-page coupling and raise regression risk outside this feature.

### 2. Use a fixed non-user display name

**Decision**: Render `小助 Claw` for every non-user message header instead of resolving the label from agent workspace files or page state.

**Rationale**:
- The sender header still clearly distinguishes user and non-user turns
- A fixed label removes file reads, caching, and stale-name edge cases from the chat page
- The same label now appears consistently for both history and live streaming cards

**Alternative considered**: Continue resolving the selected Agent name dynamically. Rejected because the runtime can mutate workspace files independently of the frontend, which makes dynamic display names harder to keep correct.

### 3. Add and consume a canonical backend time field

**Decision**: Extend the existing `/api/chats/<id>` message payload with a dedicated time field for each message, and treat that field as the source of truth for header time rendering.

**Rationale**:
- The user explicitly wants time to come from the original interface after the backend provides the real value
- A canonical backend field removes ambiguity from frontend timestamp inference
- This keeps message header formatting deterministic across request and response cards

**Alternative considered**: Continue using best-effort frontend timestamp inference from mixed fields and metadata. Rejected as the target design because it can drift from the real backend event time.

### 4. Carry header metadata through session card conversion

**Decision**: Extend `sessionApi` conversion helpers so user request cards and grouped response cards include `headerMeta.timestamp`, then let the page-local wrappers format that timestamp as `MM-dd HH:mm` for display.

**Rationale**:
- Runtime request/response cards are already the rendering boundary used by the chat page
- Keeping header metadata on card data avoids reaching back into raw session message arrays during render
- Grouped response cards should share one header row per visible assistant turn, which matches the current card grouping behavior

**Alternative considered**: Recompute timestamps in the wrapper components from raw messages. Rejected because the wrapper only sees already-converted card data.

### 5. Use optimistic-but-stable timestamps for live chat rendering

**Decision**: When the user submits a new message or a response starts streaming, the runtime layer attaches a stable local `headerMeta.timestamp` to the live request/response cards immediately. Once the session is reloaded from `/api/chats/<id>`, the canonical backend message timestamps replace the temporary live values.

**Rationale**:
- The user wants the same sender-and-time treatment during live chat, not only after history reload
- Live cards are created before canonical history data is available, so they need an immediate local fallback
- Keeping the live timestamp stable across streaming updates avoids the displayed time flickering on every chunk

**Alternative considered**: Leave live cards without time until the history API returns. Rejected because it creates inconsistent behavior between active and historical turns.

## Risks / Trade-offs

- [Backend time field rollout may lag behind frontend UI work] -> Keep the card metadata path in place so the frontend can start consuming the canonical field as soon as it is returned, and use a temporary stable live timestamp before history reload completes
- [A fixed non-user label no longer reflects per-Agent persona names] -> Accept the simplification because the current requirement is to keep assistant sender labels static
- [Grouped assistant responses only show one header row] -> Keep one header per visible response card to match the current grouped-turn UI and avoid repeated labels inside a single turn
- [Page-local custom cards can drift from shared runtime card interfaces] -> Keep wrappers thin and pass through existing card props unchanged except for the added header row

## Migration Plan

- Extend the existing chat detail response with the canonical message time field
- Update frontend session conversion to read that field into `headerMeta.timestamp`
- Rollback is straightforward: remove the custom card registrations and page-local header components to restore the original chat card rendering

## Open Questions

- Confirm the exact backend field name and whether grouped assistant turns should use the last message time or a server-precomputed turn time
