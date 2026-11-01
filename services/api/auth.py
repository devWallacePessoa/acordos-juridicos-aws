"""Módulo de autenticação e autorização com suporte a JWT Bearer Token e X-API-Key."""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Dict, Optional

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import jwt

from services.api.exceptions import AuthenticationError
from shared.config.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_access_token(
    subject: str,
    settings: Optional[Settings] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Gera um token JWT assinado para o usuário autenticado."""
    cfg = settings or get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=cfg.JWT_EXPIRE_MINUTES)
    )
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "scope": "acordos:read",
    }
    return jwt.encode(payload, cfg.JWT_SECRET_KEY, algorithm=cfg.JWT_ALGORITHM)


def verify_jwt_token(token: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Decodifica e valida a assinatura e expiração de um token JWT."""
    cfg = settings or get_settings()
    try:
        decoded = jwt.decode(
            token,
            cfg.JWT_SECRET_KEY,
            algorithms=[cfg.JWT_ALGORITHM],
        )
        return dict(decoded)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token JWT expirado.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Token JWT inválido.") from exc


def authenticate_admin_credentials(
    username: str,
    password: str,
    settings: Optional[Settings] = None,
) -> bool:
    """Valida credenciais administrativas em tempo constante contra ataques de timing."""
    cfg = settings or get_settings()
    valid_user = secrets.compare_digest(username, cfg.API_ADMIN_USER)
    valid_pass = secrets.compare_digest(password, cfg.API_ADMIN_PASSWORD)
    return valid_user and valid_pass


def require_auth(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header_scheme),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Dependência FastAPI que autentica via Bearer JWT ou cabeçalho X-API-Key."""
    if api_key and secrets.compare_digest(api_key, settings.API_STATIC_KEY):
        return {"sub": "api-key-client", "auth_type": "api_key", "scope": "acordos:read"}

    if bearer and bearer.credentials:
        claims = verify_jwt_token(bearer.credentials, settings=settings)
        claims["auth_type"] = "jwt"
        return claims

    raise AuthenticationError(
        "Autenticação obrigatória. Envie 'Authorization: Bearer <token>' ou cabeçalho 'X-API-Key'."
    )
