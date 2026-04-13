
"""
Clickstream Demo — Auto-create Jira stories from PRD epics.
Run: python create_jira_stories.py
"""

import urllib.request
import urllib.error
import json
import base64
import os

# ── CONFIG ── update these three values ──────────────────────────────────────
JIRA_URL      = "https://karuppanankalaivani.atlassian.net"
JIRA_EMAIL = "karuppanankalaivani@gmail.com"
JIRA_TOKEN = "ATATT3xFfGF0cTlWJF6S8yTSzXcOxCMhINe3cKCD3cEDJzERlocwJ1FiC5gqjlceq3uD0ofGJL6qJmYw6W-fZbMgRoH1zGxs4kaTCCW1xxfTDEj6akKyi3pXyxWIAwoc0M23jVUsD95OG1Vo1eAJGZFG4Ehq4bRjkd5FMqFfB0DQvOu2C764DIk=069A1BFB"
PROJECT_KEY = "SCRUM"
# ─────────────────────────────────────────────────────────────────────────────

STORIES = [
    # ── Epic 1: Event Ingestion Infrastructure ────────────────────────────────
    {
        "summary": "Implement RESTful API for event ingestion",
        "description": "Build a FastAPI POST /v1/events endpoint that accepts JSON clickstream event batches, validates with Pydantic v2, and publishes to Kafka topic clickstream.raw.events.\n\nAcceptance Criteria:\n- Accepts array of ClickEvent objects (event_id, user_id, session_id, event_type, timestamp, properties)\n- Returns 202 Accepted with ingestion_id\n- Returns 401 for invalid API key\n- Handles batch of up to 1000 events\n- p99 latency < 200ms at 10,000 events/sec",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 5,
        "epic": "Event Ingestion Infrastructure",
    },
    {
        "summary": "Add mandatory field validation to ingestion API",
        "description": "Implement Pydantic v2 validation for required fields (user_id, event_type, timestamp). Reject invalid payloads with 422 and field-level error messages.\n\nAcceptance Criteria:\n- Validates presence of mandatory fields\n- Returns 422 with detailed error for invalid events\n- Logs validation failures\n- No performance impact > 10%",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 3,
        "epic": "Event Ingestion Infrastructure",
    },
    {
        "summary": "Implement API key authentication for ingestion endpoint",
        "description": "Add API key authentication via x-api-key header. Return 401 for missing or invalid keys. Support multiple valid keys loaded from environment variables.\n\nAcceptance Criteria:\n- API accepts valid keys in x-api-key header\n- Returns 401 for missing or invalid keys\n- Keys loaded from environment variables\n- Tests cover key validation",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 5,
        "epic": "Event Ingestion Infrastructure",
    },
    {
        "summary": "Support batch ingestion mode (up to 1000 events)",
        "description": "Enable batch submission of multiple events in a single API request. Return summary of accepted and rejected events per batch.\n\nAcceptance Criteria:\n- API accepts arrays of up to 1000 events\n- Returns accepted_count and rejected_events list\n- Returns 422 for batches over 1000 events\n- Performance: < 500ms for batch of 100 events",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 8,
        "epic": "Event Ingestion Infrastructure",
    },
    # ── Epic 2: Stream Processing Pipeline ───────────────────────────────────
    {
        "summary": "Implement real-time event transformation pipeline",
        "description": "Build a stream processing pipeline using Apache Flink or Kafka Streams that transforms, filters and enriches incoming clickstream events in real time.\n\nAcceptance Criteria:\n- Processes events within 500ms end-to-end\n- Supports configurable transformation rules\n- Handles 100K events/sec sustained throughput\n- Exactly-once processing guaranteed",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 13,
        "epic": "Stream Processing Pipeline",
    },
    {
        "summary": "Add windowed aggregation support (tumbling, sliding, session)",
        "description": "Implement windowed operations for time-based aggregations including tumbling windows, sliding windows and session windows.\n\nAcceptance Criteria:\n- Supports tumbling windows (fixed time intervals)\n- Supports sliding windows (overlapping intervals)\n- Supports session windows (activity-based)\n- SQL-like syntax for defining window operations",
        "issuetype": "Story",
        "priority": "Medium",
        "story_points": 8,
        "epic": "Stream Processing Pipeline",
    },
    # ── Epic 3: Data Quality Framework ───────────────────────────────────────
    {
        "summary": "Implement schema validation and malformed event rejection",
        "description": "Build automated schema validation layer that validates every incoming event against the defined JSON schema and routes malformed events to a dead-letter queue.\n\nAcceptance Criteria:\n- Validates events against JSON schema\n- Routes invalid events to dead-letter topic\n- Returns detailed error messages per field\n- Audit trail for all rejected events",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 5,
        "epic": "Data Quality Framework",
    },
    {
        "summary": "Add event enrichment (geolocation, device detection)",
        "description": "Automatically enrich incoming events with derived attributes including geolocation from IP address and device type detection from user agent.\n\nAcceptance Criteria:\n- Enriches events with country, city from IP\n- Detects device type (mobile, desktop, tablet)\n- Enrichment adds < 50ms processing overhead\n- Handles null/missing IP gracefully",
        "issuetype": "Story",
        "priority": "Medium",
        "story_points": 5,
        "epic": "Data Quality Framework",
    },
    # ── Epic 4: Self-Service Data Access ─────────────────────────────────────
    {
        "summary": "Expose real-time event stream via REST API",
        "description": "Build a queryable REST API layer that allows downstream analytics teams to access both real-time and historical clickstream data with filtering, sorting and pagination.\n\nAcceptance Criteria:\n- GET /v1/events with filter, sort, pagination\n- Supports time range queries\n- Response time < 100ms for real-time data\n- Supports SQL-like query syntax",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 8,
        "epic": "Self-Service Data Access",
    },
    {
        "summary": "Implement role-based access control (RBAC) for data access",
        "description": "Build RBAC system to control which teams can access which data streams. Support reader, writer and admin roles with fine-grained permissions.\n\nAcceptance Criteria:\n- Three roles: reader, writer, admin\n- Role assignments managed via admin API\n- All access attempts logged for audit\n- GDPR-compliant data masking for PII fields",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 8,
        "epic": "Self-Service Data Access",
    },
    # ── Epic 5: Platform Administration ──────────────────────────────────────
    {
        "summary": "Build pipeline health monitoring dashboard",
        "description": "Create a monitoring dashboard that shows real-time pipeline health metrics including throughput, latency, error rates and Kafka consumer lag.\n\nAcceptance Criteria:\n- Dashboard shows events/sec, p99 latency, error rate\n- Kafka consumer lag visible per topic\n- Alerts triggered on latency > 500ms or error rate > 0.1%\n- Historical metrics retained for 30 days",
        "issuetype": "Story",
        "priority": "Medium",
        "story_points": 8,
        "epic": "Platform Administration",
    },
    {
        "summary": "Implement CI/CD pipeline for automated deployment",
        "description": "Set up GitHub Actions CI/CD pipeline with automated testing, Docker image build, security scanning and progressive deployment across dev, qa, staging and prod environments.\n\nAcceptance Criteria:\n- CI triggers on every PR and merge to main\n- All unit tests must pass before merge\n- Docker image pushed to registry with commit SHA tag\n- CD deploys progressively: dev > qa > staging > prod\n- Prod deployment requires manual approval",
        "issuetype": "Story",
        "priority": "High",
        "story_points": 8,
        "epic": "Platform Administration",
    },
]


def make_auth_header(email: str, token: str) -> str:
    credentials = f"{email}:{token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def get_issue_types(auth_header: str, project_key: str) -> dict:
    url = f"{JIRA_URL}/rest/api/3/project/{project_key}"
    req = urllib.request.Request(url, headers={
        "Authorization": auth_header,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data


def create_story(auth_header: str, story: dict) -> dict:
    url = f"{JIRA_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "summary": story["summary"],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": story["description"]}],
                    }
                ],
            },
            "issuetype": {"name": "Story"},
            "priority": {"name": story["priority"]},
            "labels": [story["epic"].replace(" ", "-")],
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ERROR {e.code}: {error_body}")
        return {}


def main():
    print("=" * 60)
    print("  Clickstream Demo — Jira Story Creator")
    print("=" * 60)

    auth_header = make_auth_header(JIRA_EMAIL, JIRA_TOKEN)

    print(f"\nCreating {len(STORIES)} stories in project {PROJECT_KEY}...\n")

    created = []
    failed = []

    for i, story in enumerate(STORIES, 1):
        print(f"[{i:02d}/{len(STORIES)}] Creating: {story['summary'][:55]}...")
        result = create_story(auth_header, story)
        if result.get("key"):
            ticket_url = f"{JIRA_URL}/browse/{result['key']}"
            print(f"         Created: {result['key']} — {ticket_url}")
            created.append(result["key"])
        else:
            print(f"         FAILED")
            failed.append(story["summary"])

    print("\n" + "=" * 60)
    print(f"  Done! {len(created)} created, {len(failed)} failed")
    print("=" * 60)

    if created:
        print(f"\nView your board:")
        print(f"  {JIRA_URL}/jira/software/projects/{PROJECT_KEY}/boards")

    if failed:
        print(f"\nFailed stories:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()