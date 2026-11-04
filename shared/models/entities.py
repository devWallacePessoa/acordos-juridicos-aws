""" Ponto central de exportação das entidades ORM (AutorORM, AcordoORM, DocumentoORM)."""

from shared.models.acordo_model import AcordoORM
from shared.models.autor_model import AutorORM, utc_now
from shared.models.documento_model import DocumentoORM

__all__ = ["AutorORM", "AcordoORM", "DocumentoORM", "utc_now"]
