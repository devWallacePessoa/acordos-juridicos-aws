"""Script auxiliar para postar mensagem de teste na DLQ da AWS.
Uso:
    python scripts/post_dlq_aws.py
"""
import json
import os
import boto3

# Remove variáveis do LocalStack e credenciais fictícias do .env para usar a cadeia padrão da AWS
os.environ.pop("AWS_ENDPOINT_URL", None)

payload = {
    "correlation_id": "demo-dlq-reprocessamento-aws-001",
    "autor": {
        "id": 99,
        "nome": "Dr. Roberto Almeida (Teste DLQ AWS)",
        "email": "roberto.almeida@juridico.com.br",
        "telefone": "(11) 98888-7777",
        "endereco": "Av. Paulista, 1000, Apt. 101 - São Paulo CEP 01310-100",
        "empresa": {
            "nome": "Almeida & Associados Advocacia",
            "segmento": "Direito Empresarial e Societário",
        },
    },
    "acordos": [
        {
            "id": 9901,
            "titulo": "Acordo Extrajudicial de Confidencialidade e Quitação",
            "documentos": [
                {
                    "id": 99001,
                    "titulo": "Termo de Quitação Assinado Digitalmente",
                    "url": "https://via.placeholder.com/600/92c952",
                    "thumbnailUrl": "https://via.placeholder.com/150/92c952",
                },
                {
                    "id": 99002,
                    "titulo": "Comprovante de Transferência Bancária",
                    "url": "https://via.placeholder.com/600/771796",
                    "thumbnailUrl": "https://via.placeholder.com/150/771796",
                },
            ],
        }
    ],
}

region = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
queue_name = "acordos-juridicos-prod-dlq"

sqs = boto3.client("sqs", region_name=region)

try:
    dlq_url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    resp = sqs.send_message(
        QueueUrl=dlq_url,
        MessageBody=json.dumps(payload),
        MessageAttributes={
            "CorrelationId": {
                "DataType": "String",
                "StringValue": payload["correlation_id"],
            }
        },
    )
    print("\n[OK] Sucesso! Mensagem postada na DLQ da AWS!")
    print(f"Queue URL:      {dlq_url}")
    print(f"Message ID:     {resp['MessageId']}")
    print(f"Correlation ID: {payload['correlation_id']}\n")
except Exception as e:
    print(f"\n[ERRO] Falha ao postar na DLQ: {e}\n")
