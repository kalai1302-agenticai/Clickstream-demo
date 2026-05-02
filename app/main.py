from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Config
from app.kafka_producer import KafkaProducerClient, KafkaProducerError
from app.models import ClickstreamEvent, EventResponse, HealthResponse

logger = logging.getLogger(__name__)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in {"msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "name"}:
                continue
            if value is not None:
                payload[key] = value
        return json.dumps(payload)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def get_correlation_id(request: Request) -> str:
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    return correlation_id


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Clickstream Kafka Producer")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        correlation_id = get_correlation_id(request)
        request.state.correlation_id = correlation_id
        logger.info(
            "Incoming request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "correlation_id": correlation_id,
            },
        )
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.on_event("startup")
    async def on_startup() -> None:
        try:
            config = Config.load()
            app.state.config = config
            app.state.kafka_client = KafkaProducerClient(config)
            if not app.state.kafka_client.validate_connection():
                raise RuntimeError("Kafka connectivity validation failed")
            app.state.start_time = datetime.now(timezone.utc)
        except Exception as exc:
            logger.error("Application startup failed", exc_info=exc)
            raise

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        kafka_client: Optional[KafkaProducerClient] = getattr(app.state, "kafka_client", None)
        if kafka_client is not None:
            kafka_client.close()

    def get_kafka_client() -> KafkaProducerClient:
        kafka_client = getattr(app.state, "kafka_client", None)
        if kafka_client is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kafka producer is not initialized")
        return kafka_client

    @app.post("/api/v1/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
    async def publish_event(event: ClickstreamEvent, kafka_client: KafkaProducerClient = Depends(get_kafka_client), request: Request = Depends()) -> EventResponse:
        try:
            metadata = await kafka_client.publish_event(event.model_dump())
            return EventResponse(
                event_id=event.event_id,
                status="published",
                kafka_offset=metadata["offset"],
                kafka_partition=metadata["partition"],
            )
        except KafkaProducerError as exc:
            logger.error(
                "Kafka publish failed",
                exc_info=exc,
                extra={"event_id": event.event_id, "correlation_id": request.state.correlation_id},
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to publish event to Kafka") from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        kafka_client = get_kafka_client()
        healthy = kafka_client.validate_connection()
        if healthy:
            return HealthResponse(
                status="healthy",
                kafka_connected=True,
                kafka_topic=app.state.config.kafka_topic,
                kafka_cluster=app.state.config.kafka_cluster,
            )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kafka cluster is unreachable")

    @app.get("/metrics")
    async def metrics() -> Dict[str, Any]:
        kafka_client = get_kafka_client()
        return kafka_client.get_metrics()

    @app.post("/api/v1/events/test")
    async def publish_test_events(count: int = 1, kafka_client: KafkaProducerClient = Depends(get_kafka_client)) -> Dict[str, Any]:
        if count < 1 or count > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="count must be between 1 and 100")

        published_event_ids = []
        for _ in range(count):
            sample_event = ClickstreamEvent(
                user_id=f"user_{uuid.uuid4().hex[:8]}",
                session_id=f"session_{uuid.uuid4().hex[:8]}",
                event_type="page_view",
                page_url="https://example.com/test",
                properties={"referrer": "https://google.com", "sample": True},
                device_type="web",
                ip_address="127.0.0.1",
            )
            metadata = await kafka_client.publish_event(sample_event.model_dump())
            published_event_ids.append(sample_event.event_id)

        return {"published_event_ids": published_event_ids, "count": len(published_event_ids)}

    return app


app = create_app()
