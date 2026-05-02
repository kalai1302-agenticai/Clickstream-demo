from pydantic import BaseModel


class KafkaEventResponse(BaseModel):
    """Response after publishing event to Kafka."""

    event_id: str
    status: str
    kafka_offset: int
    kafka_partition: int


class KafkaHealthResponse(BaseModel):
    """Kafka health check response."""

    kafka_connected: bool
    kafka_topic: str
    kafka_cluster: str
