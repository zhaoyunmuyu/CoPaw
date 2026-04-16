## ADDED Requirements

### Requirement: 64px collapsed toolbar layout
The system SHALL render a 64px wide by full-height toolbar when the ChatSidebar receives `collapsed={true}`. The toolbar SHALL display a white background (#FFFFFF), a 1px border (#E4E4E4) on the right side, and a subtle drop shadow (rgba(0,0,0,0.05), offset-x: 1, blur: 12).

#### Scenario: Toolbar renders with correct dimensions
- **WHEN** ChatSidebar is in collapsed mode
- **THEN** a 64px wide vertical toolbar is rendered with white background and right border/shadow

### Requirement: Three icon buttons in vertical layout
The toolbar SHALL contain 3 vertically-stacked icon buttons (28x28 each) with 24px gap between them, starting at 18px from the left edge and 24px from the top. The buttons are: New Chat (新建聊天), Tasks (我的任务), History (历史记录).

#### Scenario: Icons render in correct order and spacing
- **WHEN** the collapsed toolbar is visible
- **THEN** three icon buttons are displayed vertically with new chat at top, tasks in middle, history at bottom, each 28x28px with 24px vertical gap

### Requirement: Active icon highlighting
The currently active icon SHALL be colored #3769FC (blue). Inactive icons SHALL be colored #808191 (gray). Only one icon can be active at a time (the one whose panel is open).

#### Scenario: No panel is open
- **WHEN** no panel is currently expanded
- **THEN** all three icons are displayed in #808191 (gray)

#### Scenario: Tasks panel is open
- **WHEN** the user clicks the Tasks icon and the tasks panel is open
- **THEN** the Tasks icon is colored #3769FC, and the other two icons remain #808191

### Requirement: Hover tooltips
Each icon button SHALL show a tooltip on hover (mouseEnterDelay 0.3s). The tooltip SHALL have a dark semi-transparent background (rgba(0,0,0,0.6)), 4px border-radius, white text (20px Microsoft YaHei), and a left-pointing arrow. The tooltip SHALL appear to the right of the toolbar.

#### Scenario: Hovering over an icon shows its tooltip
- **WHEN** the user hovers over the "New Chat" icon
- **THEN** a dark tooltip labeled "新建聊天" appears to the right of the toolbar with a left-pointing arrow

#### Scenario: Hovering over Tasks icon
- **WHEN** the user hovers over the Tasks icon
- **THEN** a dark tooltip labeled "我的任务" appears to the right of the toolbar

#### Scenario: Hovering over History icon
- **WHEN** the user hovers over the History icon
- **THEN** a dark tooltip labeled "历史记录" appears to the right of the toolbar

### Requirement: Notification badge on Tasks icon
The Tasks icon SHALL display a red notification badge (#FE2842) in the top-right corner when there are unread task alerts. The badge SHALL be pill-shaped (border-radius 12px), contain white text (10px), and show the unread count.

#### Scenario: Tasks have unread alerts
- **WHEN** there are tasks with unread notifications
- **THEN** a red badge with the unread count appears overlapping the top-right of the Tasks icon

#### Scenario: No unread alerts
- **WHEN** there are no unread task notifications
- **THEN** no badge is displayed on the Tasks icon
