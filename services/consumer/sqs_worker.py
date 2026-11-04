"""Worker Consumidor do AWS SQS e Reprocessador da Dead Letter Queue (DLQ)."""

import json
import time
from typing import Any, Callable, Dict, List, Optional

import boto3
from sqlalchemy.orm import Session

from services.consumer.rds_persistence import persist_autor_payload
from shared.config.database import SessionLocal, init_db
from shared.config.logging import get_correlation_id, get_logger, set_correlation_id
from shared.config.settings import get_settings

logger = get_logger(__name__)


class ConsumerService:
    """Serviço responsável por consumir eventos do SQS e acionar o Upsert no PostgreSQL / RDS."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        sqs_client: Optional[Any] = None,
        queue_url: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.session_factory = session_factory
        self.sqs_client = (
            sqs_client
            if sqs_client is not None
            else boto3.client(
                "sqs",
                region_name=self.settings.AWS_REGION,
                endpoint_url=self.settings.AWS_ENDPOINT_URL,
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
            )
        )
        self.queue_url = queue_url or self._resolve_queue_url()

    def _resolve_queue_url(self) -> str:
        """Obtém a URL da fila SQS principal configurada."""
        if self.settings.SQS_QUEUE_URL:
            return self.settings.SQS_QUEUE_URL
        response = self.sqs_client.get_queue_url(QueueName=self.settings.SQS_QUEUE_NAME)
        return str(response["QueueUrl"])

    def _resolve_dlq_url(self) -> str:
        """Obtém a URL da fila Dead Letter Queue (DLQ) configurada."""
        if self.settings.SQS_DLQ_URL:
            return self.settings.SQS_DLQ_URL
        response = self.sqs_client.get_queue_url(QueueName=self.settings.SQS_DLQ_NAME)
        return str(response["QueueUrl"])

    def process_payload(self, payload: Dict[str, Any]) -> int:
        """Delega a persistência transacional (Upsert) do payload para o módulo rds_persistence."""
        return persist_autor_payload(self.session_factory, payload)

    def poll_once(self, max_messages: Optional[int] = None, wait_time_seconds: int = 5) -> int:
        """Lê um lote de mensagens da fila SQS, persiste no banco e remove da fila após sucesso."""
        batch_size = max_messages or self.settings.CONSUMER_MAX_MESSAGES
        response = self.sqs_client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=min(max(batch_size, 1), 10),
            WaitTimeSeconds=wait_time_seconds,
            MessageAttributeNames=["All"],
        )
        messages: List[Dict[str, Any]] = response.get("Messages", [])
        if not messages:
            return 0

        processed_count = 0
        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            message_id = message.get("MessageId", "unknown")
            attrs = message.get("MessageAttributes") or {}
            cid_attr = attrs.get("CorrelationId", {}).get("StringValue")
            set_correlation_id(cid_attr)
            try:
                body = json.loads(message["Body"])
                self.process_payload(body)
                self.sqs_client.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle,
                )
                processed_count += 1
            except Exception as exc:
                logger.error(
                    "Erro ao processar mensagem do SQS. Mensagem permanecerá para retry/DLQ.",
                    exc_info=True,
                    extra={
                        "extra_data": {
                            "message_id": message_id,
                            "correlation_id": get_correlation_id(),
                            "error": str(exc),
                        }
                    },
                )
        return processed_count

    def reprocess_dlq(self, max_messages: int = 10) -> Dict[str, int]:
        """Lê mensagens retidas na Dead Letter Queue (DLQ), reprocessa de forma idempotente e remove da DLQ."""
        dlq_url = self._resolve_dlq_url()
        response = self.sqs_client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=min(max(max_messages, 1), 10),
            WaitTimeSeconds=1,
            MessageAttributeNames=["All"],
        )
        messages: List[Dict[str, Any]] = response.get("Messages", [])
        reprocessed = 0
        failed = 0

        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            message_id = message.get("MessageId", "unknown")
            attrs = message.get("MessageAttributes") or {}
            cid_attr = attrs.get("CorrelationId", {}).get("StringValue")
            set_correlation_id(cid_attr)
            try:
                body = json.loads(message["Body"])
                self.process_payload(body)
                self.sqs_client.delete_message(
                    QueueUrl=dlq_url,
                    ReceiptHandle=receipt_handle,
                )
                reprocessed += 1
                logger.info(
                    "Mensagem da DLQ reprocessada com sucesso",
                    extra={"extra_data": {"message_id": message_id, "correlation_id": get_correlation_id()}},
                )
            except Exception as exc:
                failed += 1
                logger.error(
                    "Falha ao reprocessar mensagem da DLQ",
                    exc_info=True,
                    extra={"extra_data": {"message_id": message_id, "error": str(exc)}},
                )

        return {"reprocessed_count": reprocessed, "failed_count": failed}

    def run_forever(self) -> None:
        """Executa o loop contínuo de consumo da fila SQS."""
        init_db()
        logger.info(
            "Iniciando Consumer Worker SQS",
            extra={"extra_data": {"queue_url": self.queue_url}},
        )
        while True:
            try:
                count = self.poll_once()
                if count == 0:
                    time.sleep(self.settings.CONSUMER_POLL_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.info("Encerrando Consumer Worker SQS por sinal de interrupção.")
                break
            except Exception as exc:
                logger.error(
                    "Falha no ciclo de polling do Consumer Worker",
                    exc_info=True,
                    extra={"extra_data": {"error": str(exc)}},
                )
                time.sleep(self.settings.CONSUMER_POLL_INTERVAL_SECONDS)
