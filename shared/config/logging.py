"""Configuração de logs estruturados em formato JSON compatível com AWS CloudWatch Logs e Datadog HTTP Intake."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
import socket
import sys
from typing import Any, Dict, Optional
import urllib.request
import uuid

from shared.config.settings import get_settings

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
_dd_log_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dd-log-shipper")
_HOSTNAME = socket.gethostname()


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


def _resolve_component_service(logger_name: str) -> str:
    """Identifica qual peça do fluxo gerou o log (Producer, Consumer ou API) para facilitar filtro no Datadog."""
    if "producer" in logger_name:
        return "acordos-juridicos-producer"
    if "consumer" in logger_name:
        return "acordos-juridicos-consumer"
    return os.getenv("DD_SERVICE", "acordos-juridicos-api").strip()


def _ship_log_to_datadog(dd_entry: Dict[str, Any]) -> None:
    """Envia o registro de log estruturado para a API HTTP v2 do Datadog em background."""
    api_key = os.getenv("DD_API_KEY", "").strip()
    if not api_key or os.getenv("PYTEST_CURRENT_TEST"):
        return
    dd_site = os.getenv("DD_SITE", "datadoghq.com").strip()
    url = f"https://http-intake.logs.{dd_site}/api/v2/logs"
    try:
        data = json.dumps([dd_entry], ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "DD-API-KEY": api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            resp.read()
    except Exception:
        pass


class CloudWatchJsonFormatter(logging.Formatter):
    """Formata registros de log como objetos JSON estruturados com correlation_id."""

    def format(self, record: logging.LogRecord) -> str:
        cid = correlation_id_ctx.get() or "system"
        component_service = _resolve_component_service(record.name)
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": component_service,
            "logger": record.name,
            "correlation_id": cid,
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


class DatadogHttpLogHandler(logging.Handler):
    """Handler assíncrono que envia todos os logs de Producer, Consumer e API direto ao Datadog."""

    def emit(self, record: logging.LogRecord) -> None:
        if not os.getenv("DD_API_KEY", "").strip() or os.getenv("PYTEST_CURRENT_TEST"):
            return
        try:
            cid = correlation_id_ctx.get() or "system"
            dd_env = os.getenv("DD_ENV", "prod").strip()
            service_name = _resolve_component_service(record.name)
            status_map = {
                "DEBUG": "debug",
                "INFO": "info",
                "WARNING": "warn",
                "ERROR": "error",
                "CRITICAL": "error",
            }
            dd_status = status_map.get(record.levelname, "info")

            dd_entry: Dict[str, Any] = {
                "ddsource": "python",
                "ddtags": f"env:{dd_env},service:{service_name},logger:{record.name},correlation_id:{cid}",
                "hostname": _HOSTNAME,
                "service": service_name,
                "status": dd_status,
                "correlation_id": cid,
                "logger": {
                    "name": record.name,
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                },
                "message": f"[{cid}] {record.getMessage()}",
            }

            if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
                sanitized_extra = dict(record.extra_data)
                if "email" in sanitized_extra and isinstance(sanitized_extra["email"], str):
                    sanitized_extra["email"] = mask_email(sanitized_extra["email"])
                if "telefone" in sanitized_extra and isinstance(sanitized_extra["telefone"], str):
                    sanitized_extra["telefone"] = mask_phone(sanitized_extra["telefone"])
                dd_entry.update(sanitized_extra)

            if record.exc_info and self.formatter:
                dd_entry["error"] = {
                    "stack": self.formatter.formatException(record.exc_info),
                    "message": record.getMessage(),
                }

            _dd_log_executor.submit(_ship_log_to_datadog, dd_entry)
        except Exception:
            pass


def get_logger(name: str) -> logging.Logger:
    """Cria e retorna um logger configurado com saída JSON para stdout (CloudWatch) e Datadog HTTP."""
    settings = get_settings()
    logger = logging.getLogger(name)

    if not logger.handlers:
        formatter = CloudWatchJsonFormatter()

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        dd_handler = DatadogHttpLogHandler()
        dd_handler.setFormatter(formatter)
        logger.addHandler(dd_handler)

        logger.propagate = False

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    return logger
