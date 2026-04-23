## ADDED Requirements

### Requirement: Chat follow-up SHALL preserve logical session identity
The chat frontend SHALL preserve a stable logical `session_id` for a conversation across new-chat bootstrap, first-response resolution, and follow-up submissions. Resolving a backend `chat.id` for that conversation SHALL NOT change the logical `session_id` used for later `/console/chat` requests.

#### Scenario: First response resolves a backend chat record
- **WHEN** a new chat is created with a temporary UI session and the backend later returns a persisted `chat.id`
- **THEN** the frontend SHALL keep using the original logical `session_id` for subsequent chat requests
- **AND** the frontend SHALL use the resolved `chat.id` only for record-oriented operations such as navigation, detail lookup, stop, and reconnect

#### Scenario: User submits a follow-up after the first reply completes
- **WHEN** the first reply in a newly created chat has completed and the user sends another message in the same conversation
- **THEN** the next `/console/chat` request SHALL reuse the existing logical `session_id`
- **AND** the frontend SHALL NOT send the resolved `chat.id` as the conversation `session_id`

### Requirement: Refresh recovery SHALL resolve persisted chat identity before falling back to a new local session
When the page reloads after a new chat has already been persisted, the frontend SHALL restore the existing conversation using the persisted `chat.id` and its mapped logical `session_id`. It SHALL NOT silently treat a stale temporary UI ID as a brand-new empty conversation when the real chat record already exists.

#### Scenario: URL still contains a temporary ID after the first reply was persisted
- **WHEN** the first reply has already created a backend chat record but the browser URL still contains the temporary UI session ID
- **AND** the user refreshes the page
- **THEN** the frontend SHALL recover the persisted conversation represented by the resolved `chat.id`
- **AND** the restored conversation SHALL continue using its original logical `session_id` for later `/console/chat` requests
- **AND** the frontend SHALL NOT create a new empty local conversation solely because the temporary URL ID no longer exists in memory

#### Scenario: URL already contains the real backend chat ID
- **WHEN** the page loads on `/chat/{chat.id}` for an existing persisted conversation
- **THEN** the frontend SHALL restore that chat's messages via `chat.id`
- **AND** it SHALL recover the mapped logical `session_id` before any follow-up submit is sent

### Requirement: Streaming updates SHALL be applied only to their owning request
The chat runtime SHALL bind each submit and reconnect operation to a distinct request identity and SHALL ignore stale streaming events that no longer belong to the active request for that conversation.

#### Scenario: User switches sessions before old stream fully terminates
- **WHEN** a streaming response from one chat still has delayed SSE events after the user switches to a different chat
- **THEN** the delayed events from the old request SHALL NOT update the newly selected chat view
- **AND** the runtime SHALL discard those events once the request is no longer the active owner

#### Scenario: A newer request supersedes an older request in the same chat
- **WHEN** an older request has not fully drained and a newer request becomes the active request for that chat
- **THEN** only the newer request SHALL be allowed to update the live response container
- **AND** stale events from the older request SHALL be ignored

### Requirement: Completion sync SHALL target the originating conversation
When a request finishes, the frontend SHALL sync live messages back to the conversation that originated the request rather than whichever chat is selected at completion time.

#### Scenario: Request completes after the user navigates away
- **WHEN** a request started in chat A reaches completion after the user has switched to chat B
- **THEN** any completion-time message sync SHALL apply to chat A
- **AND** chat B history SHALL remain unchanged by chat A completion

#### Scenario: Reconnect finishes for a running chat
- **WHEN** the frontend reconnects to a running chat and later receives the completion event for that reconnect-bound stream
- **THEN** the completion sync SHALL apply to the reconnected chat record
- **AND** no other chat history SHALL be updated by that completion event
