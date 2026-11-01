"""Exceções de domínio e handlers globais RFC 7807 / JSON estruturado para a API."""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shared.config.logging import get_logger

logger = get_logger(__name__)


class DomainError(Exception):
    """Exceção base de regras de negócio e domínio."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str = "DOMAIN_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class ResourceNotFoundError(DomainError):
    """Exceção lançada quando um Autor, Acordo ou Documento não é encontrado."""

    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            message=f"{resource} com identificador '{identifier}' não foi encontrado.",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


class AuthenticationError(DomainError):
    """Exceção lançada em falhas de autenticação JWT ou API Key."""

    def __init__(self, message: str = "Credenciais de autenticação inválidas ou ausentes.") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os tratadores globais de exceção na instância FastAPI."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        logger.warning(
            "Erro de domínio capturado na API",
            extra={
                "extra_data": {
                    "path": request.url.path,
                    "error_code": exc.error_code,
                    "status_code": exc.status_code,
                    "message": exc.message,
                }
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "erro": exc.error_code,
                "mensagem": exc.message,
                "detalhes": exc.details,
                "caminho": str(request.url.path),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "erro": "VALIDATION_ERROR",
                "mensagem": "Parâmetros de requisição inválidos.",
                "detalhes": exc.errors(),
                "caminho": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Erro interno inesperado na API",
            exc_info=True,
            extra={"extra_data": {"path": request.url.path, "error": str(exc)}},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "erro": "INTERNAL_SERVER_ERROR",
                "mensagem": "Ocorreu um erro interno inesperado ao processar a solicitação.",
                "detalhes": {},
                "caminho": str(request.url.path),
            },
        )
