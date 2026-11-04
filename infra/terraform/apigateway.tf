# =============================================================================
# Amazon API Gateway HTTP API (v2) e Rotas
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

  request_parameters = {
    "overwrite:path" = "$request.path"
  }
}

resource "aws_apigatewayv2_route" "proxy_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.api_proxy.id}"
}

locals {
  explicit_api_routes = toset([
    "GET /health",
    "GET /docs",
    "GET /openapi.json",
    "POST /api/v1/auth/token",
    "GET /api/v1/autores",
    "GET /api/v1/autores/{autor_id}/acordos",
    "GET /api/v1/usuarios",
    "GET /api/v1/usuarios/{autor_id}/acordos",
    "GET /api/v1/acordos",
    "GET /api/v1/acordos/{acordo_id}",
    "GET /api/v1/acordos/{acordo_id}/documentos",
    "GET /api/v1/documentos/{documento_id}",
    "GET /api/v1/estatisticas",
    "POST /api/v1/dlq/reprocessar",
  ])
}

resource "aws_apigatewayv2_route" "explicit_routes" {
  for_each  = local.explicit_api_routes
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.api_proxy.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}
