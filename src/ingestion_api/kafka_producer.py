from __future__ import annotations

import asyncio
import json
import logging
import threading
from time import monotonic
from typing import Any, Dict

from confluent_kafka import KafkaError, KafkaException, Producer

logger = logging.getLogger(__name__)


class KafkaProducerError(Exception):
    """Raised when Kafka produce operations fail."""


class KafkaProducerClient:
    """Kafka producer client for Confluent Cloud."""

    def __init__(
        self,
        bootstrap_servers: str,
        api_key: str,
        api_secret: str,
        topic: str,
        security_protocol: str = "SASL_SSL",
        sasl_mechanism: str = "PLAIN",
    ) -> None:
        """Initialize Kafka producer with Confluent Cloud credentials."""
        self._topic = topic
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": security_protocol,
            "sasl.mechanisms": sasl_mechanism,
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "acks": "all",
            "retries": 10,
            "compression.type": "snappy",
            "max.in.flight.requests.per.connection": 5,
            "client.id": "clickstream-producer",
        })

        self.events_published_success = 0
        self.events_published_failed = 0
        self._metrics_lock = threading.Lock()
        self._start_time = monotonic()

        logger.info(
            "Kafka producer initialized successfully",
            extra={"bootstrap_servers": bootstrap_servers, "topic": topic},
        )

    def validate_connection(self, timeout: float = 10.0) -> bool:
        """Validate Kafka connectivity by listing topics."""
        try:
            metadata = self._producer.list_topics(timeout=timeout)
            if metadata is None:
                raise KafkaProducerError("Kafka returned no metadata")
            if metadata.topics is None:
                raise KafkaProducerError("Kafka metadata contains no topics")
            logger.debug(
                "Kafka connection validated successfully, topic count=%d",
                len(metadata.topics),
            )
            if self._topic not in metadata.topics:
                logger.warning(
                    "Kafka topic '%s' not found during validation. Available topics: %s",
                    self._topic,
                    ", ".join(sorted(metadata.topics.keys())),
                )
            return True
        except KafkaException as exc:
            raise KafkaProducerError("Failed to validate Kafka connection") from exc

    async def publish_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish an event to Kafka and return metadata."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Dict[str, Any]] = loop.create_future()

        def delivery_callback(error: KafkaError, message: Any) -> None:
            if future.done():
                return
            if error is not None and error.code() != KafkaError._PARTITION_EOF:
                self._increment_failed()
                future.set_exception(
                    KafkaProducerError(
                        f"Kafka delivery failed: {error.str()}"
                    )
                )
                return

            if message is None:
                self._increment_failed()
                future.set_exception(
                    KafkaProducerError("Kafka delivery callback received no message")
                )
                return

            self._increment_success()
            future.set_result(
                {
                    "event_id": str(event_data.get("event_id", "")),
                    "status": "published",
                    "kafka_offset": message.offset(),
                    "kafka_partition": message.partition(),
                }
            )

        try:
            self._producer.produce(
                topic=self._topic,
                value=json.dumps(event_data, default=str).encode("utf-8"),
                callback=delivery_callback,
            )
            self._producer.poll(0.0)
        except BufferError as exc:
            self._increment_failed()
            raise KafkaProducerError(
                "Kafka producer queue is full, unable to publish event"
            ) from exc
        except KafkaException as exc:
            self._increment_failed()
            raise KafkaProducerError(
                "Failed to enqueue event for Kafka delivery"
            ) from exc

        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError as exc:
            raise KafkaProducerError(
                "Timeout waiting for Kafka delivery confirmation"
            ) from exc

    def get_metrics(self) -> Dict[str, Any]:
        """Return publish metrics."""
        elapsed_seconds = monotonic() - self._start_time
        with self._metrics_lock:
            return {
                "events_published_success": self.events_published_success,
                "events_published_failed": self.events_published_failed,
                "uptime_seconds": elapsed_seconds,
                "topic": self._topic,
            }

    def close(self) -> None:
        """Flush and close the Kafka producer gracefully."""
        self._producer.flush(10.0)
        logger.info("Kafka producer flushed and closed successfully")
