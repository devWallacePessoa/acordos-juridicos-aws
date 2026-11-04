"""Modelo relacional ORM da tabela 'autores' (Pai na hierarquia 1:N de Acordos)."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.config.database import Base

if TYPE_CHECKING:
    from shared.models.acordo_model import AcordoORM


def utc_now() -> datetime:
    """Retorna o timestamp atual em UTC."""
    return datetime.now(timezone.utc)


class AutorORM(Base):
    """Entidade que representa o Autor de ações judiciais contra o banco."""

    __tablename__ = "autores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    telefone: Mapped[str] = mapped_column(String(100), nullable=False)
    endereco: Mapped[str] = mapped_column(String(500), nullable=False)
    empresa_nome: Mapped[str] = mapped_column(String(255), nullable=False)
    empresa_segmento: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    acordos: Mapped[List["AcordoORM"]] = relationship(
        "AcordoORM",
        back_populates="autor",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AcordoORM.id",
    )
