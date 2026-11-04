"""Ponto de entrada CLI, Docker e AWS Lambda (EventBridge) para o serviço Produtor."""

from typing import Any, Dict

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
    "lambda_handler",
    "main",
]


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handler compatível com AWS Lambda para execução serverless agendada (EventBridge)."""
    max_users = event.get("max_users") if isinstance(event, dict) else None
    with ExternalAPIClient() as api_client:
        service = ProducerService(api_client=api_client)
        message_ids = service.run(max_users=max_users)
    return {
        "statusCode": 200,
        "publishedCount": len(message_ids),
        "messageIds": message_ids,
    }


def main() -> None:
    """Ponto de entrada CLI/Docker do serviço Produtor."""
    with ExternalAPIClient() as api_client:
        service = ProducerService(api_client=api_client)
        service.run()


if __name__ == "__main__":
    main()
