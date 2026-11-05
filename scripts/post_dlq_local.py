"""Script auxiliar para postar mensagem de teste na DLQ Local (LocalStack).
Uso:
    python scripts/post_dlq_local.py
"""
import json
import os
import boto3

payload = {
    "correlation_id": "demo-dlq-reprocessamento-local-001",
    "autor": {
        "id": 99,
        "nome": "Dr. Roberto Almeida (Teste DLQ Local)",
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

region = os.getenv("AWS_REGION", "us-east-1")
endpoint = "http://localhost:4566"
queue_name = os.getenv("SQS_DLQ_NAME", "acordos-juridicos-dlq")

sqs = boto3.client(
    "sqs",
    region_name=region,
    endpoint_url=endpoint,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

try:
    try:
        dlq_url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    except sqs.exceptions.QueueDoesNotExist:
        # Cria a DLQ caso o container do LocalStack tenha sido reiniciado
        print(f"[*] Fila '{queue_name}' nao encontrada no LocalStack. Criando automaticamente...")
        resp_create = sqs.create_queue(QueueName=queue_name)
        dlq_url = resp_create["QueueUrl"]
    except Exception as ex:
        if "NonExistentQueue" in str(ex):
            print(f"[*] Fila '{queue_name}' nao encontrada no LocalStack. Criando automaticamente...")
            resp_create = sqs.create_queue(QueueName=queue_name)
            dlq_url = resp_create["QueueUrl"]
        else:
            raise

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
    print("\n[OK] Sucesso! Mensagem postada na DLQ Local!")
    print(f"Queue URL:      {dlq_url}")
    print(f"Message ID:     {resp['MessageId']}")
    print(f"Correlation ID: {payload['correlation_id']}\n")
except Exception as e:
    print(f"\n[ERRO] Falha ao postar na DLQ: {e}\n")
