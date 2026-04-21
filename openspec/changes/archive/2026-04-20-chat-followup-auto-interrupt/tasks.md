## 1. Add follow-up interrupt orchestration

- [x] 1.1 Detect follow-up submit while the current chat is still generating
- [x] 1.2 Store only the latest pending follow-up submit without rendering it immediately
- [x] 1.3 Trigger direct stop for the active chat run in the background

## 2. Add bounded retry and completion detection

- [x] 2.1 Retry stop with a bounded retry budget and backoff
- [x] 2.2 Detect stop completion from chat generating status rather than stop response alone
- [x] 2.3 Auto-submit the latest pending follow-up message only after generation fully stops

## 3. Add failure recovery behavior

- [x] 3.1 Preserve the latest pending follow-up message when stop retry budget is exhausted
- [x] 3.2 Show a failure notification when automatic follow-up submit cannot proceed
- [x] 3.3 Restore the pending message into the input box for manual resend
- [x] 3.4 Expose runtime input-content restoration through the chat runtime ref if needed

## 4. Verify behavior

- [x] 4.1 Add frontend tests for hidden interrupt-then-submit flow
- [x] 4.2 Add tests that only the latest pending follow-up message is auto-submitted
- [x] 4.3 Add tests for stop retry exhaustion and input restoration
