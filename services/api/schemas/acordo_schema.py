"""Definição dos contratos de dados Pydantic v2 com o De-Para obrigatório de Acordos."""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class EmpresaSchema(BaseModel):
    """Dados empresariais do autor da ação judicial."""

    model_config = ConfigDict(from_attributes=True)

    nome: str = Field(..., description="Razão social ou nome da empresa do autor", examples=["Romaguera-Crona"])
    segmento: str = Field(
        ...,
        description="Segmento de atuação empresarial (mapeado de company.bs)",
        examples=["harness real-time e-markets"],
    )


class DocumentoSchema(BaseModel):
    """Documento comprobatório pertencente a um acordo jurídico."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., description="Identificador único do documento", examples=[1])
    titulo: str = Field(..., description="Título descritivo do documento", examples=["accusamus beatae ad facilis"])
    url: str = Field(..., description="URL completa do documento", examples=["https://via.placeholder.com/600/92c952"])
    thumbnailUrl: str = Field(
        ...,
        alias="thumbnailUrl",
        description="URL da miniatura do documento",
        examples=["https://via.placeholder.com/150/92c952"],
    )


class AcordoSchema(BaseModel):
    """Acordo jurídico firmado no processo do autor contendo seus documentos."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único do acordo", examples=[1])
    titulo: str = Field(..., description="Título do acordo jurídico", examples=["quidem molestiae enim"])
    quantidadeDocumentos: int = Field(
        0,
        description="Quantidade total de documentos comprobatórios vinculados ao acordo",
        examples=[50],
    )
    documentos: List[DocumentoSchema] = Field(
        default_factory=list,
        description="Lista de documentos comprobatórios do acordo",
    )


class ResumoAcordosSchema(BaseModel):
    """Resumo consolidado de quantidades de acordos e documentos do autor."""

    quantidadeAcordos: int = Field(
        0,
        description="Quantidade total de acordos do autor",
        examples=[10],
    )
    quantidadeDocumentos: int = Field(
        0,
        description="Quantidade total de documentos somando todos os acordos do autor",
        examples=[500],
    )


class AutorSchema(BaseModel):
    """Dados cadastrais completos do autor da ação judicial."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único do autor", examples=[1])
    nome: str = Field(..., description="Nome completo do autor", examples=["Leanne Graham"])
    email: str = Field(..., description="E-mail de contato do autor", examples=["Sincere@april.biz"])
    telefone: str = Field(..., description="Telefone de contato do autor", examples=["1-770-736-8031 x56442"])
    endereco: str = Field(
        ...,
        description="Endereço formatado: '{street}, {suite} - {city} CEP {zipcode}'",
        examples=["Kulas Light, Apt. 556 - Gwenborough CEP 92998-3874"],
    )
    empresa: EmpresaSchema = Field(..., description="Empresa vinculada ao autor")


class AutorResumoSchema(AutorSchema):
    """Dados do autor acompanhados da contagem de acordos para listagens."""

    total_acordos: int = Field(0, description="Quantidade de acordos vinculados ao autor")


class AutorComAcordosSchema(BaseModel):
    """Estrutura hierárquica completa: Autor (1) -> Resumo -> (N) Acordos (1) -> (N) Documentos."""

    model_config = ConfigDict(from_attributes=True)

    autor: AutorSchema = Field(..., description="Dados do autor da ação judicial")
    resumo: ResumoAcordosSchema = Field(
        default_factory=ResumoAcordosSchema,
        description="Resumo quantitativo de acordos e documentos do autor",
    )
    acordos: List[AcordoSchema] = Field(
        default_factory=list,
        description="Lista de acordos jurídicos e respectivos documentos do autor",
    )


class AcordoDetalheResponse(BaseModel):
    """Resposta detalhada de um acordo específico junto aos dados do seu autor."""

    acordo: AcordoSchema
    autor: AutorSchema


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope padronizado para respostas paginadas da API."""

    total: int = Field(..., description="Total de registros encontrados")
    page: int = Field(..., description="Página atual (iniciando em 1)")
    size: int = Field(..., description="Quantidade máxima de itens por página")
    pages: int = Field(..., description="Total de páginas disponíveis")
    items: List[T] = Field(..., description="Itens da página atual")


class EstatisticaGeralResponse(BaseModel):
    """Indicadores consolidados da base de acordos jurídicos."""

    total_autores: int
    total_acordos: int
    total_documentos: int
    media_acordos_por_autor: float
    media_documentos_por_acordo: float


class TokenRequest(BaseModel):
    """Credenciais para geração de token JWT."""

    username: str = Field(..., examples=["admin"])
    password: str = Field(..., examples=["admin123"])


class TokenResponse(BaseModel):
    """Resposta contendo o token JWT de acesso."""

    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class HealthCheckResponse(BaseModel):
    """Status de saúde da API e conectividade com o banco de dados."""

    status: str = Field(..., examples=["healthy"])
    service: str = Field(..., examples=["acordos-juridicos-api"])
    database: str = Field(..., examples=["connected"])


class DLQRedriveResponse(BaseModel):
    """Resultado do reprocessamento sob demanda da fila Dead Letter Queue (DLQ)."""

    reprocessed_count: int = Field(..., description="Quantidade de mensagens reprocessadas com sucesso")
    failed_count: int = Field(..., description="Quantidade de mensagens que voltaram a falhar")
    correlation_id: str = Field(..., description="Identificador de correlação da operação")
