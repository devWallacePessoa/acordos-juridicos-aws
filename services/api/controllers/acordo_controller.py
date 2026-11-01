"""Definição dos endpoints RESTful para autenticação e consulta de Autores, Acordos e Documentos."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.api.auth import (
    authenticate_admin_credentials,
    create_access_token,
    require_auth,
)
from services.api.exceptions import AuthenticationError
from services.api.repositories.acordo_repository import AcordoRepository
from services.api.schemas.acordo_schema import (
    AcordoDetalheResponse,
    AcordoSchema,
    AutorComAcordosSchema,
    AutorResumoSchema,
    DocumentoSchema,
    EstatisticaGeralResponse,
    PaginatedResponse,
    TokenRequest,
    TokenResponse,
)
from services.api.services.acordo_service import AcordoService
from shared.config.database import get_db
from shared.config.settings import Settings, get_settings

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])
v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Acordos Jurídicos"],
    dependencies=[Depends(require_auth)],
)


def get_acordo_service(db: Session = Depends(get_db)) -> AcordoService:
    """Injeta o serviço de acordos com sua respectiva sessão de repositório."""
    repository = AcordoRepository(db)
    return AcordoService(repository)


@auth_router.post(
    "/token",
    response_model=TokenResponse,
    summary="Gerar Token JWT de Acesso",
    description="Autentica credenciais administrativas e emite um token Bearer JWT válido.",
)
def login_for_access_token(
    credentials: TokenRequest,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Emite um token JWT quando username e password são válidos."""
    if not authenticate_admin_credentials(
        credentials.username, credentials.password, settings=settings
    ):
        raise AuthenticationError("Usuário ou senha inválidos.")

    token = create_access_token(subject=credentials.username, settings=settings)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.JWT_EXPIRE_MINUTES,
    )


@v1_router.get(
    "/autores",
    response_model=PaginatedResponse[AutorResumoSchema],
    summary="Listar Autores de Ações Judiciais",
    description="Retorna lista paginada de autores cadastrados com filtros por nome e segmento empresarial.",
)
def listar_autores(
    page: int = Query(1, ge=1, description="Número da página"),
    size: int = Query(10, ge=1, le=100, description="Itens por página"),
    nome: Optional[str] = Query(None, description="Filtro parcial por nome do autor"),
    segmento: Optional[str] = Query(None, description="Filtro parcial por segmento empresarial"),
    service: AcordoService = Depends(get_acordo_service),
) -> PaginatedResponse[AutorResumoSchema]:
    return service.listar_autores(page=page, size=size, nome=nome, segmento=segmento)


@v1_router.get(
    "/autores/{autor_id}/acordos",
    response_model=AutorComAcordosSchema,
    summary="Consultar Autor e Hierarquia Completa de Acordos e Documentos",
    description=(
        "Retorna os dados consolidados do Autor (1) -> (N) Acordos (1) -> (N) Documentos "
        "seguindo o De-Para oficial do Case Técnico."
    ),
)
def obter_acordos_do_autor(
    autor_id: int,
    incluir_documentos: bool = Query(
        True, description="Define se a lista de documentos de cada acordo deve ser incluída"
    ),
    service: AcordoService = Depends(get_acordo_service),
) -> AutorComAcordosSchema:
    return service.obter_acordos_por_autor(
        autor_id=autor_id, incluir_documentos=incluir_documentos
    )


@v1_router.get(
    "/acordos",
    response_model=PaginatedResponse[AcordoSchema],
    summary="Listar Acordos Jurídicos",
    description="Lista acordos paginados com filtro opcional por ID do autor ou título do acordo.",
)
def listar_acordos(
    page: int = Query(1, ge=1, description="Número da página"),
    size: int = Query(10, ge=1, le=100, description="Itens por página"),
    autor_id: Optional[int] = Query(None, description="Filtrar acordos por ID do autor"),
    titulo: Optional[str] = Query(None, description="Busca textual no título do acordo"),
    incluir_documentos: bool = Query(True, description="Incluir documentos de cada acordo"),
    service: AcordoService = Depends(get_acordo_service),
) -> PaginatedResponse[AcordoSchema]:
    return service.listar_acordos(
        page=page,
        size=size,
        autor_id=autor_id,
        titulo=titulo,
        incluir_documentos=incluir_documentos,
    )


@v1_router.get(
    "/acordos/{acordo_id}",
    response_model=AcordoDetalheResponse,
    summary="Consultar Detalhes de um Acordo Específico",
    description="Retorna os dados do acordo, todos os seus documentos e os dados do autor vinculado.",
)
def obter_acordo_por_id(
    acordo_id: int,
    service: AcordoService = Depends(get_acordo_service),
) -> AcordoDetalheResponse:
    return service.obter_acordo_por_id(acordo_id=acordo_id)


@v1_router.get(
    "/acordos/{acordo_id}/documentos",
    response_model=List[DocumentoSchema],
    summary="Listar Documentos de um Acordo",
    description="Retorna exclusivamente os documentos comprobatórios vinculados a um acordo específico.",
)
def listar_documentos_do_acordo(
    acordo_id: int,
    service: AcordoService = Depends(get_acordo_service),
) -> List[DocumentoSchema]:
    detalhe = service.obter_acordo_por_id(acordo_id=acordo_id)
    return detalhe.acordo.documentos


@v1_router.get(
    "/documentos/{documento_id}",
    response_model=DocumentoSchema,
    summary="Consultar um Documento Específico",
    description="Retorna os metadados e URLs de um documento específico pelo seu identificador.",
)
def obter_documento_por_id(
    documento_id: int,
    service: AcordoService = Depends(get_acordo_service),
) -> DocumentoSchema:
    return service.obter_documento_por_id(documento_id=documento_id)


@v1_router.get(
    "/estatisticas",
    response_model=EstatisticaGeralResponse,
    summary="Consultar Estatísticas Gerais de Acordos",
    description="Retorna indicadores consolidados de autores, acordos e documentos na base.",
)
def obter_estatisticas(
    service: AcordoService = Depends(get_acordo_service),
) -> EstatisticaGeralResponse:
    return service.obter_estatisticas()
