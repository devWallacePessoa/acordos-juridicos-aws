"""Configuração de logs estruturados em formato JSON compatível com AWS CloudWatch Logs."""

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict

from shared.config.settings import get_settings


class CloudWatchJsonFormatter(logging.Formatter):
    """Formata registros de log como objetos JSON estruturados."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload.update(record.extra_data)

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
