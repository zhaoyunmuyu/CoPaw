## ADDED Requirements

### Requirement: Case detail iframe embedding

The system SHALL automatically embed an iframe in the case detail drawer when `iframe_url` is present in case detail.

#### Scenario: Case with iframe_url renders iframe
- **WHEN** case detail contains `iframe_url: "https://internal.example.com/data"`
- **THEN** CaseDetailDrawer renders `<iframe src="https://internal.example.com/data">` in right panel

#### Scenario: iframe_title displayed as panel title
- **WHEN** case detail contains `iframe_title: "客户名单"`
- **THEN** iframe panel header displays "客户名单"

### Requirement: CaseDetailDrawer left-right layout

The system SHALL render CaseDetailDrawer with left panel for steps and right panel for iframe embedding.

#### Scenario: Left panel shows steps
- **WHEN** case detail contains `steps: [{title, content}]`
- **THEN** left panel renders each step with title and content

#### Scenario: Right panel shows iframe
- **WHEN** case detail contains `iframe_url`
- **THEN** right panel occupies flex:2 and renders iframe

### Requirement: iframe sandbox security

The system SHALL apply sandbox attributes to iframe for security.

#### Scenario: iframe has sandbox attributes
- **WHEN** iframe is rendered
- **THEN** iframe has `sandbox="allow-scripts allow-same-origin allow-forms"` attribute

### Requirement: iframe loading state

The system SHALL display loading indicator while iframe content is loading.

#### Scenario: iframe shows loading state
- **WHEN** iframe starts loading external URL
- **THEN** system displays loading spinner or placeholder

#### Scenario: iframe load failure shows error
- **WHEN** iframe fails to load (network error, CORS block)
- **THEN** system displays error message with retry option

### Requirement: iframe_url as required detail field

The system SHALL require `iframe_url` in case detail for proper iframe rendering.

#### Scenario: Case without iframe_url shows steps only
- **WHEN** case detail has empty or null `iframe_url`
- **THEN** drawer shows only left steps panel, right panel is hidden or shows placeholder