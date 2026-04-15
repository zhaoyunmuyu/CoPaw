## ADDED Requirements

### Requirement: Cases API endpoint for listing cases

The system SHALL provide a `GET /cases` endpoint that returns a list of cases visible to the requesting user.

#### Scenario: User requests case list with valid userId
- **WHEN** client sends `GET /cases` with `X-User-Id: A001234` header
- **THEN** system returns array of cases filtered by user mapping, each containing `{id, label, value, sort_order}`

#### Scenario: User requests case list without userId header
- **WHEN** client sends `GET /cases` without `X-User-Id` header
- **THEN** system returns cases from `default` mapping

### Requirement: Cases API endpoint for case detail

The system SHALL provide a `GET /cases/{case_id}` endpoint that returns full case detail including iframe_url and steps.

#### Scenario: User requests existing case detail
- **WHEN** client sends `GET /cases/case-deposit-maturity`
- **THEN** system returns `{id, label, value, detail: {iframe_url, iframe_title, steps}}`

#### Scenario: User requests non-existent case
- **WHEN** client sends `GET /cases/non-existent-id`
- **THEN** system returns `404 Not Found` with error message "Case not found"

### Requirement: Cases API management endpoints

The system SHALL provide management endpoints for case CRUD operations.

#### Scenario: Admin creates new case
- **WHEN** admin sends `POST /cases` with case data `{id, label, value, detail}`
- **THEN** system creates case in cases.json and returns created case

#### Scenario: Admin updates existing case
- **WHEN** admin sends `PUT /cases/case-001` with updated case data
- **THEN** system updates case in cases.json and returns updated case

#### Scenario: Admin deletes existing case
- **WHEN** admin sends `DELETE /cases/case-001`
- **THEN** system removes case from cases.json and returns `{deleted: case_id}`

### Requirement: Cases stored in JSON configuration file

The system SHALL store cases in `WORKING_DIR/cases.json` with structure `{cases: [{id, label, value, sort_order, is_active, detail}]}`.

#### Scenario: System loads cases from file
- **WHEN** API endpoint is called
- **THEN** system reads and parses cases.json file

#### Scenario: Cases file does not exist
- **WHEN** cases.json file is missing
- **THEN** system returns empty cases list instead of error