output "sqs_queue_url" {
  description = "URL da fila principal AWS SQS de Acordos Jurídicos"
  value       = aws_sqs_queue.acordos_queue.id
}

output "sqs_dlq_url" {
  description = "URL da Dead Letter Queue (DLQ) AWS SQS"
  value       = aws_sqs_queue.acordos_dlq.id
}

output "ecr_repository_url" {
  description = "URL do repositório Amazon ECR da aplicação"
  value       = aws_ecr_repository.app_repo.repository_url
}

output "rds_endpoint" {
  description = "Endpoint de conexão do banco de dados Amazon RDS PostgreSQL"
  value       = aws_db_instance.postgres.endpoint
}

output "ecs_cluster_name" {
  description = "Nome do Cluster Amazon ECS Fargate"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Nome do Service ECS Fargate da API"
  value       = aws_ecs_service.api_service.name
}

output "api_gateway_url" {
  description = "Invoke URL publica do Amazon API Gateway HTTP API"
  value       = aws_apigatewayv2_stage.default.invoke_url
}
