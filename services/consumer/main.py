"""Ponto de entrada CLI e Docker (ECS Fargate / Docker Compose) do serviço Consumidor."""

from services.consumer.rds_persistence import persist_autor_payload
from services.consumer.sqs_worker import ConsumerService

__all__ = [
    "ConsumerService",
    "persist_autor_payload",
    "main",
]


def main() -> None:
    """Ponto de entrada CLI/Docker do serviço Consumidor."""
    service = ConsumerService()
    service.run_forever()


if __name__ == "__main__":
    main()
