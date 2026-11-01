"""Regras de negócio e conversão de entidades ORM para os schemas de resposta da API."""

import math
from typing import Optional

from services.api.exceptions import ResourceNotFoundError
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
)
from shared.models.entities import AcordoORM, AutorORM, DocumentoORM


class AcordoService:
    """Serviço de aplicação responsável pela consulta e montagem da hierarquia de Acordos."""

    def __init__(self, repository: AcordoRepository) -> None:
        self.repository = repository

    @staticmethod
    def _to_documento_schema(doc: DocumentoORM) -> DocumentoSchema:
        return DocumentoSchema(
            id=doc.id,
            titulo=doc.titulo,
            url=doc.url,
            thumbnailUrl=doc.thumbnail_url,
        )

    @classmethod
    def _to_acordo_schema(cls, acordo: AcordoORM, include_docs: bool = True) -> AcordoSchema:
        docs = (
            [cls._to_documento_schema(d) for d in acordo.documentos]
            if include_docs and acordo.documentos
            else []
        )
        return AcordoSchema(
            id=acordo.id,
            titulo=acordo.titulo,
            documentos=docs,
        )

    @staticmethod
    def _to_autor_schema(autor: AutorORM) -> AutorSchema:
        return AutorSchema(
            id=autor.id,
            nome=autor.nome,
            email=autor.email,
            telefone=autor.telefone,
            endereco=autor.endereco,
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
    ) -> PaginatedResponse[AutorResumoSchema]:
        """Retorna lista paginada de autores com o total de acordos de cada autor."""
        autores, total = self.repository.list_autores(
            page=page, size=size, nome=nome, segmento=segmento
        )
        items = [
            AutorResumoSchema(
                id=a.id,
                nome=a.nome,
                email=a.email,
                telefone=a.telefone,
                endereco=a.endereco,
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
    ) -> AutorComAcordosSchema:
        """Retorna a estrutura completa Autor (1) -> (N) Acordos (1) -> (N) Documentos."""
        autor = self.repository.get_autor_with_acordos_and_documentos(autor_id)
        if not autor:
            raise ResourceNotFoundError("Autor", autor_id)

        acordos = [
            self._to_acordo_schema(ac, include_docs=incluir_documentos)
            for ac in autor.acordos
        ]
        return AutorComAcordosSchema(
            autor=self._to_autor_schema(autor),
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

    def obter_acordo_por_id(self, acordo_id: int) -> AcordoDetalheResponse:
        """Retorna detalhes de um acordo específico, seus documentos e os dados do autor."""
        acordo = self.repository.get_acordo_by_id(acordo_id)
        if not acordo:
            raise ResourceNotFoundError("Acordo", acordo_id)

        return AcordoDetalheResponse(
            acordo=self._to_acordo_schema(acordo, include_docs=True),
            autor=self._to_autor_schema(acordo.autor),
        )

    def obter_documento_por_id(self, documento_id: int) -> DocumentoSchema:
        """Retorna os dados de um documento específico pelo seu ID."""
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
