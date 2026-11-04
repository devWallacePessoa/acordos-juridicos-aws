# =============================================================================
# Mensageria Assíncrona: AWS SQS + Dead Letter Queue (DLQ)
# =============================================================================

resource "aws_sqs_queue" "acordos_dlq" {
  name                      = "${var.project_name}-${var.environment}-dlq"
  message_retention_seconds = 1209600 # 14 dias
}

resource "aws_sqs_queue" "acordos_queue" {
  name                       = "${var.project_name}-${var.environment}-queue"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600 # 4 dias
  receive_wait_time_seconds  = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.acordos_dlq.arn
    maxReceiveCount     = 3
  })
}
