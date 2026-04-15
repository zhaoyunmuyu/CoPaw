## ADDED Requirements

### Requirement: Cases management page

The system SHALL provide a management page at `/cases-management` for case CRUD operations and user assignment.

#### Scenario: Admin navigates to cases management
- **WHEN** admin clicks "案例管理" in sidebar
- **THEN** system displays cases management page with case list table

#### Scenario: Case table shows case info
- **WHEN** cases management page loads
- **THEN** table displays columns: ID, 标题, iframe_url, 状态, 操作

### Requirement: Case creation form

The system SHALL provide a drawer form for creating new cases with all required fields.

#### Scenario: Admin opens create form
- **WHEN** admin clicks "+新建案例" button
- **THEN** drawer opens with form fields: ID, 标题, 提问内容, iframe_url, iframe_title, 步骤说明, 排序

#### Scenario: Admin saves new case
- **WHEN** admin fills form and clicks "保存"
- **THEN** system calls `POST /cases` and refreshes case list

### Requirement: Case editing form

The system SHALL provide a drawer form for editing existing cases.

#### Scenario: Admin opens edit form
- **WHEN** admin clicks "编辑" on a case row
- **THEN** drawer opens with pre-filled form data

#### Scenario: Admin saves edited case
- **WHEN** admin modifies form and clicks "保存"
- **THEN** system calls `PUT /cases/{id}` and refreshes case list

### Requirement: Case deletion with confirmation

The system SHALL require confirmation before deleting a case.

#### Scenario: Admin requests case deletion
- **WHEN** admin clicks "删除" on a case row
- **THEN** system shows confirmation modal "确认删除此案例？"

#### Scenario: Admin confirms deletion
- **WHEN** admin clicks "确认" in deletion modal
- **THEN** system calls `DELETE /cases/{id}` and refreshes case list

### Requirement: User assignment tab

The system SHALL provide a tab for managing user-case assignments.

#### Scenario: Admin views user assignments
- **WHEN** admin clicks "用户分配" tab
- **THEN** system displays table: userId | 可见案例（checkbox list）

#### Scenario: Admin adds user assignment
- **WHEN** admin clicks "+添加用户" and enters userId and selects cases
- **THEN** system updates user_cases.json via `PUT /cases/admin/user-mapping`

#### Scenario: Admin modifies user cases
- **WHEN** admin toggles case checkboxes for userId A001234
- **THEN** system updates user_cases.json with new case list