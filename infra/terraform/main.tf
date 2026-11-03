terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# =============================================================================
# 1. Mensageria Assíncrona: AWS SQS + Dead Letter Queue (DLQ)
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

# =============================================================================
# 2. Container Registry (AWS ECR) para Producer, Consumer e API
# =============================================================================

resource "aws_ecr_repository" "app_repo" {
  name                 = "${var.project_name}-${var.environment}-repo"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# =============================================================================
# 3. Rede Básica e Banco de Dados Relacional (Amazon RDS PostgreSQL 16)
# =============================================================================

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "ecs_sg" {
  name        = "${var.project_name}-${var.environment}-ecs-sg"
  description = "Permite entrada HTTP na porta 8000 para a API no ECS Fargate"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "FastAPI HTTP Port 8000"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds_sg" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "Permite trafego PostgreSQL na porta 5432 dentro da VPC"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL access from VPC and ECS SG"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = [data.aws_vpc.default.cidr_block]
    security_groups = [aws_security_group.ecs_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "postgres" {
  identifier             = "${var.project_name}-${var.environment}-db"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  max_allocated_storage  = 50
  storage_type           = "gp3"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  storage_encrypted      = true
}

# =============================================================================
# 4. IAM Roles e CloudWatch Log Groups
# =============================================================================

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/ecs/${var.project_name}-${var.environment}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "consumer_logs" {
  name              = "/aws/ecs/${var.project_name}-${var.environment}-consumer"
  retention_in_days = 14
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-${var.environment}-ecs-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_exec_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-${var.environment}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "sqs_access_policy" {
  name = "${var.project_name}-${var.environment}-sqs-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.acordos_queue.arn,
          aws_sqs_queue.acordos_dlq.arn
        ]
      }
    ]
  })
}

# =============================================================================
# 5. Cluster Amazon ECS Fargate (API & Consumer Worker)
# =============================================================================

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "api_task" {
  family                   = "${var.project_name}-${var.environment}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.app_repo.repository_url}:latest"
      essential = true
      command   = ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "DB_HOST", value = aws_db_instance.postgres.address },
        { name = "DB_PORT", value = tostring(aws_db_instance.postgres.port) },
        { name = "DB_NAME", value = var.db_name },
        { name = "DB_USER", value = var.db_username },
        { name = "DB_PASSWORD", value = var.db_password },
        { name = "JWT_SECRET_KEY", value = var.jwt_secret_key },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "DD_API_KEY", value = var.dd_api_key },
        { name = "DD_SITE", value = var.dd_site },
        { name = "DD_ENV", value = var.environment },
        { name = "DD_SERVICE", value = "${var.project_name}-api" },
        { name = "SQS_QUEUE_NAME", value = aws_sqs_queue.acordos_queue.name },
        { name = "SQS_DLQ_NAME", value = aws_sqs_queue.acordos_dlq.name }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api_logs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api_service" {
  name            = "${var.project_name}-${var.environment}-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = true
  }
}

# =============================================================================
# 6. Amazon API Gateway HTTP API (v2)
# =============================================================================

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-${var.environment}-http-api"
  protocol_type = "HTTP"
  description   = "API Gateway HTTP para a API de Consulta de Acordos Juridicos"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["*"]
  }
}

resource "aws_apigatewayv2_integration" "api_proxy" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = var.api_backend_url
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_route" "proxy_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.api_proxy.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}
