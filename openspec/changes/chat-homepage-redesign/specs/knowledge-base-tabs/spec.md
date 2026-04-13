## ADDED Requirements

### Requirement: Knowledge base tab bar
The welcome page SHALL display a horizontal tab bar below the input box with knowledge base options. Each tab SHALL use a pill/capsule style with border-radius 20px, height 28px. The active tab SHALL have background #8482E7 with white text and a checkbox icon. Inactive tabs SHALL have transparent background with color #333 text.

#### Scenario: Tab bar display
- **WHEN** the welcome page is displayed
- **THEN** the knowledge base tab bar shows below the input box with "原保险经验库" as active (purple) and "分行经验库" as inactive

#### Scenario: Tab switching UI
- **WHEN** the user clicks an inactive tab
- **THEN** that tab becomes active (purple background) and the previously active tab becomes inactive

#### Scenario: Tab divider
- **WHEN** multiple tabs are displayed
- **THEN** tabs are separated by a vertical divider line (1px, color #C2BBD0)

### Requirement: Tab functionality placeholder
The knowledge base tab switching SHALL be UI-only with no backend logic. The active tab state SHALL be maintained locally. The tab bar is a placeholder for future knowledge base integration.

#### Scenario: No backend call on tab switch
- **WHEN** the user switches tabs
- **THEN** only the visual state changes, no API calls are made
