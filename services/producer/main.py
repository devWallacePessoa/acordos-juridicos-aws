"""Serviço Produtor: realiza o De-Para da API pública para o domínio de Acordos e envia ao AWS SQS."""

import json
from typing import Any, Dict, List, Optional

import boto3

from services.producer.client import ExternalAPIClient
from shared.config.logging import get_correlation_id, get_logger, set_correlation_id
from shared.config.settings import get_settings

logger = get_logger(__name__)


def format_address(address: Optional[Dict[str, Any]]) -> str:
    """Formata o endereço seguindo o padrão: '{street}, {suite} - {city} CEP {zipcode}'."""
    if not address or not isinstance(address, dict):
        return "Endereço não informado"
    street = str(address.get("street", "")).strip()
    suite = str(address.get("suite", "")).strip()
    city = str(address.get("city", "")).strip()
    zipcode = str(address.get("zipcode", "")).strip()
    return f"{street}, {suite} - {city} CEP {zipcode}"


def map_photo_to_documento(photo: Dict[str, Any]) -> Dict[str, Any]:
    """Realiza o De-Para de um registro de foto (/photos) para documento jurídico."""
    return {
        "id": int(photo["id"]),
        "titulo": str(photo.get("title", "")).strip(),
        "url": str(photo.get("url", "")).strip(),
        "thumbnailUrl": str(photo.get("thumbnailUrl", "")).strip(),
    }


def map_album_to_acordo(album: Dict[str, Any], photos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Realiza o De-Para de um álbum (/albums) e suas fotos para acordo jurídico e documentos."""
    return {
        "id": int(album["id"]),
        "titulo": str(album.get("title", "")).strip(),
        "documentos": [map_photo_to_documento(p) for p in photos],
    }


def map_user_to_autor_payload(
    user: Dict[str, Any],
    albums_with_photos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Realiza o De-Para completo do usuário (/users) para o contrato canônico de Autor e Acordos."""
    company = user.get("company") if isinstance(user.get("company"), dict) else {}
    return {
        "autor": {
            "id": int(user["id"]),
            "nome": str(user.get("name", "")).strip(),
            "email": str(user.get("email", "")).strip(),
            "telefone": str(user.get("phone", "")).strip(),
            "endereco": format_address(user.get("address")),
            "empresa": {
                "nome": str(company.get("name", "")).strip(),
                "segmento": str(company.get("bs", "")).strip(),
            },
        },
        "acordos": albums_with_photos,
    }


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
        """Obtém ou cria a URL da fila SQS configurada."""
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
