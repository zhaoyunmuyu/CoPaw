## ADDED Requirements

### Requirement: User messages show a right-aligned sender and time header
The chat page SHALL render a compact metadata row immediately above each visible user message bubble. The row SHALL display the fixed sender label `我` and the formatted message time in `MM-dd HH:mm`, and it SHALL align to the right edge of the user message block.

#### Scenario: Rendering a user message
- **WHEN** the chat page renders a message turn whose visible card role is `user`
- **THEN** a metadata row is shown directly above the message body
- **THEN** the sender label is `我`
- **THEN** the metadata row is right-aligned with the user message block

#### Scenario: User message has a resolved timestamp
- **WHEN** the user message card includes a valid backend-provided time value
- **THEN** the metadata row shows the formatted time next to `我`

#### Scenario: Live user message is rendered before canonical history reload
- **WHEN** the user submits a message during an active realtime chat turn and the canonical `/api/chats/<id>` message timestamp has not been reloaded yet
- **THEN** the user request card uses a stable frontend-generated timestamp for the metadata row
- **THEN** a later history reload replaces that display time with the canonical backend-provided timestamp once available

### Requirement: Non-user messages show a left-aligned sender and time header
The chat page SHALL render a compact metadata row immediately above each visible non-user message turn. The row SHALL display the fixed sender label `小助 Claw` and the formatted message time in `MM-dd HH:mm`, and it SHALL align to the left edge of the non-user message block.

#### Scenario: Rendering a non-user message
- **WHEN** the chat page renders a visible message turn for a non-user runtime response card
- **THEN** a metadata row is shown directly above the message body
- **THEN** the metadata row is left-aligned with the non-user message block

#### Scenario: Non-user message has a resolved timestamp
- **WHEN** the non-user response card includes a valid backend-provided time value
- **THEN** the metadata row shows the formatted time next to `小助 Claw`

#### Scenario: Live non-user response is still streaming
- **WHEN** a non-user response card is being rendered from the active streaming session before chat history is reloaded
- **THEN** the response card shows a stable header timestamp derived from the live response creation time
- **THEN** a later history reload replaces that display time with the canonical backend-provided timestamp once available

### Requirement: Non-user sender label is fixed
The chat page SHALL use the fixed label `小助 Claw` for non-user message headers.

#### Scenario: Rendering a non-user message label
- **WHEN** the chat page renders a non-user runtime response card
- **THEN** the non-user metadata row displays `小助 Claw`

### Requirement: Message header metadata stays visually attached to the message body
The chat page SHALL place the sender-and-time metadata row tightly above the corresponding message body so that the header is visually associated with the message it describes.

#### Scenario: Rendering the message header row
- **WHEN** a message metadata row is rendered
- **THEN** the metadata row appears directly above the message body with compact vertical spacing
- **THEN** the header and message body remain on the same left or right alignment track for that role

### Requirement: Existing chat detail payload includes canonical message time
The existing chat detail payload for `/api/chats/<id>` SHALL expose a canonical time field for each message so the frontend can render message header time from backend-provided values.

#### Scenario: Loading chat detail messages
- **WHEN** the frontend requests `/api/chats/<id>`
- **THEN** each returned message includes a canonical time field that represents the backend-provided message time

### Requirement: Request and response cards carry header timestamp metadata for rendering
The chat page session conversion layer SHALL attach header timestamp metadata to rendered request and response cards using the canonical backend time field so the page-local card wrappers can display message times without re-reading raw backend messages.

#### Scenario: Building a user request card
- **WHEN** the session conversion layer creates a user request card from a message that includes the canonical backend time field
- **THEN** it attaches that value to `headerMeta.timestamp`

#### Scenario: Building a grouped response card
- **WHEN** the session conversion layer creates a grouped non-user response card from messages that include the canonical backend time field
- **THEN** it attaches a `headerMeta.timestamp` value derived from the backend-provided time field according to the grouping rule

### Requirement: Live chat cards keep sender headers visible before history refresh
The chat runtime layer SHALL attach header timestamp metadata to live request and streaming response cards so sender name and time remain visible during an active chat turn before the session is reloaded from `/api/chats/<id>`.

#### Scenario: Creating a live user request card
- **WHEN** the runtime layer creates a new user request card for an in-progress chat turn
- **THEN** it attaches a stable `headerMeta.timestamp` generated at submit time

#### Scenario: Updating a live response card during streaming
- **WHEN** the runtime layer updates the active non-user response card with new streaming chunks
- **THEN** it preserves the same `headerMeta.timestamp` across updates instead of changing the displayed time on each chunk
