# Clickstream Data Product — Event Ingestion API

Real-time clickstream analytics platform. This service is the ingestion layer — it accepts user interaction events from web/mobile apps and publishes them to a Kafka stream for downstream processing.

## Tech Stack
- **API**: FastAPI + Pydantic v2
- **Streaming**: Apache Kafka (`clickstream.raw.events` topic)
- **Runtime**: Python 3.11
- **Container**: Docker
- **CI/CD**: GitHub Actions
- **Registry**: Docker Hub

## Local Development (Windows)

```powershell
# 1. Clone the repo
git clone https://github.com/<your-username>/clickstream-data-product.git
cd clickstream-data-product

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the API locally
uvicorn src.ingestion_api.main:app --reload --port 8000

# 5. Run tests
pytest tests/ -v
```

## API Reference

### POST /v1/events
Ingest a batch of clickstream events.

**Headers:** `x-api-key: demo-api-key-123`

**Request body:**
```json
{
  "events": [
    {
      "user_id": "user-001",
      "session_id": "session-abc",
      "event_type": "click",
      "properties": { "page": "/home", "element": "buy-button" }
    }
  ]
}
```

**Response 202:**
```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "accepted_count": 1,
  "rejected_events": [],
  "topic": "clickstream.raw.events"
}
```

### GET /health
```json
{ "status": "healthy", "service": "clickstream-ingestion-api", "version": "1.0.0" }
```

## CI/CD Pipeline
- **CI**: Triggers on every push to `main` and every PR — runs tests, builds Docker image, pushes to Docker Hub
- **CD**: Manual trigger via GitHub Actions → select environment (dev / qa / staging / prod)
- **Approval gate**: `prod` environment requires manual approval before deployment proceeds

## Event Schema

| Field | Type | Required | Description |
|---|---|---|---|
| event_id | UUID string | No (auto-generated) | Unique event identifier |
| user_id | string | Yes | Authenticated user identifier |
| session_id | string | Yes | Browser/app session identifier |
| event_type | enum | Yes | click, view, scroll, purchase |
| timestamp | ISO 8601 | No (auto-generated) | Event occurrence time |
| properties | object | No | Arbitrary event metadata |
 
