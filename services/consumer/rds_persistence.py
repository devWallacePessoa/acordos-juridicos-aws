"""Persistência transacional e idempotente (Upsert) no banco de dados relacional PostgreSQL / Amazon RDS."""

from typing import Any, Callable, Dict, List

from sqlalchemy.orm import Session

from shared.config.logging import get_logger
from shared.models.entities import AcordoORM, AutorORM, DocumentoORM

logger = get_logger(__name__)


def persist_autor_payload(
    session_factory: Callable[[], Session],
    payload: Dict[str, Any],
) -> int:
    """Persiste de forma transacional e idempotente (merge/upsert) um Autor, seus Acordos e Documentos no RDS."""
    if "autor" not in payload or not isinstance(payload["autor"], dict):
        raise ValueError("Payload inválido: chave obrigatória 'autor' ausente ou malformada.")

    autor_data = payload["autor"]
    empresa_data = autor_data.get("empresa") or {}
    acordos_data: List[Dict[str, Any]] = payload.get("acordos", [])

    autor_id = int(autor_data["id"])

    with session_factory() as session:
        with session.begin():
            autor_entity = AutorORM(
                id=autor_id,
                nome=str(autor_data["nome"]),
                email=str(autor_data["email"]),
                telefone=str(autor_data["telefone"]),
                endereco=str(autor_data["endereco"]),
                empresa_nome=str(empresa_data.get("nome", "")),
                empresa_segmento=str(empresa_data.get("segmento", "")),
            )
            session.merge(autor_entity)

            for acordo_item in acordos_data:
                acordo_id = int(acordo_item["id"])
                acordo_entity = AcordoORM(
                    id=acordo_id,
                    autor_id=autor_id,
                    titulo=str(acordo_item["titulo"]),
                )
                session.merge(acordo_entity)

                for doc_item in acordo_item.get("documentos", []):
                    doc_entity = DocumentoORM(
                        id=int(doc_item["id"]),
                        acordo_id=acordo_id,
                        titulo=str(doc_item["titulo"]),
                        url=str(doc_item["url"]),
                        thumbnail_url=str(
                            doc_item.get("thumbnailUrl") or doc_item.get("thumbnail_url") or ""
                        ),
                    )
                    session.merge(doc_entity)

    total_docs = sum(len(ac.get("documentos", [])) for ac in acordos_data)
    nome_autor = autor_data.get("nome", "")
    logger.info(
        f"Autor {autor_id} ('{nome_autor}') persistido no RDS com sucesso ({len(acordos_data)} acordos, {total_docs} documentos)",
        extra={
            "extra_data": {
                "autor_id": autor_id,
                "nome_autor": nome_autor,
                "qtd_acordos": len(acordos_data),
                "qtd_documentos": total_docs,
            }
        },
    )
    return autor_id
