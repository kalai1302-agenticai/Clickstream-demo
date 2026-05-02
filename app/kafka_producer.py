from __future__ import annotations

import asyncio
import json
import logging
import threading
from time import monotonic
from typing import Any, Dict, Optional

from confluent_kafka import KafkaError, KafkaException, Producer

from app.config import Config

logger = logging.getLogger(__name__)


class KafkaProducerError(Exception):
    """Raised when Kafka produce operations fail."""


class KafkaProducerClient:
    """Kafka producer client for Confluent Cloud."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._producer = Producer(
            {
                "bootstrap.servers": config.kafka_bootstrap_servers,
                "security.protocol": config.kafka_security_protocol,
                "sasl.mechanisms": config.kafka_sasl_mechanism,
                "sasl.username": config.kafka_api_key,
                "sasl.password": config.kafka_api_secret,
                "acks": "all",
                "retries": 10,
                "compression.type": "snappy",
                "max.in.flight.requests.per.connection": 5,
                "client.id": "clickstream-producer",
            }
        )
        self.events_published_success = 0
        self.events_published_failed = 0
        self._metrics_lock = threading.Lock()
        self._start_time = monotonic()
        logger.info("Kafka producer initialized successfully", extra={"bootstrap_servers": config.kafka_bootstrap_servers})

    def validate_connection(self, timeout: float = 10.0) -> bool:
        """Validate Kafka connectivity by listing topics."""
        try:
            metadata = self._producer.list_topics(timeout=timeout)
            if metadata.topics is None:
                raise KafkaProducerError("Kafka returned no topic metadata")
            logger.info("Kafka connection validated successfully", extra={"topic_count": len(metadata.topics)})
            return True
        except (KafkaException, KafkaError) as exc:
            logger.error("Kafka connection failed", exc_info=exc)
            return False
        except Exception as exc:
            logger.error("Kafka connection validation error", exc_info=exc)
            return False

    async def publish_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish an event to Kafka and return metadata."""
        return await asyncio.get_running_loop().run_in_executor(None, self._publish_sync, event_data)

    def _publish_sync(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payload = json.dumps(event_data, default=str)
        except (TypeError, ValueError) as exc:
            logger.error("Failed to serialize event payload", exc_info=exc, extra={"event_data": event_data})
            raise KafkaProducerError("Failed to serialize event payload") from exc

        completion_event = threading.Event()
        result: Dict[str, Any] = {}
        exception: Optional[Exception] = None

        def delivery_callback(err: Optional[KafkaError], msg: Optional[Any]) -> None:
            nonlocal result, exception
            if err is not None:
                logger.error(
                    "Failed to publish event to Kafka",
                    exc_info=err,
                    extra={"topic": self._config.kafka_topic, "event_data": event_data},
                )
                with self._metrics_lock:
                    self.events_published_failed += 1
                exception = KafkaProducerError(str(err))
                completion_event.set()
                return

            assert msg is not None
            offset = msg.offset()
            partition = msg.partition()
            logger.info(
                "Event published to Kafka",
                extra={"event_id": event_data.get("event_id"), "offset": offset, "partition": partition},
            )
            with self._metrics_lock:
                self.events_published_success += 1
            result = {"offset": offset, "partition": partition}
            completion_event.set()

        try:
            self._producer.produce(
                topic=self._config.kafka_topic,
                value=payload,
                callback=delivery_callback,
            )
            self._producer.poll(0)
            self._producer.flush(10)
        except BufferError as exc:
            logger.error("Kafka producer buffer error", exc_info=exc)
            raise KafkaProducerError("Kafka producer buffer error") from exc
        except KafkaException as exc:
            logger.error("Kafka produce failed", exc_info=exc)
            raise KafkaProducerError("Kafka produce failed") from exc
        except Exception as exc:
            logger.error("Unexpected Kafka publish error", exc_info=exc)
            raise KafkaProducerError("Unexpected Kafka publish error") from exc

        completed = completion_event.wait(10)
        if not completed:
            raise KafkaProducerError("Kafka delivery callback did not complete")
        if exception is not None:
            raise exception
        return result

    def get_metrics(self) -> Dict[str, Any]:
        uptime_seconds = int(monotonic() - self._start_time)
        with self._metrics_lock:
            return {
                "events_published_success": self.events_published_success,
                "events_published_failed": self.events_published_failed,
                "uptime_seconds": uptime_seconds,
            }

    def close(self) -> None:
        """Flush and close the Kafka producer gracefully."""
        try:
            self._producer.flush(10)
            logger.info("Kafka producer flushed and closed successfully")
        except Exception as exc:
            logger.error("Kafka producer shutdown failed", exc_info=exc)
