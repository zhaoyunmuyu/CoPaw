## ADDED Requirements

### Requirement: Task list section in sidebar
The sidebar SHALL display a "我的任务" section with a collapsible task list. The section header SHALL show the title "我的任务(N)" where N is the task count, along with a collapse/expand toggle icon. Task items SHALL be fetched from the cronjob API.

#### Scenario: Task section display
- **WHEN** the sidebar is visible and tasks exist
- **THEN** the "我的任务(N)" section is displayed with task items below

#### Scenario: Empty task list
- **WHEN** no tasks are configured
- **THEN** the "我的任务(0)" section is displayed with no items or an empty state message

### Requirement: Task item display
Each task item SHALL display a title (color #11142D), an optional subtitle/description (color #808191), and an optional red badge (background #FE2842) showing an unread count.

#### Scenario: Task with unread badge
- **WHEN** a task has unread updates
- **THEN** a red badge with the count number is displayed next to the task title

#### Scenario: Task with subtitle
- **WHEN** a task has a recent update summary
- **THEN** the subtitle is displayed below the title in secondary color (e.g., "昨日5:00 已更新，快来阅读～")

### Requirement: Click task to trigger execution
Clicking a task item SHALL trigger the corresponding scheduled task to execute immediately via the cronjob API, and send the task content as a new chat message.

#### Scenario: Click task item
- **WHEN** the user clicks a task item in the task list
- **THEN** the corresponding cronjob is triggered via `cronjobApi.triggerCronJob(id)` and a new chat message is created with the task content

### Requirement: History section in sidebar
The sidebar SHALL display a "历史记录" section with a collapsible list below the task section. Each history item SHALL display a title (color #4F5060) and a timestamp (color #808191) in "YYYY-MM-DD HH:mm" format.

#### Scenario: History section display
- **WHEN** the sidebar is visible and history items exist
- **THEN** the "历史记录(N)" section shows history items with title and formatted timestamp

#### Scenario: History item click
- **WHEN** the user clicks a history item
- **THEN** the corresponding chat session is loaded (existing session navigation behavior)
