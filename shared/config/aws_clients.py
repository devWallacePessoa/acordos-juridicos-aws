"""Fábrica de clientes AWS (boto3) que funciona igual no LocalStack (local) e na AWS (ECS Fargate)."""

from typing import Any

import boto3

from shared.config.settings import Settings


def build_sqs_client(settings: Settings) -> Any:
    """Cria o cliente SQS.

    - Local (LocalStack): `AWS_ENDPOINT_URL` preenchido -> usa endpoint e credenciais de teste.
    - AWS (ECS Fargate): `AWS_ENDPOINT_URL` vazio -> usa a IAM Role da Task (cadeia padrão do boto3).
    """
    if settings.AWS_ENDPOINT_URL:
        return boto3.client(
            "sqs",
            region_name=settings.AWS_REGION,
            endpoint_url=settings.AWS_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    return boto3.client("sqs", region_name=settings.AWS_REGION)
