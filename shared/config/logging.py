"""Configuração de logs estruturados em formato JSON compatível com AWS CloudWatch Logs."""

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict, Optional
import uuid

from shared.config.settings import get_settings

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Retorna o correlation_id do contexto atual ou gera um novo UUID v4."""
    cid = correlation_id_ctx.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Define o correlation_id no contexto de execução atual."""
    value = (cid or "").strip() or str(uuid.uuid4())
    correlation_id_ctx.set(value)
    return value


def mask_email(email: str) -> str:
    """Mascara endereço de e-mail para conformidade LGPD (ex.: 'S***@april.biz')."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    prefix = local[0] if local else "*"
    return f"{prefix}***@{domain}"


def mask_phone(phone: str) -> str:
    """Mascara telefone exibindo apenas os 4 últimos dígitos."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) >= 4:
        return f"***-{digits[-4:]}"
    return "***"


def mask_address(address: str) -> str:
    """Mascara logradouro e complemento preservando apenas cidade/CEP quando presente."""
    if not address:
        return "***"
    if " - " in address:
        _, city_part = address.split(" - ", 1)
        return f"*** - {city_part}"
    return "***"


class CloudWatchJsonFormatter(logging.Formatter):
    """Formata registros de log como objetos JSON estruturados com correlation_id."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": correlation_id_ctx.get() or "system",
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            sanitized_extra = dict(record.extra_data)
            if "email" in sanitized_extra and isinstance(sanitized_extra["email"], str):
                sanitized_extra["email"] = mask_email(sanitized_extra["email"])
            if "telefone" in sanitized_extra and isinstance(sanitized_extra["telefone"], str):
                sanitized_extra["telefone"] = mask_phone(sanitized_extra["telefone"])
            log_payload.update(sanitized_extra)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Cria e retorna um logger configurado com saída JSON para stdout."""
    settings = get_settings()
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CloudWatchJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    return logger
