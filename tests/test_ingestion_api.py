"""
Unit tests for the Clickstream Ingestion API.
Run with: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

from src.ingestion_api.main import app

client = TestClient(app)
VALID_KEY = "demo-api-key-123"
AUTH = {"x-api-key": VALID_KEY}


def make_event(**overrides):
    base = {
        "user_id": "user-001",
        "session_id": "session-abc",
        "event_type": "click",
        "properties": {"page": "/home"},
    }
    base.update(overrides)
    return base


class TestHealthCheck:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        response = client.post("/v1/events", json={"events": [make_event()]})
        assert response.status_code == 401

    def test_invalid_api_key_returns_401(self):
        response = client.post(
            "/v1/events",
            json={"events": [make_event()]},
            headers={"x-api-key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_valid_api_key_accepted(self):
        response = client.post(
            "/v1/events",
            json={"events": [make_event()]},
            headers=AUTH,
        )
        assert response.status_code == 202


class TestEventIngestion:
    def test_single_valid_event_accepted(self):
        response = client.post(
            "/v1/events",
            json={"events": [make_event()]},
            headers=AUTH,
        )
        data = response.json()
        assert response.status_code == 202
        assert data["accepted_count"] == 1
        assert data["rejected_events"] == []
        assert data["topic"] == "clickstream.raw.events"
        assert "ingestion_id" in data

    def test_batch_of_events_all_accepted(self):
        events = [make_event(user_id=f"user-{i}") for i in range(10)]
        response = client.post("/v1/events", json={"events": events}, headers=AUTH)
        assert response.status_code == 202
        assert response.json()["accepted_count"] == 10

    def test_all_event_types_accepted(self):
        for event_type in ["click", "view", "scroll", "purchase"]:
            response = client.post(
                "/v1/events",
                json={"events": [make_event(event_type=event_type)]},
                headers=AUTH,
            )
            assert response.status_code == 202

    def test_invalid_event_type_rejected(self):
        response = client.post(
            "/v1/events",
            json={"events": [make_event(event_type="hover")]},
            headers=AUTH,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["accepted_count"] == 0
        assert len(data["detail"]["rejected_events"]) == 1
        assert "Input should be" in data["detail"]["rejected_events"][0]["reason"]

    def test_missing_user_id_rejected(self):
        event = make_event()
        del event["user_id"]
        response = client.post("/v1/events", json={"events": [event]}, headers=AUTH)
        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["accepted_count"] == 0
        assert len(data["detail"]["rejected_events"]) == 1
        assert "Field required" in data["detail"]["rejected_events"][0]["reason"]

    def test_empty_batch_rejected(self):
        response = client.post("/v1/events", json={"events": []}, headers=AUTH)
        assert response.status_code == 422

    def test_batch_limit_1000_accepted(self):
        events = [make_event(user_id=f"user-{i}") for i in range(1000)]
        response = client.post("/v1/events", json={"events": events}, headers=AUTH)
        assert response.status_code == 202
        assert response.json()["accepted_count"] == 1000

    def test_batch_over_1000_rejected(self):
        events = [make_event(user_id=f"user-{i}") for i in range(1001)]
        response = client.post("/v1/events", json={"events": events}, headers=AUTH)
        assert response.status_code == 422

    def test_custom_event_id_preserved(self):
        event = make_event()
        event["event_id"] = "my-custom-id-999"
        response = client.post("/v1/events", json={"events": [event]}, headers=AUTH)
        assert response.status_code == 202

    def test_properties_accepts_arbitrary_keys(self):
        event = make_event(properties={"page": "/checkout", "product_id": "sku-123", "price": 49.99})
        response = client.post("/v1/events", json={"events": [event]}, headers=AUTH)
        assert response.status_code == 202
