"""Testes da fábrica de clientes AWS: LocalStack (local) vs. IAM Role (ECS Fargate)."""

from unittest.mock import patch

from shared.config.aws_clients import build_sqs_client
from shared.config.settings import Settings


def test_build_sqs_client_localstack_usa_endpoint_e_credenciais_de_teste() -> None:
    settings = Settings(
        AWS_ENDPOINT_URL="http://localstack:4566",
        AWS_REGION="us-east-1",
        AWS_ACCESS_KEY_ID="test",
        AWS_SECRET_ACCESS_KEY="test",
    )
    with patch("shared.config.aws_clients.boto3.client") as mock_client:
        build_sqs_client(settings)
    kwargs = mock_client.call_args.kwargs
    assert kwargs["endpoint_url"] == "http://localstack:4566"
    assert kwargs["aws_access_key_id"] == "test"


def test_build_sqs_client_aws_real_usa_iam_role_sem_endpoint_nem_chaves() -> None:
    settings = Settings(AWS_ENDPOINT_URL="", AWS_REGION="us-east-2")
    assert settings.AWS_ENDPOINT_URL is None
    with patch("shared.config.aws_clients.boto3.client") as mock_client:
        build_sqs_client(settings)
    mock_client.assert_called_once_with("sqs", region_name="us-east-2")
