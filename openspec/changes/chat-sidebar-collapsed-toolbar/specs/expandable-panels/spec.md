## ADDED Requirements

### Requirement: Expandable panel slide-out behavior
Clicking an icon in the collapsed toolbar SHALL toggle an expandable sub-panel (308px wide) that appears 8px to the right of the toolbar. Clicking the same icon again SHALL close the panel. Clicking a different icon SHALL switch to that panel. Clicking outside both the toolbar and panel SHALL close the panel.

#### Scenario: Opening the Tasks panel
- **WHEN** the user clicks the Tasks icon in the collapsed toolbar
- **THEN** a 308px wide panel slides out 8px to the right of the toolbar, and the Tasks icon turns blue (#3769FC)

#### Scenario: Switching from Tasks to History
- **WHEN** the Tasks panel is open and the user clicks the History icon
- **THEN** the Tasks panel closes, the History panel opens, and the History icon turns blue

#### Scenario: Closing panel by clicking same icon
- **WHEN** the Tasks panel is open and the user clicks the Tasks icon again
- **THEN** the panel closes and all icons return to gray (#808191)

#### Scenario: Closing panel by clicking outside
- **WHEN** any panel is open and the user clicks outside the toolbar and panel area
- **THEN** the panel closes and all icons return to gray

### Requirement: Panel container styling
Each expandable panel SHALL have white background (#FFFFFF), 8px border-radius, 20px padding on all sides, and a vertical layout with 12px gap between sections.

#### Scenario: Panel renders with correct visual styling
- **WHEN** a panel is expanded
- **THEN** it displays as a white rounded card with proper padding and spacing

### Requirement: Panel header
Each panel SHALL have a header containing a 16x16 icon (matching the toolbar section icon, colored #11142D) and text label in Semibold 16px Microsoft YaHei, colored #11142D. The format is: icon + section name + (count).

#### Scenario: Tasks panel header
- **WHEN** the Tasks panel is open
- **THEN** the header shows a tasks icon + "我的任务(5)" in semibold 16px dark text

#### Scenario: History panel header
- **WHEN** the History panel is open
- **THEN** the header shows a history icon + "历史记录(12)" in semibold 16px dark text

### Requirement: Task items as bordered cards
Task items in the Tasks panel SHALL be rendered as cards with: white background, 0.5px solid border (#E4E4E4), 8px border-radius, 12px padding, and 8px gap between items. Each card contains a title row (16px, #11142D) with optional badge, and a subtitle row (12px, #808191, 4px gap from title).

#### Scenario: Task card with badge
- **WHEN** a task has unread notifications
- **THEN** the task card shows the task title, a red badge (#FE2842) with the count, and a subtitle line below

#### Scenario: Task card without badge
- **WHEN** a task has no unread notifications
- **THEN** the task card shows only the task title and subtitle with no badge

### Requirement: Task badge styling
The notification badge on task items SHALL be pill-shaped (border-radius 12px), background #FE2842, white text 10px PingFang SC, with 4px horizontal padding. Single-digit badges are 14x14, multi-digit badges auto-size.

#### Scenario: Single digit badge
- **WHEN** a task has 1 unread item
- **THEN** a 14x14 red pill badge with "1" is shown

#### Scenario: Multi-digit badge
- **WHEN** a task has 21 unread items
- **THEN** a wider red pill badge with "21" is shown

### Requirement: History items as plain text rows
History items in the History panel SHALL be rendered as plain text rows (no border, no card styling, no background). Each item shows a title (16px, #4F5060) and timestamp (12px, #808191, 2px gap). Items are separated by padding only (top/bottom 10px).

#### Scenario: History item display
- **WHEN** the History panel is open with session records
- **THEN** each history item shows the session title in secondary text color and a formatted timestamp below

#### Scenario: History item hover
- **WHEN** the user hovers over a history item
- **THEN** the item shows a subtle background highlight (rgba(0,0,0,0.02))

### Requirement: History item click navigates to session
Clicking a history item SHALL navigate to the corresponding chat session by updating the URL to `/chat/{realId}`.

#### Scenario: Clicking a history item
- **WHEN** the user clicks a history item in the panel
- **THEN** the app navigates to `/chat/{sessionId}` and the panel closes

### Requirement: Task item click triggers cronjob
Clicking a task item SHALL trigger the associated cronjob via the API and close the panel.

#### Scenario: Clicking a task item
- **WHEN** the user clicks a task in the Tasks panel
- **THEN** the cronjob trigger API is called for that task and the panel closes
