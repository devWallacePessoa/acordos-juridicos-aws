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
    """Garante a criação das tabelas mapeadas no banco de dados caso não existam."""
    from shared.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI para fornecer uma sessão de banco de dados por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
