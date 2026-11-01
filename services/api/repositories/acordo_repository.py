"""Repositório SQLAlchemy otimizado com carregamento selectinload para Autores, Acordos e Documentos."""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from shared.models.entities import AcordoORM, AutorORM, DocumentoORM


class AcordoRepository:
    """Encapsula todas as consultas SQL relacionais para Autores, Acordos e Documentos."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_autores(
        self,
        page: int = 1,
        size: int = 10,
        nome: Optional[str] = None,
        segmento: Optional[str] = None,
    ) -> Tuple[List[AutorORM], int]:
        """Lista autores com paginação, filtros opcionais e eager loading de acordos."""
        stmt = select(AutorORM).options(selectinload(AutorORM.acordos))
        count_stmt = select(func.count(AutorORM.id))

        if nome:
            pattern = f"%{nome.strip()}%"
            stmt = stmt.where(AutorORM.nome.ilike(pattern))
            count_stmt = count_stmt.where(AutorORM.nome.ilike(pattern))

        if segmento:
            seg_pattern = f"%{segmento.strip()}%"
            stmt = stmt.where(AutorORM.empresa_segmento.ilike(seg_pattern))
            count_stmt = count_stmt.where(AutorORM.empresa_segmento.ilike(seg_pattern))

        total = int(self.db.execute(count_stmt).scalar_one() or 0)
        offset = (page - 1) * size
        stmt = stmt.order_by(AutorORM.id.asc()).offset(offset).limit(size)
        autores = list(self.db.execute(stmt).scalars().all())
        return autores, total

    def get_autor_with_acordos_and_documentos(self, autor_id: int) -> Optional[AutorORM]:
        """Busca um autor pelo ID trazendo seus acordos e documentos na hierarquia completa."""
        stmt = (
            select(AutorORM)
            .where(AutorORM.id == autor_id)
            .options(
                selectinload(AutorORM.acordos).selectinload(AcordoORM.documentos)
            )
        )
        return self.db.execute(stmt).scalars().first()

    def list_acordos(
        self,
        page: int = 1,
        size: int = 10,
        autor_id: Optional[int] = None,
        titulo: Optional[str] = None,
    ) -> Tuple[List[AcordoORM], int]:
        """Lista acordos paginados com seus documentos e filtros por autor_id ou título."""
        stmt = select(AcordoORM).options(
            selectinload(AcordoORM.documentos),
            selectinload(AcordoORM.autor),
        )
        count_stmt = select(func.count(AcordoORM.id))

        if autor_id is not None:
            stmt = stmt.where(AcordoORM.autor_id == autor_id)
            count_stmt = count_stmt.where(AcordoORM.autor_id == autor_id)

        if titulo:
            pattern = f"%{titulo.strip()}%"
            stmt = stmt.where(AcordoORM.titulo.ilike(pattern))
            count_stmt = count_stmt.where(AcordoORM.titulo.ilike(pattern))

        total = int(self.db.execute(count_stmt).scalar_one() or 0)
        offset = (page - 1) * size
        stmt = stmt.order_by(AcordoORM.id.asc()).offset(offset).limit(size)
        acordos = list(self.db.execute(stmt).scalars().all())
        return acordos, total

    def get_acordo_by_id(self, acordo_id: int) -> Optional[AcordoORM]:
        """Busca um acordo específico pelo ID com seu autor e seus documentos."""
        stmt = (
            select(AcordoORM)
            .where(AcordoORM.id == acordo_id)
            .options(
                selectinload(AcordoORM.autor),
                selectinload(AcordoORM.documentos),
            )
        )
        return self.db.execute(stmt).scalars().first()

    def get_documento_by_id(self, documento_id: int) -> Optional[DocumentoORM]:
        """Busca um documento específico pelo ID."""
        stmt = select(DocumentoORM).where(DocumentoORM.id == documento_id)
        return self.db.execute(stmt).scalars().first()

    def get_estatisticas_gerais(self) -> Dict[str, int]:
        """Retorna os totais de autores, acordos e documentos persistidos."""
        total_autores = int(
            self.db.execute(select(func.count(AutorORM.id))).scalar_one() or 0
        )
        total_acordos = int(
            self.db.execute(select(func.count(AcordoORM.id))).scalar_one() or 0
        )
        total_documentos = int(
            self.db.execute(select(func.count(DocumentoORM.id))).scalar_one() or 0
        )
        return {
            "total_autores": total_autores,
            "total_acordos": total_acordos,
            "total_documentos": total_documentos,
        }
