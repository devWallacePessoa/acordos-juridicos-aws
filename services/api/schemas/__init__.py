"""Schemas Pydantic para contratos de entrada e saída da API."""

from services.api.schemas.acordo_schema import (
    AcordoDetalheResponse,
    AcordoSchema,
    AutorComAcordosSchema,
    AutorResumoSchema,
    AutorSchema,
    DocumentoSchema,
    EmpresaSchema,
    EstatisticaGeralResponse,
    HealthCheckResponse,
    PaginatedResponse,
    TokenRequest,
    TokenResponse,
)

__all__ = [
    "EmpresaSchema",
    "DocumentoSchema",
    "AcordoSchema",
    "AutorSchema",
    "AutorResumoSchema",
    "AutorComAcordosSchema",
    "AcordoDetalheResponse",
    "PaginatedResponse",
    "EstatisticaGeralResponse",
    "TokenRequest",
    "TokenResponse",
    "HealthCheckResponse",
]
