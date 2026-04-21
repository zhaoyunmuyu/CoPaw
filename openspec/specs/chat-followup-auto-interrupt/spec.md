# chat-followup-auto-interrupt Specification

## Purpose
TBD - created by archiving change chat-followup-auto-interrupt. Update Purpose after archive.
## Requirements
### Requirement: Follow-up submit SHALL interrupt the active chat run before sending

When a user submits a new message in a chat that is still generating, the frontend SHALL stop the active run first and SHALL only submit the new message after the chat is no longer generating.

#### Scenario: Hidden interrupt-then-submit flow
- **WHEN** the current chat is still generating and the user submits a new message
- **THEN** the frontend SHALL NOT immediately render the new user message
- **AND** the frontend SHALL store that message as the latest pending follow-up submit
- **AND** the frontend SHALL trigger stop for the active run in the background
- **AND** the frontend SHALL automatically submit the pending message after the chat is no longer generating

### Requirement: Latest pending follow-up message SHALL win

When multiple follow-up messages are submitted while stop is still in progress, the frontend SHALL keep only the latest pending message for automatic submission.

#### Scenario: Multiple follow-up submits during interrupt
- **WHEN** the user submits multiple new messages while the previous run is still being stopped
- **THEN** the frontend SHALL replace any earlier pending follow-up message with the latest one
- **AND** the frontend SHALL auto-submit only the latest pending message after the chat stops generating

### Requirement: Stop SHALL be retried before automatic follow-up submit is abandoned

When the active run does not stop immediately, the frontend SHALL retry stop for a bounded number of attempts before giving up on automatic follow-up submit.

#### Scenario: Stop succeeds after retry
- **WHEN** the first stop attempt does not make the chat leave generating state
- **AND** a later retry succeeds within the configured retry budget
- **THEN** the frontend SHALL automatically submit the latest pending follow-up message

#### Scenario: Stop retry budget is exhausted
- **WHEN** the chat remains generating after the configured stop retry budget is exhausted
- **THEN** the frontend SHALL NOT auto-submit the pending follow-up message
- **AND** the frontend SHALL surface a failure notification
- **AND** the pending follow-up message SHALL remain recoverable for manual resend

### Requirement: Pending follow-up recovery SHALL restore input content

When automatic follow-up submit is abandoned after stop retry exhaustion, the pending message SHALL be restored to the visible input box so the user can resend it manually.

#### Scenario: Pending message is restored after retry exhaustion
- **WHEN** stop retry budget is exhausted for a hidden pending follow-up message
- **THEN** the frontend SHALL restore the pending message content into the chat input box
- **AND** the restored message SHALL be editable before manual resend

