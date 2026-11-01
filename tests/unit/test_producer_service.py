"""Testes unitários para o serviço Produtor, cliente HTTP e funções de De-Para."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import httpx

from services.producer.client import ExternalAPIClient
from services.producer.main import (
    ProducerService,
    format_address,
    map_album_to_acordo,
    map_photo_to_documento,
    map_user_to_autor_payload,
)


def test_format_address_de_para(sample_raw_api_data: Dict[str, Any]) -> None:
    """Valida a formatação exata do endereço: '{street}, {suite} - {city} CEP {zipcode}'."""
    address = sample_raw_api_data["user"]["address"]
    formatted = format_address(address)
    assert formatted == "Kulas Light, Apt. 556 - Gwenborough CEP 92998-3874"
    assert format_address(None) == "Endereço não informado"


def test_map_user_album_photo_de_para(sample_raw_api_data: Dict[str, Any]) -> None:
    """Valida o De-Para completo entre os dados da API pública e o contrato de Acordos."""
    user = sample_raw_api_data["user"]
    album = sample_raw_api_data["album"]
    photos = sample_raw_api_data["photos"]

    doc = map_photo_to_documento(photos[0])
    assert doc == {
        "id": 100,
        "titulo": "accusamus beatae ad facilis cum similique qui sunt",
        "url": "https://via.placeholder.com/600/92c952",
        "thumbnailUrl": "https://via.placeholder.com/150/92c952",
    }

    acordo = map_album_to_acordo(album, photos)
    assert acordo["id"] == 10
    assert acordo["titulo"] == "quidem molestiae enim"
    assert len(acordo["documentos"]) == 2

    payload = map_user_to_autor_payload(user, [acordo])
    assert payload["autor"]["id"] == 1
    assert payload["autor"]["nome"] == "Leanne Graham"
    assert payload["autor"]["email"] == "Sincere@april.biz"
    assert payload["autor"]["telefone"] == "1-770-736-8031 x56442"
    assert payload["autor"]["endereco"] == "Kulas Light, Apt. 556 - Gwenborough CEP 92998-3874"
    assert payload["autor"]["empresa"] == {
        "nome": "Romaguera-Crona",
        "segmento": "harness real-time e-markets",
    }
    assert len(payload["acordos"]) == 1


def test_external_api_client_all_six_endpoints(sample_raw_api_data: Dict[str, Any]) -> None:
    """Testa os 6 endpoints obrigatórios do cliente HTTP usando MockTransport do HTTPX."""
    user = sample_raw_api_data["user"]
    album = sample_raw_api_data["album"]
    photos = sample_raw_api_data["photos"]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/users":
            return httpx.Response(200, json=[user])
        if path == "/users/1":
            return httpx.Response(200, json=user)
        if path == "/users/1/albums":
            return httpx.Response(200, json=[album])
        if path == "/albums/10":
            return httpx.Response(200, json=album)
        if path == "/albums/10/photos":
            return httpx.Response(200, json=photos)
        if path == "/photos/100":
            return httpx.Response(200, json=photos[0])
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(handler)
    mock_http = httpx.Client(base_url="https://jsonplaceholder.typicode.com", transport=transport)

    with ExternalAPIClient(http_client=mock_http) as client:
        assert len(client.get_users()) == 1
        assert client.get_user_by_id(1)["name"] == "Leanne Graham"
        assert len(client.get_user_albums(1)) == 1
        assert client.get_album_by_id(10)["title"] == "quidem molestiae enim"
        assert len(client.get_album_photos(10)) == 2
        assert client.get_photo_by_id(100)["id"] == 100


def test_producer_service_run_publishes_to_sqs(sample_raw_api_data: Dict[str, Any]) -> None:
    """Verifica se o ProducerService constrói a hierarquia e envia a mensagem JSON para o SQS."""
    mock_api_client = MagicMock(spec=ExternalAPIClient)
    mock_api_client.get_users.return_value = [sample_raw_api_data["user"]]
    mock_api_client.get_user_by_id.return_value = sample_raw_api_data["user"]
    mock_api_client.get_user_albums.return_value = [sample_raw_api_data["album"]]
    mock_api_client.get_album_photos.return_value = sample_raw_api_data["photos"]

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-001"}

    producer = ProducerService(
        api_client=mock_api_client,
        sqs_client=mock_sqs,
        queue_url="http://localhost:4566/000000000000/acordos-juridicos-queue",
    )
    published_ids = producer.run(max_users=1)

    assert published_ids == ["msg-001"]
    mock_sqs.send_message.assert_called_once()
    call_kwargs = mock_sqs.send_message.call_args.kwargs
    sent_body = json.loads(call_kwargs["MessageBody"])
    assert sent_body["autor"]["id"] == 1
    assert sent_body["acordos"][0]["id"] == 10
    assert len(sent_body["acordos"][0]["documentos"]) == 2


def test_producer_lambda_handler(
    sample_raw_api_data: Dict[str, Any],
    monkeypatch: Any,
) -> None:
    """Valida a execução do lambda_handler do Producer."""
    from services.producer import main as producer_main

    mock_service = MagicMock()
    mock_service.run.return_value = ["msg-lambda-1"]
    monkeypatch.setattr(producer_main, "ProducerService", lambda api_client=None: mock_service)

    response = producer_main.lambda_handler({"max_users": 1})
    assert response == {
        "statusCode": 200,
        "publishedCount": 1,
        "messageIds": ["msg-lambda-1"],
    }

