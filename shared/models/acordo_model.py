"""Modelo relacional ORM da tabela 'acordos' (Vinculado a 'autores' e pai de 'documentos')."""

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.config.database import Base
from shared.models.autor_model import utc_now

if TYPE_CHECKING:
    from shared.models.autor_model import AutorORM
    from shared.models.documento_model import DocumentoORM


class AcordoORM(Base):
    """Entidade que representa um Acordo jurídico vinculado a um Autor."""

    __tablename__ = "acordos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    autor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("autores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    autor: Mapped["AutorORM"] = relationship("AutorORM", back_populates="acordos")
    documentos: Mapped[List["DocumentoORM"]] = relationship(
        "DocumentoORM",
        back_populates="acordo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentoORM.id",
    )
