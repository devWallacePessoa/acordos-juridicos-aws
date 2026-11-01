"""Entidades ORM do SQLAlchemy representando Autor, Acordo e Documento."""

from datetime import datetime, timezone
from typing import List

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.config.database import Base


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


class DocumentoORM(Base):
    """Entidade que representa um Documento comprobatório vinculado a um Acordo."""

    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    acordo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("acordos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    acordo: Mapped["AcordoORM"] = relationship("AcordoORM", back_populates="documentos")
