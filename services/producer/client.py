"""Cliente HTTP resiliente para consumo dos 6 endpoints da API pública JSONPlaceholder."""

from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared.config.logging import get_logger
from shared.config.settings import get_settings

logger = get_logger(__name__)


class ExternalAPIClient:
    """Cliente HTTP com retry exponencial para consumir a API pública de usuários, álbuns e fotos."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.EXTERNAL_API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.EXTERNAL_API_TIMEOUT
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Accept": "application/json", "User-Agent": "AcordosJuridicosProducer/1.0"},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _get(self, path: str) -> Any:
        """Executa uma requisição GET com tratamento de erros e retry automático."""
        response = self._client.get(path)
        response.raise_for_status()
        return response.json()

    def get_users(self) -> List[Dict[str, Any]]:
        """1. GET /users - Lista todos os autores cadastrados."""
        logger.info("Consultando todos os autores na API externa", extra={"extra_data": {"endpoint": "/users"}})
        data = self._get("/users")
        return list(data) if isinstance(data, list) else []

    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """2. GET /users/{id} - Consulta detalhes de um autor específico."""
        endpoint = f"/users/{user_id}"
        logger.debug("Consultando detalhes do autor", extra={"extra_data": {"endpoint": endpoint, "user_id": user_id}})
        data = self._get(endpoint)
        return dict(data) if isinstance(data, dict) else {}

    def get_user_albums(self, user_id: int) -> List[Dict[str, Any]]:
        """3. GET /users/{id}/albums - Lista os acordos de um autor."""
        endpoint = f"/users/{user_id}/albums"
        logger.debug("Consultando acordos do autor", extra={"extra_data": {"endpoint": endpoint, "user_id": user_id}})
        data = self._get(endpoint)
        return list(data) if isinstance(data, list) else []

    def get_album_by_id(self, album_id: int) -> Dict[str, Any]:
        """4. GET /albums/{id} - Consulta detalhes de um acordo específico."""
        endpoint = f"/albums/{album_id}"
        logger.debug("Consultando detalhes do acordo", extra={"extra_data": {"endpoint": endpoint, "album_id": album_id}})
        data = self._get(endpoint)
        return dict(data) if isinstance(data, dict) else {}

    def get_album_photos(self, album_id: int) -> List[Dict[str, Any]]:
        """5. GET /albums/{id}/photos - Lista os documentos de um acordo específico."""
        endpoint = f"/albums/{album_id}/photos"
        logger.debug("Consultando documentos do acordo", extra={"extra_data": {"endpoint": endpoint, "album_id": album_id}})
        data = self._get(endpoint)
        return list(data) if isinstance(data, list) else []

    def get_photo_by_id(self, photo_id: int) -> Dict[str, Any]:
        """6. GET /photos/{id} - Consulta um documento específico."""
        endpoint = f"/photos/{photo_id}"
        logger.debug("Consultando detalhes do documento", extra={"extra_data": {"endpoint": endpoint, "photo_id": photo_id}})
        data = self._get(endpoint)
        return dict(data) if isinstance(data, dict) else {}

    def close(self) -> None:
        """Fecha o pool de conexões HTTP."""
        self._client.close()

    def __enter__(self) -> "ExternalAPIClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
