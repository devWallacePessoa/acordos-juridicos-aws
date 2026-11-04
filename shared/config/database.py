"""Configuração do SQLAlchemy Engine, SessionLocal e Base declarativa."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from shared.config.settings import get_settings


class Base(DeclarativeBase):
    """Classe base declarativa para os modelos ORM do SQLAlchemy 2.0."""


settings = get_settings()

engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def init_db() -> None:
    """Garante a criação das tabelas mapeadas no banco de dados com retry resiliente na subida."""
    import time
    from shared.config.logging import get_logger
    from shared.models import entities  # noqa: F401

    db_logger = get_logger(__name__)
    for attempt in range(1, 6):
        try:
            Base.metadata.create_all(bind=engine)
            db_logger.info("Schema do banco de dados verificado/inicializado com sucesso.")
            return
        except Exception as exc:
            db_logger.warning(
                f"Tentativa {attempt}/5 de conectar ao banco na subida falhou: {exc}"
            )
            if attempt < 5:
                time.sleep(3)
    db_logger.error("Nao foi possivel inicializar o schema na subida; a API continuara rodando.")


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI para fornecer uma sessão de banco de dados por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
