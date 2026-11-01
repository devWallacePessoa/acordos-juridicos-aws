"""Testes unitários do ConsumerService garantindo persistência transacional e idempotência (Upsert)."""

from collections.abc import Callable
import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.consumer.main import ConsumerService
from shared.models.entities import AcordoORM, AutorORM, DocumentoORM


def _build_sample_sqs_payload(nome_autor: str = "Leanne Graham") -> Dict[str, Any]:
    return {
        "autor": {
            "id": 1,
            "nome": nome_autor,
            "email": "Sincere@april.biz",
            "telefone": "1-770-736-8031",
            "endereco": "Kulas Light, Apt. 556 - Gwenborough CEP 92998-3874",
            "empresa": {
                "nome": "Romaguera-Crona",
                "segmento": "harness real-time e-markets",
            },
        },
        "acordos": [
            {
                "id": 10,
                "titulo": "quidem molestiae enim",
                "documentos": [
                    {
                        "id": 100,
                        "titulo": "accusamus beatae ad facilis",
                        "url": "https://via.placeholder.com/600/92c952",
                        "thumbnailUrl": "https://via.placeholder.com/150/92c952",
                    }
                ],
            }
        ],
    }


def test_consumer_process_payload_and_idempotent_upsert(
    db_session_factory: Callable[[], Session],
) -> None:
    """Garante que o reprocessamento da mesma mensagem atualiza os dados sem duplicar registros."""
    mock_sqs = MagicMock()
    consumer = ConsumerService(
        session_factory=db_session_factory,
        sqs_client=mock_sqs,
        queue_url="http://localhost:4566/000000000000/acordos-juridicos-queue",
    )

    payload_v1 = _build_sample_sqs_payload(nome_autor="Leanne Graham")
    autor_id = consumer.process_payload(payload_v1)
    assert autor_id == 1

    # Reprocessa com nome atualizado (teste de idempotência / upsert)
    payload_v2 = _build_sample_sqs_payload(nome_autor="Leanne Graham Atualizada")
    consumer.process_payload(payload_v2)

    with db_session_factory() as session:
        autores = list(session.execute(select(AutorORM)).scalars().all())
        acordos = list(session.execute(select(AcordoORM)).scalars().all())
        docs = list(session.execute(select(DocumentoORM)).scalars().all())

        assert len(autores) == 1
        assert autores[0].nome == "Leanne Graham Atualizada"
        assert len(acordos) == 1
        assert len(docs) == 1
        assert docs[0].thumbnail_url == "https://via.placeholder.com/150/92c952"


def test_consumer_poll_once_deletes_processed_message(
    db_session_factory: Callable[[], Session],
) -> None:
    """Verifica que o Consumer lê a mensagem do SQS, persiste no banco e chama delete_message."""
    mock_sqs = MagicMock()
    payload = _build_sample_sqs_payload()
    mock_sqs.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "msg-123",
                "ReceiptHandle": "rh-123",
                "Body": json.dumps(payload),
            }
        ]
    }

    consumer = ConsumerService(
        session_factory=db_session_factory,
        sqs_client=mock_sqs,
        queue_url="http://localhost:4566/000000000000/acordos-juridicos-queue",
    )
    processed = consumer.poll_once()

    assert processed == 1
    mock_sqs.delete_message.assert_called_once_with(
        QueueUrl="http://localhost:4566/000000000000/acordos-juridicos-queue",
        ReceiptHandle="rh-123",
    )


def test_consumer_invalid_payload_raises_value_error(
    db_session_factory: Callable[[], Session],
) -> None:
    """Verifica que payloads sem a chave obrigatória 'autor' disparam ValueError."""
    consumer = ConsumerService(
        session_factory=db_session_factory,
        sqs_client=MagicMock(),
        queue_url="http://localhost:4566/000000000000/acordos-juridicos-queue",
    )
    with pytest.raises(ValueError, match="autor"):
        consumer.process_payload({"invalido": True})


def test_consumer_poll_once_empty_and_error_handling(
    db_session_factory: Callable[[], Session],
) -> None:
    """Valida o comportamento quando a fila está vazia ou ocorre falha na mensagem."""
    mock_sqs = MagicMock()
    mock_sqs.receive_message.return_value = {"Messages": []}
    consumer = ConsumerService(
        session_factory=db_session_factory,
        sqs_client=mock_sqs,
        queue_url="http://localhost:4566/000000000000/acordos-juridicos-queue",
    )
    assert consumer.poll_once() == 0

    mock_sqs.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "bad-msg",
                "ReceiptHandle": "rh-bad",
                "Body": json.dumps({"invalido": True}),
            }
        ]
    }
    assert consumer.poll_once() == 0
    mock_sqs.delete_message.assert_not_called()


def test_consumer_lambda_handler_success_and_partial_batch_failure(
    db_session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valida o lambda_handler do Consumer para eventos SQS com sucesso e falha parcial."""
    from services.consumer import main as consumer_main

    monkeypatch.setattr(consumer_main, "init_db", lambda: None)
    monkeypatch.setattr(consumer_main, "SessionLocal", db_session_factory)

    valid_body = json.dumps(_build_sample_sqs_payload())
    invalid_body = json.dumps({"invalido": True})
    event = {
        "Records": [
            {"messageId": "msg-ok", "body": valid_body},
            {"messageId": "msg-fail", "body": invalid_body},
        ]
    }
    result = consumer_main.lambda_handler(event)
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-fail"}]}

