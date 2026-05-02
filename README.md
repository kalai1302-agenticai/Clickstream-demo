# Clickstream Event Ingestion API

A FastAPI service that validates clickstream events, publishes them to a Kafka topic in Confluent Cloud, and exposes health and metrics endpoints.

## Features

- `POST /api/v1/events` — accepts clickstream events and publishes them to Kafka
- `GET /health` — checks service and Kafka availability
- `GET /metrics` — returns publishing metrics
- `POST /api/v1/events/test` — generates sample events for end-to-end testing

## Getting Started

1. Copy `.env.example` to `.env`
2. Fill in Kafka credentials and topic values
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Run the application:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

- `KAFKA_BOOTSTRAP_SERVERS` — Kafka bootstrap server list
- `KAFKA_API_KEY` — Confluent Cloud API key
- `KAFKA_API_SECRET` — Confluent Cloud API secret
- `KAFKA_TOPIC` — Kafka topic name
- `KAFKA_SECURITY_PROTOCOL` — security protocol (default `SASL_SSL`)
- `KAFKA_SASL_MECHANISM` — SASL mechanism (default `PLAIN`)
- `KAFKA_CLUSTER` — cluster identifier for diagnostics

## API Endpoints

- `POST /api/v1/events`
  - Body: `ClickstreamEvent`
  - Response: `EventResponse`

- `GET /health`
  - Response: `HealthResponse`

- `GET /metrics`
  - Response: producer metrics

- `POST /api/v1/events/test?count=1`
  - Publishes one or more sample test events

## Notes

- The app reads `.env` automatically at startup via `python-dotenv`.
- Logging is emitted as structured JSON to stdout.
- On shutdown, the Kafka producer flushes outstanding messages.
