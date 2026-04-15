## ADDED Requirements

### Requirement: User-specific case list filtering

The system SHALL filter the case list based on the requesting user's userId, returning only cases assigned to that user.

#### Scenario: User with custom mapping requests case list
- **WHEN** user with `userId: A001234` requests `GET /cases` and user_cases.json contains `{"A001234": ["case-1", "case-2"]}`
- **THEN** system returns only cases with ids `case-1` and `case-2`

#### Scenario: User without custom mapping requests case list
- **WHEN** user with `userId: NEW999` requests `GET /cases` and user_cases.json does not contain `NEW999`
- **THEN** system returns cases from `default` mapping

### Requirement: User-case mapping configuration

The system SHALL store user-case mappings in `WORKING_DIR/user_cases.json` with structure `{user_cases: {userId: [case_id1, case_id2]}}`.

#### Scenario: Default mapping always exists
- **WHEN** user_cases.json is loaded
- **THEN** system ensures `default` key exists with at least one case id

### Requirement: userId source priority

The system SHALL determine userId from multiple sources with defined priority: X-User-Id header > query parameter > default fallback.

#### Scenario: userId from header takes priority
- **WHEN** request has `X-User-Id: A001234` header and `?user_id=B002456` query parameter
- **THEN** system uses `A001234` from header

#### Scenario: userId from query parameter when no header
- **WHEN** request has no `X-User-Id` header but has `?user_id=B002456`
- **THEN** system uses `B002456` from query parameter

#### Scenario: userId fallback to default
- **WHEN** request has no userId header and no query parameter
- **THEN** system uses `"default"` as userId

### Requirement: User mapping management API

The system SHALL provide endpoints for managing user-case mappings.

#### Scenario: Admin views user mappings
- **WHEN** admin sends `GET /cases/admin/user-mapping`
- **THEN** system returns `{user_cases: {...}}` object

#### Scenario: Admin updates user mappings
- **WHEN** admin sends `PUT /cases/admin/user-mapping` with `{default: ["case-1", "case-2"], A001234: ["case-1"]}`
- **THEN** system updates user_cases.json and returns `{success: true}`