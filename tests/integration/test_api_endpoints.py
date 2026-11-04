"""Testes de integração dos endpoints da API FastAPI (Autenticação, Consultas e Erros)."""

from typing import Dict

from fastapi.testclient import TestClient

from shared.config.settings import get_settings


def test_health_check_endpoint(api_client: TestClient) -> None:
    """Valida o endpoint público /health."""
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


def test_auth_token_generation_and_invalid_credentials(api_client: TestClient) -> None:
    """Valida a emissão de token JWT e rejeição de credenciais inválidas."""
    settings = get_settings()
    ok_resp = api_client.post(
        "/api/v1/auth/token",
        json={"username": settings.API_ADMIN_USER, "password": settings.API_ADMIN_PASSWORD},
    )
    assert ok_resp.status_code == 200
    assert "access_token" in ok_resp.json()

    bad_resp = api_client.post(
        "/api/v1/auth/token",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["erro"] == "UNAUTHORIZED"


def test_protected_endpoints_reject_unauthenticated_requests(api_client: TestClient) -> None:
    """Garante que chamadas sem token JWT ou X-API-Key recebem HTTP 401."""
    response = api_client.get("/api/v1/autores")
    assert response.status_code == 401


def test_listar_autores_with_filters_and_api_key(api_client: TestClient) -> None:
    """Valida a listagem paginada de autores autenticando via X-API-Key."""
    settings = get_settings()
    response = api_client.get(
        "/api/v1/autores?nome=Leanne",
        headers={"X-API-Key": settings.API_STATIC_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nome"] == "Leanne Graham"
    assert data["items"][0]["total_acordos"] == 2


def test_consultar_acordos_do_autor_hierarquia_completa(
    api_client: TestClient,
    auth_headers: Dict[str, str],
) -> None:
    """Valida os endpoints GET /api/v1/autores/{id}/acordos e GET /api/v1/usuarios/{id}/acordos e seu contrato JSON."""
    for path in ("/api/v1/autores/1/acordos", "/api/v1/usuarios/1/acordos"):
        response = api_client.get(
            path,
            headers={**auth_headers, "X-Correlation-ID": "corr-test-123"},
        )
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == "corr-test-123"
        payload = response.json()

        assert payload["autor"]["id"] == 1
        assert payload["autor"]["nome"] == "Leanne Graham"
        assert payload["autor"]["endereco"] == "Kulas Light, Apt. 556 - Gwenborough CEP 92998-3874"
        assert payload["autor"]["empresa"] == {
            "nome": "Romaguera-Crona",
            "segmento": "harness real-time e-markets",
        }
        assert payload["resumo"] == {
            "quantidadeAcordos": 2,
            "quantidadeDocumentos": 2,
        }
        assert len(payload["acordos"]) == 2
        assert payload["acordos"][0]["id"] == 10
        assert payload["acordos"][0]["titulo"] == "quidem molestiae enim"
        assert payload["acordos"][0]["quantidadeDocumentos"] == 2
        assert len(payload["acordos"][0]["documentos"]) == 2
        assert payload["acordos"][0]["documentos"][0]["thumbnailUrl"] == "https://via.placeholder.com/150/92c952"

    # Testa retorno HTTP 400 para id inválido (<= 0) conforme especificação do Case
    bad_id_resp = api_client.get("/api/v1/usuarios/0/acordos", headers=auth_headers)
    assert bad_id_resp.status_code == 400
    assert bad_id_resp.json()["erro"] == "INVALID_ID"


def test_consultar_acordos_detalhe_documentos_e_estatisticas(
    api_client: TestClient,
    auth_headers: Dict[str, str],
) -> None:
    """Valida os endpoints de listagem de acordos, detalhes do acordo, documentos e estatísticas."""
    list_resp = api_client.get("/api/v1/acordos?autor_id=1", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 2

    detalhe_resp = api_client.get("/api/v1/acordos/10", headers=auth_headers)
    assert detalhe_resp.status_code == 200
    assert detalhe_resp.json()["acordo"]["id"] == 10
    assert detalhe_resp.json()["autor"]["id"] == 1

    docs_resp = api_client.get("/api/v1/acordos/10/documentos", headers=auth_headers)
    assert docs_resp.status_code == 200
    assert len(docs_resp.json()) == 2

    doc_single = api_client.get("/api/v1/documentos/100", headers=auth_headers)
    assert doc_single.status_code == 200
    assert doc_single.json()["id"] == 100

    stats_resp = api_client.get("/api/v1/estatisticas", headers=auth_headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["total_autores"] == 2

    not_found_resp = api_client.get("/api/v1/acordos/99999", headers=auth_headers)
    assert not_found_resp.status_code == 404
    assert not_found_resp.json()["erro"] == "RESOURCE_NOT_FOUND"

    # Testa filtros de segmento, título, documento inexistente, token inválido e erro de validação (422)
    seg_resp = api_client.get("/api/v1/autores?segmento=e-markets", headers=auth_headers)
    assert seg_resp.status_code == 200
    assert seg_resp.json()["total"] == 1

    titulo_resp = api_client.get("/api/v1/acordos?titulo=molestiae", headers=auth_headers)
    assert titulo_resp.status_code == 200
    assert titulo_resp.json()["total"] == 1

    doc_404 = api_client.get("/api/v1/documentos/99999", headers=auth_headers)
    assert doc_404.status_code == 404

    invalid_jwt = api_client.get(
        "/api/v1/autores",
        headers={"Authorization": "Bearer token-invalido"},
    )
    assert invalid_jwt.status_code == 401

    validation_422 = api_client.get("/api/v1/autores?page=0", headers=auth_headers)
    assert validation_422.status_code == 422
    assert validation_422.json()["erro"] == "VALIDATION_ERROR"


def test_datadog_telemetry_collection_and_post_mock(monkeypatch: object) -> None:
    """Valida a coleta de métricas de RDS e SQS/DLQ do módulo datadog_telemetry."""
    from unittest.mock import MagicMock
    from services.api import datadog_telemetry

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = 1048576
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_sqs = MagicMock()
    mock_sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs.us-east-2.amazonaws.com/123/q"}
    mock_sqs.get_queue_attributes.return_value = {
        "Attributes": {
            "ApproximateNumberOfMessages": "5",
            "ApproximateNumberOfMessagesNotVisible": "1",
            "ApproximateNumberOfMessagesDelayed": "0",
        }
    }
    monkeypatch.setattr(datadog_telemetry.boto3, "client", lambda *a, **kw: mock_sqs)

    series = datadog_telemetry._collect_infra_metrics_sync(mock_engine)
    metric_names = {item["metric"] for item in series}
    assert "acordos.rds.db_size_mb" in metric_names
    assert "acordos.rds.table_size_bytes" in metric_names
    assert "acordos.sqs.messages_visible" in metric_names
    assert "acordos.sqs.messages_in_flight" in metric_names


def test_dlq_reprocessar_endpoint(
    api_client: TestClient,
    auth_headers: Dict[str, str],
    monkeypatch: object,
) -> None:
    """Valida o endpoint POST /api/v1/dlq/reprocessar para reprocessamento sob demanda da DLQ."""
    from services.api.controllers import acordo_controller

    class DummyConsumer:
        def __init__(self, **kwargs: object) -> None:
            pass

        def reprocess_dlq(self, max_messages: int = 10) -> Dict[str, int]:
            return {"reprocessed_count": 2, "failed_count": 0}

    monkeypatch.setattr(acordo_controller, "ConsumerService", DummyConsumer)
    resp = api_client.post(
        "/api/v1/dlq/reprocessar?max_messages=5",
        headers={**auth_headers, "X-Correlation-ID": "dlq-corr-999"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reprocessed_count"] == 2
    assert body["failed_count"] == 0
    assert body["correlation_id"] == "dlq-corr-999"


