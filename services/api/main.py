"""Ponto de entrada da API FastAPI para Consulta de Acordos Jurídicos."""

from contextlib import asynccontextmanager, suppress
import asyncio
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.api.controllers.acordo_controller import auth_router, v1_router
from services.api.datadog_telemetry import (
    _infra_metrics_loop,
    setup_datadog_telemetry,
)
from services.api.exceptions import register_exception_handlers
from services.api.schemas.acordo_schema import HealthCheckResponse
from shared.config.database import engine, get_db, init_db
from shared.config.logging import get_logger

logger = get_logger(__name__)


def create_app(initialize_database: bool = True) -> FastAPI:
    """Factory de criação da aplicação FastAPI configurada com middlewares, rotas e handlers."""

    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Inicializa o schema de banco de dados e coletor Datadog na subida da aplicação."""
        logger.info("Inicializando API de Consulta de Acordos Jurídicos")
        collector_task = None
        if initialize_database:
            init_db()
            collector_task = asyncio.create_task(
                _infra_metrics_loop(db_engine=engine, interval_seconds=30)
            )
        try:
            yield
        finally:
            if collector_task is not None:
                collector_task.cancel()
                with suppress(asyncio.CancelledError):
                    await collector_task
            logger.info("Encerrando API de Consulta de Acordos Jurídicos")

    app = FastAPI(
        title="API de Consulta de Acordos Jurídicos",
        description=(
            "API RESTful para consulta hierárquica de Autores, Acordos e Documentos "
            "processados assincronamente via AWS SQS e PostgreSQL."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=app_lifespan,
    )

    setup_datadog_telemetry(app, db_engine=engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get(
        "/health",
        response_model=HealthCheckResponse,
        tags=["Observabilidade"],
        summary="Health Check da Aplicação e Banco de Dados",
    )
    def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
        db_status = "connected"
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_status = "disconnected"
        return HealthCheckResponse(
            status="healthy" if db_status == "connected" else "degraded",
            service="acordos-juridicos-api",
            database=db_status,
        )

    app.include_router(auth_router)
    app.include_router(v1_router)
    return app


app = create_app()
