from dataclasses import dataclass
from os import environ

from dotenv import load_dotenv


@dataclass(frozen=True)
class KafkaConfig:
    """Kafka configuration from environment variables."""

    bootstrap_servers: str
    api_key: str
    api_secret: str
    topic: str
    security_protocol: str
    sasl_mechanism: str
    cluster: str

    @classmethod
    def load(cls) -> "KafkaConfig":
        """Load Kafka config from environment variables."""
        load_dotenv()

        bootstrap_servers = environ.get(
            "KAFKA_BOOTSTRAP_SERVERS",
            "pkc-n3603.us-central1.gcp.confluent.cloud:9092",
        )
        api_key = environ.get("KAFKA_API_KEY")
        api_secret = environ.get("KAFKA_API_SECRET")
        topic = environ.get("KAFKA_TOPIC", "ragents-demo")
        security_protocol = environ.get("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
        sasl_mechanism = environ.get("KAFKA_SASL_MECHANISM", "PLAIN")
        cluster = environ.get("KAFKA_CLUSTER", "lkc-rd18y7")

        if not api_key:
            raise ValueError("Missing required environment variable: KAFKA_API_KEY")
        if not api_secret:
            raise ValueError("Missing required environment variable: KAFKA_API_SECRET")

        return cls(
            bootstrap_servers=bootstrap_servers,
            api_key=api_key,
            api_secret=api_secret,
            topic=topic,
            security_protocol=security_protocol,
            sasl_mechanism=sasl_mechanism,
            cluster=cluster,
        )
