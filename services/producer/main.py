"""Ponto de entrada CLI e Docker (ECS Fargate / Docker Compose) para o serviço Produtor."""

from services.producer.client import ExternalAPIClient
from services.producer.de_para_mapper import (
    format_address,
    map_album_to_acordo,
    map_photo_to_documento,
    map_user_to_autor_payload,
)
from services.producer.sqs_publisher import ProducerService

__all__ = [
    "ExternalAPIClient",
    "ProducerService",
    "format_address",
    "map_photo_to_documento",
    "map_album_to_acordo",
    "map_user_to_autor_payload",
    "main",
]


def main() -> None:
    """Ponto de entrada CLI/Docker do serviço Produtor."""
    with ExternalAPIClient() as api_client:
        service = ProducerService(api_client=api_client)
        service.run()


if __name__ == "__main__":
    main()
