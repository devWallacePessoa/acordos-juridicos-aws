variable "aws_region" {
  description = "Região AWS para provisionamento dos recursos"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Prefixo identificador do projeto de Acordos Jurídicos"
  type        = string
  default     = "acordos-juridicos"
}

variable "environment" {
  description = "Ambiente de deploy (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "db_name" {
  description = "Nome do banco de dados PostgreSQL no RDS"
  type        = string
  default     = "acordos_db"
}

variable "db_username" {
  description = "Usuário administrador do banco de dados PostgreSQL"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "Senha do banco de dados PostgreSQL (injetada via TF_VAR_db_password)"
  type        = string
  sensitive   = true
  default     = "ChangeMeStrongPassword2026!"
}

variable "jwt_secret_key" {
  description = "Chave secreta para assinatura de tokens JWT na API"
  type        = string
  sensitive   = true
  default     = "super-secret-jwt-key-acordos-juridicos-2026"
}

variable "api_backend_url" {
  description = "URL HTTP publica do container ECS Fargate na porta 8000 para integracao com o API Gateway"
  type        = string
  default     = "http://127.0.0.1:8000/{proxy}"
}
