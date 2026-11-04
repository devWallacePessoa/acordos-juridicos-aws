"""Testes unitários para a camada de serviço (AcordoService) e tratamento de erros."""

import pytest
from sqlalchemy.orm import Session

from services.api.exceptions import DomainError, ResourceNotFoundError
from services.api.repositories.acordo_repository import AcordoRepository
from services.api.services.acordo_service import AcordoService


def test_obter_acordos_por_autor_hierarquia_completa(seeded_db: Session) -> None:
    """Verifica se o AcordoService retorna Autor -> Resumo -> Acordos -> Documentos mapeados corretamente."""
    service = AcordoService(AcordoRepository(seeded_db))
    resultado = service.obter_acordos_por_autor(autor_id=1, incluir_documentos=True)

    assert resultado.autor.id == 1
    assert resultado.autor.nome == "Leanne Graham"
    assert resultado.autor.empresa.nome == "Romaguera-Crona"
    assert resultado.autor.empresa.segmento == "harness real-time e-markets"
    assert resultado.resumo.quantidadeAcordos == 2
    assert resultado.resumo.quantidadeDocumentos == 2
    assert len(resultado.acordos) == 2
    assert resultado.acordos[0].quantidadeDocumentos == 2
    assert len(resultado.acordos[0].documentos) == 2
    assert resultado.acordos[0].documentos[0].thumbnailUrl == "https://via.placeholder.com/150/92c952"


def test_obter_acordos_por_autor_paginacao_docs_e_mascaramento_lgpd(seeded_db: Session) -> None:
    """Valida a paginação de documentos dentro do acordo e o mascaramento de dados pessoais (LGPD)."""
    service = AcordoService(AcordoRepository(seeded_db))
    resultado = service.obter_acordos_por_autor(
        autor_id=1,
        incluir_documentos=True,
        doc_page=1,
        doc_size=1,
        mascarar_dados=True,
    )

    assert resultado.autor.email == "S***@april.biz"
    assert resultado.autor.telefone.startswith("***-")
    assert resultado.autor.endereco.startswith("*** - ")
    assert resultado.acordos[0].quantidadeDocumentos == 2
    assert len(resultado.acordos[0].documentos) == 1


def test_obter_acordos_por_autor_id_invalido_levanta_400(seeded_db: Session) -> None:
    """Verifica se informar ID <= 0 lança DomainError com HTTP 400 (requisito obrigatório do Case)."""
    service = AcordoService(AcordoRepository(seeded_db))
    with pytest.raises(DomainError) as exc_info:
        service.obter_acordos_por_autor(autor_id=0)
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "INVALID_ID"


def test_obter_acordos_por_autor_inexistente_levanta_404(seeded_db: Session) -> None:
    """Verifica se buscar um autor inexistente lança ResourceNotFoundError."""
    service = AcordoService(AcordoRepository(seeded_db))
    with pytest.raises(ResourceNotFoundError) as exc_info:
        service.obter_acordos_por_autor(autor_id=9999)
    assert exc_info.value.status_code == 404


def test_estatisticas_gerais_calculo_correto(seeded_db: Session) -> None:
    """Valida o cálculo das médias e totais na camada de negócio."""
    service = AcordoService(AcordoRepository(seeded_db))
    stats = service.obter_estatisticas()

    assert stats.total_autores == 2
    assert stats.total_acordos == 3
    assert stats.total_documentos == 2
    assert stats.media_acordos_por_autor == 1.5
    assert stats.media_documentos_por_acordo == 0.67
