"""Publicador SQS do Produtor: orquestra a extração da API externa, De-Para e envio para a fila AWS SQS."""

import json
from typing import Any, Dict, List, Optional

import boto3

from services.producer.client import ExternalAPIClient
from services.producer.de_para_mapper import (
    map_album_to_acordo,
    map_user_to_autor_payload,
)
from shared.config.logging import get_correlation_id, get_logger, set_correlation_id
from shared.config.settings import get_settings

logger = get_logger(__name__)


class ProducerService:
    """Orquestra a extração da API externa, transformação (De-Para) e publicação na fila SQS."""

    def __init__(
        self,
        api_client: Optional[ExternalAPIClient] = None,
        sqs_client: Optional[Any] = None,
        queue_url: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.api_client = api_client or ExternalAPIClient()
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

    def build_autor_message(self, user_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Constrói o payload hierárquico completo (Autor -> Acordos -> Documentos) para um autor."""
        user_id = int(user_summary["id"])
        user_detail = self.api_client.get_user_by_id(user_id) or user_summary
        raw_albums = self.api_client.get_user_albums(user_id)

        acordos_mapeados: List[Dict[str, Any]] = []
        for album in raw_albums:
            album_id = int(album["id"])
            photos = self.api_client.get_album_photos(album_id)
            acordos_mapeados.append(map_album_to_acordo(album, photos))

        return map_user_to_autor_payload(user_detail, acordos_mapeados)

    def publish_message(self, payload: Dict[str, Any]) -> str:
        """Publica o payload JSON de um autor e seus acordos na fila AWS SQS com CorrelationId."""
        autor_id = payload["autor"]["id"]
        correlation_id = get_correlation_id()
        response = self.sqs_client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(payload, ensure_ascii=False),
            MessageAttributes={
                "AutorId": {
                    "DataType": "Number",
                    "StringValue": str(autor_id),
                },
                "EventType": {
                    "DataType": "String",
                    "StringValue": "ACORDO_SYNC",
                },
                "CorrelationId": {
                    "DataType": "String",
                    "StringValue": correlation_id,
                },
            },
        )
        message_id = str(response.get("MessageId", ""))
        logger.info(
            "Mensagem publicada com sucesso no SQS",
            extra={
                "extra_data": {
                    "autor_id": autor_id,
                    "message_id": message_id,
                    "correlation_id": correlation_id,
                    "total_acordos": len(payload.get("acordos", [])),
                }
            },
        )
        return message_id

    def run(self, max_users: Optional[int] = None) -> List[str]:
        """Executa o fluxo completo do produtor para todos os autores (ou limite especificado)."""
        set_correlation_id()
        limit = max_users if max_users is not None else self.settings.PRODUCER_MAX_USERS
        users = self.api_client.get_users()
        if limit and limit > 0:
            users = users[:limit]

        published_ids: List[str] = []
        logger.info(
            "Iniciando processamento do Producer",
            extra={"extra_data": {"total_autores_para_processar": len(users)}},
        )

        for user in users:
            payload = self.build_autor_message(user)
            msg_id = self.publish_message(payload)
            published_ids.append(msg_id)

        logger.info(
            "Execução do Producer concluída com sucesso",
            extra={"extra_data": {"mensagens_publicadas": len(published_ids)}},
        )
        return published_ids
