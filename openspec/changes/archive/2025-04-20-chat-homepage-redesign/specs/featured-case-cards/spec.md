## ADDED Requirements

### Requirement: Featured case card grid
The featured cases SHALL be displayed as a horizontal row of cards. Each card SHALL be 176px wide and 168px tall with a white background and border-radius. Cards SHALL contain an optional image thumbnail at the top and text description below.

#### Scenario: Multiple cases displayed
- **WHEN** there are 5 or more featured cases available
- **THEN** the cases are displayed as a horizontal row of cards with 12px gap between them

#### Scenario: Case card content
- **WHEN** a case card is rendered
- **THEN** it shows an image thumbnail (75x53px when present) and truncated text description in color #4F5060

### Requirement: Featured case section header
The featured case section SHALL have a header row with "精选案例" title (color #4F5060, with a document icon) on the left and "查看更多" link with an arrow icon on the right.

#### Scenario: Section header display
- **WHEN** the featured case section is visible
- **THEN** "精选案例" with document icon is shown on the left, and "查看更多 >" is shown on the right

### Requirement: Case card hover overlay
When the user hovers over a case card, a semi-transparent black overlay (rgba(0,0,0,0.6)) SHALL appear with two action buttons: "看案例" and "做同款". Both buttons SHALL use pill style (border-radius 100px) with background #3769FC and white text.

#### Scenario: Hover interaction
- **WHEN** the user hovers over a case card
- **THEN** a dark overlay appears with "看案例" and "做同款" buttons

#### Scenario: Click "做同款"
- **WHEN** the user clicks the "做同款" button on a case card
- **THEN** the case text is filled into the welcome page input box

#### Scenario: Click "看案例"
- **WHEN** the user clicks the "看案例" button on a case card
- **THEN** a detail view of the case is expanded/shown (UI placeholder)

### Requirement: Click case card to fill input
Clicking anywhere on a case card (outside the hover overlay buttons) SHALL fill the case text into the welcome page input box.

#### Scenario: Direct card click
- **WHEN** the user clicks on a case card body (not on hover overlay buttons)
- **THEN** the case text is filled into the input box without auto-sending
