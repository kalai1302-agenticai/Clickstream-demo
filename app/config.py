from dataclasses import dataclass
from os import environ
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = environ.get(name, default)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


@dataclass(frozen=True)
class Config:
    kafka_bootstrap_servers: str
    kafka_api_key: str
    kafka_api_secret: str
    kafka_topic: str
    kafka_security_protocol: str
    kafka_sasl_mechanism: str
    kafka_cluster: str

    @classmethod
    def load(cls) -> "Config":
        kafka_bootstrap_servers = _get_env(
            "KAFKA_BOOTSTRAP_SERVERS",
            default="pkc-n3603.us-central1.gcp.confluent.cloud:9092",
            required=False,
        )
        kafka_api_key = _get_env("KAFKA_API_KEY", required=True)
        kafka_api_secret = _get_env("KAFKA_API_SECRET", required=True)
        kafka_topic = _get_env("KAFKA_TOPIC", default="ragents-demo", required=False)
        kafka_security_protocol = _get_env("KAFKA_SECURITY_PROTOCOL", default="SASL_SSL", required=False)
        kafka_sasl_mechanism = _get_env("KAFKA_SASL_MECHANISM", default="PLAIN", required=False)
        kafka_cluster = _get_env("KAFKA_CLUSTER", default="lkc-rd18y7", required=False)

        if not kafka_bootstrap_servers:
            raise ValueError("Missing required environment variable: KAFKA_BOOTSTRAP_SERVERS")
        if not kafka_topic:
            raise ValueError("Missing required environment variable: KAFKA_TOPIC")

        return cls(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            kafka_api_key=kafka_api_key,
            kafka_api_secret=kafka_api_secret,
            kafka_topic=kafka_topic,
            kafka_security_protocol=kafka_security_protocol,
            kafka_sasl_mechanism=kafka_sasl_mechanism,
            kafka_cluster=kafka_cluster,
        )
