## MODIFIED Requirements

### Requirement: Follow-up submit SHALL interrupt the active chat run before sending

When a user submits a new message in a chat that is still generating, the frontend SHALL stop the active run first and SHALL only submit the new message after the chat is no longer generating. The automatic follow-up submission SHALL remain bound to the same logical conversation that held the generating run and SHALL NOT create or switch to a new logical session during that flow.

#### Scenario: Hidden interrupt-then-submit flow
- **WHEN** the current chat is still generating and the user submits a new message
- **THEN** the frontend SHALL NOT immediately render the new user message
- **AND** the frontend SHALL store that message as the latest pending follow-up submit
- **AND** the frontend SHALL trigger stop for the active run in the background
- **AND** the frontend SHALL automatically submit the pending message after the chat stops generating
- **AND** the automatic submission SHALL reuse the same logical `session_id` as the interrupted chat

#### Scenario: Follow-up submit after a backend chat record has been resolved
- **WHEN** the generating chat has already resolved a backend `chat.id` before the pending follow-up is auto-submitted
- **THEN** the frontend SHALL still submit the pending follow-up against the original logical `session_id`
- **AND** the frontend SHALL NOT replace that logical `session_id` with the resolved `chat.id`
