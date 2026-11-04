"""Modelo relacional ORM da tabela 'documentos' (Vinculado a 'acordos' via chave estrangeira)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.config.database import Base
from shared.models.autor_model import utc_now

if TYPE_CHECKING:
    from shared.models.acordo_model import AcordoORM


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
