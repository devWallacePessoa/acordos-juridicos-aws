"""Regras de negócio e conversão de entidades ORM para os schemas de resposta da API."""

import math
from typing import Optional

from services.api.exceptions import DomainError, ResourceNotFoundError
from services.api.repositories.acordo_repository import AcordoRepository
from services.api.schemas.acordo_schema import (
    AcordoDetalheResponse,
    AcordoSchema,
    AutorComAcordosSchema,
    AutorResumoSchema,
    AutorSchema,
    DocumentoSchema,
    EmpresaSchema,
    EstatisticaGeralResponse,
    PaginatedResponse,
    ResumoAcordosSchema,
)
from shared.config.logging import mask_address, mask_email, mask_phone
from shared.models.entities import AcordoORM, AutorORM, DocumentoORM


class AcordoService:
    """Serviço de aplicação responsável pela consulta e montagem da hierarquia de Acordos."""

    def __init__(self, repository: AcordoRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_positive_id(identifier: int, field_name: str = "id") -> None:
        if identifier <= 0:
            raise DomainError(
                message=f"Parâmetro '{field_name}' inválido ({identifier}). Deve ser um inteiro positivo maior que zero.",
                status_code=400,
                error_code="INVALID_ID",
                details={"field": field_name, "value": identifier},
            )

    @staticmethod
    def _to_documento_schema(doc: DocumentoORM) -> DocumentoSchema:
        return DocumentoSchema(
            id=doc.id,
            titulo=doc.titulo,
            url=doc.url,
            thumbnailUrl=doc.thumbnail_url,
        )

    @classmethod
    def _to_acordo_schema(
        cls,
        acordo: AcordoORM,
        include_docs: bool = True,
        doc_page: Optional[int] = None,
        doc_size: Optional[int] = None,
    ) -> AcordoSchema:
        raw_docs = list(acordo.documentos) if acordo.documentos else []
        total_docs = len(raw_docs)
        if not include_docs:
            docs_slice: list[DocumentoORM] = []
        elif doc_page is not None and doc_size is not None and doc_page >= 1 and doc_size >= 1:
            start = (doc_page - 1) * doc_size
            docs_slice = raw_docs[start : start + doc_size]
        else:
            docs_slice = raw_docs

        docs = [cls._to_documento_schema(d) for d in docs_slice]
        return AcordoSchema(
            id=acordo.id,
            titulo=acordo.titulo,
            quantidadeDocumentos=total_docs,
            documentos=docs,
        )

    @staticmethod
    def _to_autor_schema(autor: AutorORM, mascarar_dados: bool = False) -> AutorSchema:
        return AutorSchema(
            id=autor.id,
            nome=autor.nome,
            email=mask_email(autor.email) if mascarar_dados else autor.email,
            telefone=mask_phone(autor.telefone) if mascarar_dados else autor.telefone,
            endereco=mask_address(autor.endereco) if mascarar_dados else autor.endereco,
            empresa=EmpresaSchema(
                nome=autor.empresa_nome,
                segmento=autor.empresa_segmento,
            ),
        )

    def listar_autores(
        self,
        page: int = 1,
        size: int = 10,
        nome: Optional[str] = None,
        segmento: Optional[str] = None,
        mascarar_dados: bool = False,
    ) -> PaginatedResponse[AutorResumoSchema]:
        """Retorna lista paginada de autores com o total de acordos de cada autor."""
        autores, total = self.repository.list_autores(
            page=page, size=size, nome=nome, segmento=segmento
        )
        items = [
            AutorResumoSchema(
                id=a.id,
                nome=a.nome,
                email=mask_email(a.email) if mascarar_dados else a.email,
                telefone=mask_phone(a.telefone) if mascarar_dados else a.telefone,
                endereco=mask_address(a.endereco) if mascarar_dados else a.endereco,
                empresa=EmpresaSchema(
                    nome=a.empresa_nome,
                    segmento=a.empresa_segmento,
                ),
                total_acordos=len(a.acordos) if a.acordos else 0,
            )
            for a in autores
        ]
        pages = math.ceil(total / size) if total > 0 else 0
        return PaginatedResponse[AutorResumoSchema](
            total=total,
            page=page,
            size=size,
            pages=pages,
            items=items,
        )

    def obter_acordos_por_autor(
        self,
        autor_id: int,
        incluir_documentos: bool = True,
        doc_page: Optional[int] = None,
        doc_size: Optional[int] = None,
        mascarar_dados: bool = False,
    ) -> AutorComAcordosSchema:
        """Retorna a estrutura completa Autor (1) -> Resumo -> (N) Acordos (1) -> (N) Documentos."""
        self._validate_positive_id(autor_id, "autor_id")
        autor = self.repository.get_autor_with_acordos_and_documentos(autor_id)
        if not autor:
            raise ResourceNotFoundError("Autor", autor_id)

        acordos = [
            self._to_acordo_schema(
                ac,
                include_docs=incluir_documentos,
                doc_page=doc_page,
                doc_size=doc_size,
            )
            for ac in autor.acordos
        ]
        total_docs = sum(ac.quantidadeDocumentos for ac in acordos)
        return AutorComAcordosSchema(
            autor=self._to_autor_schema(autor, mascarar_dados=mascarar_dados),
            resumo=ResumoAcordosSchema(
                quantidadeAcordos=len(acordos),
                quantidadeDocumentos=total_docs,
            ),
            acordos=acordos,
        )

    def listar_acordos(
        self,
        page: int = 1,
        size: int = 10,
        autor_id: Optional[int] = None,
        titulo: Optional[str] = None,
        incluir_documentos: bool = True,
    ) -> PaginatedResponse[AcordoSchema]:
        """Retorna lista paginada de acordos com filtro opcional por autor ou título."""
        if autor_id is not None:
            self._validate_positive_id(autor_id, "autor_id")
        acordos, total = self.repository.list_acordos(
            page=page, size=size, autor_id=autor_id, titulo=titulo
        )
        items = [
            self._to_acordo_schema(ac, include_docs=incluir_documentos)
            for ac in acordos
        ]
        pages = math.ceil(total / size) if total > 0 else 0
        return PaginatedResponse[AcordoSchema](
            total=total,
            page=page,
            size=size,
            pages=pages,
            items=items,
        )

    def obter_acordo_por_id(
        self,
        acordo_id: int,
        mascarar_dados: bool = False,
    ) -> AcordoDetalheResponse:
        """Retorna detalhes de um acordo específico, seus documentos e os dados do autor."""
        self._validate_positive_id(acordo_id, "acordo_id")
        acordo = self.repository.get_acordo_by_id(acordo_id)
        if not acordo:
            raise ResourceNotFoundError("Acordo", acordo_id)

        return AcordoDetalheResponse(
            acordo=self._to_acordo_schema(acordo, include_docs=True),
            autor=self._to_autor_schema(acordo.autor, mascarar_dados=mascarar_dados),
        )

    def obter_documento_por_id(self, documento_id: int) -> DocumentoSchema:
        """Retorna os dados de um documento específico pelo seu ID."""
        self._validate_positive_id(documento_id, "documento_id")
        doc = self.repository.get_documento_by_id(documento_id)
        if not doc:
            raise ResourceNotFoundError("Documento", documento_id)
        return self._to_documento_schema(doc)

    def obter_estatisticas(self) -> EstatisticaGeralResponse:
        """Calcula estatísticas agregadas de autores, acordos e documentos."""
        stats = self.repository.get_estatisticas_gerais()
        total_autores = stats["total_autores"]
        total_acordos = stats["total_acordos"]
        total_documentos = stats["total_documentos"]

        media_acordos = round(total_acordos / total_autores, 2) if total_autores > 0 else 0.0
        media_docs = round(total_documentos / total_acordos, 2) if total_acordos > 0 else 0.0

        return EstatisticaGeralResponse(
            total_autores=total_autores,
            total_acordos=total_acordos,
            total_documentos=total_documentos,
            media_acordos_por_autor=media_acordos,
            media_documentos_por_acordo=media_docs,
        )
