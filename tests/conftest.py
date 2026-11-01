"""Fixtures compartilhadas do Pytest para banco SQLite em memória, dados de exemplo e cliente HTTP."""

from collections.abc import Callable, Generator
from typing import Any, Dict

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.auth import create_access_token
from services.api.main import create_app
from shared.config.database import Base, get_db
from shared.config.settings import get_settings
from shared.models.entities import AcordoORM, AutorORM, DocumentoORM


@pytest.fixture()
def db_session_factory() -> Generator[Callable[[], Session], None, None]:
    """Cria um banco SQLite em memória isolado por teste e retorna sua factory de sessão."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(
    db_session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """Fornece uma sessão ativa de banco de dados para testes."""
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_raw_api_data() -> Dict[str, Any]:
    """Retorna payloads simulados idênticos aos retornados pela API JSONPlaceholder."""
    return {
        "user": {
            "id": 1,
            "name": "Leanne Graham",
            "username": "Bret",
            "email": "Sincere@april.biz",
            "address": {
                "street": "Kulas Light",
                "suite": "Apt. 556",
                "city": "Gwenborough",
                "zipcode": "92998-3874",
            },
            "phone": "1-770-736-8031 x56442",
            "website": "hildegard.org",
            "company": {
                "name": "Romaguera-Crona",
                "catchPhrase": "Multi-layered client-server neural-net",
                "bs": "harness real-time e-markets",
            },
        },
        "album": {
            "userId": 1,
            "id": 10,
            "title": "quidem molestiae enim",
        },
        "photos": [
            {
                "albumId": 10,
                "id": 100,
                "title": "accusamus beatae ad facilis cum similique qui sunt",
                "url": "https://via.placeholder.com/600/92c952",
                "thumbnailUrl": "https://via.placeholder.com/150/92c952",
            },
            {
                "albumId": 10,
                "id": 101,
                "title": "reprehenderit est deserunt velit ipsam",
                "url": "https://via.placeholder.com/600/771796",
                "thumbnailUrl": "https://via.placeholder.com/150/771796",
            },
        ],
    }


@pytest.fixture()
def seeded_db(db_session: Session) -> Session:
    """Popula o banco de testes com Autores, Acordos e Documentos para testes da API."""
    autor1 = AutorORM(
        id=1,
        nome="Leanne Graham",
        email="Sincere@april.biz",
        telefone="1-770-736-8031 x56442",
        endereco="Kulas Light, Apt. 556 - Gwenborough CEP 92998-3874",
        empresa_nome="Romaguera-Crona",
        empresa_segmento="harness real-time e-markets",
    )
    autor2 = AutorORM(
        id=2,
        nome="Ervin Howell",
        email="Shanna@melissa.tv",
        telefone="010-692-6593 x09125",
        endereco="Victor Plains, Suite 879 - Wisokyburgh CEP 90566-7771",
        empresa_nome="Deckow-Crist",
        empresa_segmento="synergize scalable supply-chains",
    )

    acordo1 = AcordoORM(id=10, autor_id=1, titulo="quidem molestiae enim")
    acordo2 = AcordoORM(id=11, autor_id=1, titulo="sunt qui excepturi placeat culpa")
    acordo3 = AcordoORM(id=20, autor_id=2, titulo="distinctio laborum qui")

    doc1 = DocumentoORM(
        id=100,
        acordo_id=10,
        titulo="accusamus beatae ad facilis",
        url="https://via.placeholder.com/600/92c952",
        thumbnail_url="https://via.placeholder.com/150/92c952",
    )
    doc2 = DocumentoORM(
        id=101,
        acordo_id=10,
        titulo="reprehenderit est deserunt",
        url="https://via.placeholder.com/600/771796",
        thumbnail_url="https://via.placeholder.com/150/771796",
    )

    db_session.add_all([autor1, autor2, acordo1, acordo2, acordo3, doc1, doc2])
    db_session.commit()
    return db_session


@pytest.fixture()
def api_client(seeded_db: Session) -> Generator[TestClient, None, None]:
    """Retorna um TestClient FastAPI configurado com override da sessão de banco de dados."""
    app = create_app(initialize_database=False)

    def override_get_db() -> Generator[Session, None, None]:
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> Dict[str, str]:
    """Gera cabeçalho Authorization Bearer com JWT válido para testes de integração."""
    settings = get_settings()
    token = create_access_token(subject=settings.API_ADMIN_USER, settings=settings)
    return {"Authorization": f"Bearer {token}"}
