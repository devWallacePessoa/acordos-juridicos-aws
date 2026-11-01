"""Worker e Lambda Handler do Consumidor SQS com persistência transacional idempotente (Upsert)."""

import json
import time
from typing import Any, Callable, Dict, List, Optional

import boto3
from sqlalchemy.orm import Session

from shared.config.database import SessionLocal, init_db
from shared.config.logging import get_logger
from shared.config.settings import get_settings
from shared.models.entities import AcordoORM, AutorORM, DocumentoORM

logger = get_logger(__name__)


class ConsumerService:
    """Serviço responsável por consumir eventos do SQS e realizar Upsert no PostgreSQL."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        sqs_client: Optional[Any] = None,
        queue_url: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.session_factory = session_factory
        self.sqs_client = sqs_client or boto3.client(
            "sqs",
            region_name=self.settings.AWS_REGION,
            endpoint_url=self.settings.AWS_ENDPOINT_URL,
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
        )
        self.queue_url = queue_url or self._resolve_queue_url()

    def _resolve_queue_url(self) -> str:
        """Obtém a URL da fila SQS configurada."""
        if self.settings.SQS_QUEUE_URL:
            return self.settings.SQS_QUEUE_URL
        response = self.sqs_client.get_queue_url(QueueName=self.settings.SQS_QUEUE_NAME)
        return str(response["QueueUrl"])

    def process_payload(self, payload: Dict[str, Any]) -> int:
        """Persiste de forma transacional e idempotente (merge/upsert) um Autor, seus Acordos e Documentos."""
        if "autor" not in payload or not isinstance(payload["autor"], dict):
            raise ValueError("Payload inválido: chave obrigatória 'autor' ausente ou malformada.")

        autor_data = payload["autor"]
        empresa_data = autor_data.get("empresa") or {}
        acordos_data: List[Dict[str, Any]] = payload.get("acordos", [])

        autor_id = int(autor_data["id"])

        with self.session_factory() as session:
            with session.begin():
                autor_entity = AutorORM(
                    id=autor_id,
                    nome=str(autor_data["nome"]),
                    email=str(autor_data["email"]),
                    telefone=str(autor_data["telefone"]),
                    endereco=str(autor_data["endereco"]),
                    empresa_nome=str(empresa_data.get("nome", "")),
                    empresa_segmento=str(empresa_data.get("segmento", "")),
                )
                session.merge(autor_entity)

                for acordo_item in acordos_data:
                    acordo_id = int(acordo_item["id"])
                    acordo_entity = AcordoORM(
                        id=acordo_id,
                        autor_id=autor_id,
                        titulo=str(acordo_item["titulo"]),
                    )
                    session.merge(acordo_entity)

                    for doc_item in acordo_item.get("documentos", []):
                        doc_entity = DocumentoORM(
                            id=int(doc_item["id"]),
                            acordo_id=acordo_id,
                            titulo=str(doc_item["titulo"]),
                            url=str(doc_item["url"]),
                            thumbnail_url=str(doc_item.get("thumbnailUrl") or doc_item.get("thumbnail_url") or ""),
                        )
                        session.merge(doc_entity)

        logger.info(
            "Autor, acordos e documentos persistidos com sucesso",
            extra={
                "extra_data": {
                    "autor_id": autor_id,
                    "qtd_acordos": len(acordos_data),
                }
            },
        )
        return autor_id

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
                    extra={"extra_data": {"message_id": message_id, "error": str(exc)}},
                )
        return processed_count

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


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handler compatível com AWS Lambda Event Source Mapping para SQS (com BatchItemFailures)."""
    init_db()
    service = ConsumerService(sqs_client=False)
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
