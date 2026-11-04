"""Gerenciamento centralizado de configurações via variáveis de ambiente com Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais da aplicação carregadas do ambiente ou arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Banco de Dados
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "acordos_db"
    DATABASE_URL: Optional[str] = None

    # AWS / LocalStack (SQS)
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = "test"
    AWS_SECRET_ACCESS_KEY: str = "test"
    AWS_ENDPOINT_URL: Optional[str] = "http://localhost:4566"
    SQS_QUEUE_NAME: str = "acordos-juridicos-queue"
    SQS_DLQ_NAME: str = "acordos-juridicos-dlq"
    SQS_QUEUE_URL: Optional[str] = None
    SQS_DLQ_URL: Optional[str] = None

    # API Pública Externa
    EXTERNAL_API_BASE_URL: str = "https://jsonplaceholder.typicode.com"
    EXTERNAL_API_TIMEOUT: float = 15.0
    EXTERNAL_API_MAX_RETRIES: int = 3
    PRODUCER_MAX_USERS: int = 10

    # Autenticação JWT & Segurança
    JWT_SECRET_KEY: str = "super-secret-jwt-key-acordos-juridicos-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    API_ADMIN_USER: str = "admin"
    API_ADMIN_PASSWORD: str = "admin123"
    API_KEY_HEADER: str = "X-API-Key"
    API_STATIC_KEY: str = "chave-secreta-api-acordos-2026"

    # Aplicação & Observabilidade
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CONSUMER_POLL_INTERVAL_SECONDS: int = 2
    CONSUMER_MAX_MESSAGES: int = 10

    @field_validator("AWS_ENDPOINT_URL", "SQS_QUEUE_URL", "SQS_DLQ_URL", "DATABASE_URL", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Optional[str]) -> Optional[str]:
        """Converte variável de ambiente vazia em None (ex.: AWS_ENDPOINT_URL vazio na AWS real)."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def sqlalchemy_database_url(self) -> str:
        """Retorna a URL de conexão SQLAlchemy priorizando DB_HOST quando diferente do padrão local."""
        if self.DB_HOST and self.DB_HOST not in ("localhost", "127.0.0.1"):
            return (
                f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância em cache das configurações da aplicação."""
    return Settings()
