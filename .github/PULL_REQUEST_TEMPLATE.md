## Jira Ticket
[CLICK-101](https://your-jira.atlassian.net/browse/CLICK-101) — Build POST /events ingestion endpoint

## Description
Implements the FastAPI-based event ingestion endpoint that accepts batches of ClickEvent objects, validates them using Pydantic v2, and publishes each event to the Kafka topic `clickstream.raw.events`.

## Acceptance Criteria
- [x] Accepts array of ClickEvent objects (event_id, user_id, session_id, event_type, timestamp, properties)
- [x] Returns 202 Accepted with ingestion_id for valid payloads
- [x] Returns 401 for missing or invalid API key
- [x] Returns 422 with field-level errors for invalid payloads
- [x] Handles batch of up to 1000 events per request
- [x] Publishes each event to `clickstream.raw.events` Kafka topic

## Type of Change
- [x] Feature
- [ ] Bug Fix
- [ ] Refactor
- [ ] Documentation

## Testing
- [x] Unit tests added — 11 test cases, 100% pass rate
- [ ] Integration tests — follow-up ticket CLICK-105
- [ ] Performance tests — follow-up ticket CLICK-106

## CI Checklist
- [x] All unit tests pass
- [x] Docker image builds successfully
- [x] No hardcoded secrets
- [x] Pydantic v2 field validators used throughout
