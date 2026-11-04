"""Ponto de entrada CLI, Docker e AWS Lambda (SQS Event Source Mapping) do serviço Consumidor."""

import json
from typing import Any, Dict, List

from services.consumer.rds_persistence import persist_autor_payload
from services.consumer.sqs_worker import ConsumerService
from shared.config.database import SessionLocal, init_db
from shared.config.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "ConsumerService",
    "persist_autor_payload",
    "lambda_handler",
    "main",
]


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handler compatível com AWS Lambda Event Source Mapping para SQS (com BatchItemFailures)."""
    init_db()
    service = ConsumerService(
        session_factory=SessionLocal,
        sqs_client=False,
        queue_url="lambda://event-source-mapping",
    )
    records: List[Dict[str, Any]] = event.get("Records", []) if isinstance(event, dict) else []
    batch_item_failures: List[Dict[str, str]] = []

    for record in records:
        message_id = str(record.get("messageId", ""))
        try:
            payload = json.loads(record["body"])
            service.process_payload(payload)
        except Exception as exc:
            logger.error(
                "Erro ao processar record SQS no Lambda",
                exc_info=True,
                extra={"extra_data": {"message_id": message_id, "error": str(exc)}},
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}


def main() -> None:
    """Ponto de entrada CLI/Docker do serviço Consumidor."""
    service = ConsumerService()
    service.run_forever()


if __name__ == "__main__":
    main()
