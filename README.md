# Clickstream Kafka Producer - Sprint 4

A FastAPI application that implements a Confluent Cloud Kafka producer client for clickstream event ingestion. It validates incoming clickstream events, publishes them to Kafka with guaranteed delivery settings, provides health checks, and exposes producer metrics.

## Features

- `POST /api/v1/events` — accept clickstream events and publish them to Confluent Cloud Kafka
- `GET /health` — verify Kafka connectivity and service health
- `GET /metrics` — expose producer metrics for monitoring
- `POST /api/v1/events/test` — publish sample events for validation

## Prerequisites

- Python 3.10+
- Confluent Cloud Kafka cluster and credentials
- `pip` package manager

## Setup

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Populate `.env` with your Confluent Cloud credentials and topic settings.

3. Install dependencies:

```bash
python -m pip install --no-cache-dir -r requirements.txt
```

## Running Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### POST /api/v1/events

Accepts a clickstream event payload and publishes it to Kafka.

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "session_id": "session_abc",
    "event_type": "page_view",
    "page_url": "https://example.com/product",
    "properties": {"button": "buy_now"},
    "device_type": "web",
    "ip_address": "203.0.113.10"
  }'
```

Successful response:

```json
{
  "event_id": "<uuid>",
  "status": "published",
  "kafka_offset": 12
}
```

### GET /health

Returns Kafka connectivity and health status.

Example response:

```json
{
  "status": "healthy",
  "kafka_connected": true,
  "kafka_topic": "ragents-demo",
  "kafka_cluster": "lkc-rd18y7"
}
```

### GET /metrics

Returns producer metrics for monitoring.

Example response:

```json
{
  "events_published_success": 10,
  "events_published_failed": 0,
  "uptime_seconds": 123
}
```

### POST /api/v1/events/test

Publishes one or more generated sample events.

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/events/test?count=3"
```

## Environment Variables

- `KAFKA_BOOTSTRAP_SERVERS` — Kafka bootstrap server address
- `KAFKA_API_KEY` — Confluent Cloud API key
- `KAFKA_API_SECRET` — Confluent Cloud API secret
- `KAFKA_TOPIC` — Kafka topic name
- `KAFKA_SECURITY_PROTOCOL` — security protocol (default `SASL_SSL`)
- `KAFKA_SASL_MECHANISM` — SASL mechanism (default `PLAIN`)
- `KAFKA_CLUSTER` — Kafka cluster identifier used for diagnostics

## Docker

Build the container:

```bash
docker build -t clickstream-kafka-producer .
```

Run the container:

```bash
docker run -p 8000:8000 --env-file .env clickstream-kafka-producer
```

## Troubleshooting

- If startup fails, verify that `.env` contains valid Kafka credentials.
- Check logs for JSON structured error details.
- Confirm the Kafka bootstrap server and topic are accessible.
