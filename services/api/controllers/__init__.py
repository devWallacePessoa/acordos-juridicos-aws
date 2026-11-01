"""Controllers (Routers FastAPI) da API de Consulta de Acordos."""

from services.api.controllers.acordo_controller import auth_router, v1_router

__all__ = ["auth_router", "v1_router"]
