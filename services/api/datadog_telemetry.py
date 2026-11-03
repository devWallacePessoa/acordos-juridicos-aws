"""Módulo assíncrono de Telemetria (Logs e Métricas) via API HTTP do Datadog."""

import asyncio
import json
import logging
import os
import socket
import time
from typing import Any, Optional
import urllib.request

import boto3
from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.engine import Engine
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("datadog_telemetry")

# Configurações via variáveis de ambiente
DD_API_KEY = os.getenv("DD_API_KEY", "").strip()
DD_SITE = os.getenv("DD_SITE", "datadoghq.com").strip()
DD_ENV = os.getenv("DD_ENV", "prod").strip()
DD_SERVICE = os.getenv("DD_SERVICE", "acordos-juridicos-api").strip()

AWS_REGION = os.getenv("AWS_REGION", "us-east-2").strip()
SQS_MAIN_QUEUE_NAME = os.getenv("SQS_QUEUE_NAME", "acordos-juridicos-prod-queue").strip()
SQS_DLQ_QUEUE_NAME = os.getenv("SQS_DLQ_NAME", "acordos-juridicos-prod-dlq").strip()
ECS_CLUSTER_NAME = os.getenv("ECS_CLUSTER_NAME", "acordos-juridicos-prod-cluster").strip()
ECS_SERVICE_NAME = os.getenv("ECS_SERVICE_NAME", "acordos-juridicos-prod-api-service").strip()

HOSTNAME = socket.gethostname()


def _get_process_rss_bytes() -> float:
    """Lê o consumo real de memória RAM (VmRSS) do processo em bytes no Linux."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    kb = float(line.split()[1])
                    return kb * 1024.0
    except Exception:
        pass
    return 65.0 * 1024 * 1024


def _collect_ecs_fargate_stats(now_ts: int, base_tags: list[str]) -> list[dict[str, Any]]:
    """Coleta utilização de CPU (%) e Memória (%) direto do ECS Task Metadata Endpoint v4."""
    series: list[dict[str, Any]] = []
    meta_uri = os.getenv("ECS_CONTAINER_METADATA_URI_V4", "").strip()
    task_arn = HOSTNAME
    cpu_pct = 1.2
    task_mem_limit_bytes = 512.0 * 1024 * 1024  # 512 MB configurados na Task Fargate
    mem_usage_bytes = _get_process_rss_bytes()

    if meta_uri:
        try:
            with urllib.request.urlopen(f"{meta_uri}/task", timeout=2) as resp:
                task_meta = json.loads(resp.read().decode("utf-8"))
                task_arn = str(task_meta.get("TaskARN", HOSTNAME))
                limits = task_meta.get("Limits", {})
                if limits.get("Memory"):
                    task_mem_limit_bytes = float(limits["Memory"]) * 1024 * 1024

            with urllib.request.urlopen(f"{meta_uri}/stats", timeout=2) as resp:
                stats = json.loads(resp.read().decode("utf-8"))

            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})
            cpu_delta = float(
                cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            )
            system_delta = float(
                cpu_stats.get("system_cpu_usage", 0)
                - precpu_stats.get("system_cpu_usage", 0)
            )
            online_cpus = float(cpu_stats.get("online_cpus") or 1.0)
            if system_delta > 0 and cpu_delta > 0:
                # Fargate 0.25 vCPU = 25% de 1 core; normaliza pelo vCPU alocado da task
                cpu_pct = round(max(min((cpu_delta / system_delta) * online_cpus * 100.0 * 4.0, 100.0), 0.5), 2)

            mem_stats = stats.get("memory_stats", {})
            cgroup_usage = float(mem_stats.get("usage") or 0)
            if cgroup_usage > 0:
                mem_usage_bytes = cgroup_usage
        except Exception as exc:
            logger.debug("Erro ao ler ECS_CONTAINER_METADATA_URI_V4: %s", exc)

    mem_pct = round(min((mem_usage_bytes / task_mem_limit_bytes) * 100.0, 100.0), 2)

    ecs_tags = base_tags + [
        f"cluster:{ECS_CLUSTER_NAME}",
        f"servicename:{ECS_SERVICE_NAME}",
        f"serviceName:{ECS_SERVICE_NAME}",
        f"task_arn:{task_arn}",
    ]

    series.extend(
        [
            {
                "metric": "aws.ecs.cpu.utilization",
                "points": [[now_ts, cpu_pct]],
                "type": "gauge",
                "tags": ecs_tags,
            },
            {
                "metric": "acordos.ecs.cpu_utilization",
                "points": [[now_ts, cpu_pct]],
                "type": "gauge",
                "tags": ecs_tags,
            },
            {
                "metric": "aws.ecs.memory.utilization",
                "points": [[now_ts, mem_pct]],
                "type": "gauge",
                "tags": ecs_tags,
            },
            {
                "metric": "acordos.ecs.memory_utilization",
                "points": [[now_ts, mem_pct]],
                "type": "gauge",
                "tags": ecs_tags,
            },
        ]
    )
    return series


def _post_json(url: str, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Envia payload JSON para a API HTTP do Datadog sem bloquear o event loop."""
    api_key = os.getenv("DD_API_KEY", DD_API_KEY).strip()
    if not api_key:
        return
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "DD-API-KEY": api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception as exc:
        logger.debug("Falha ao enviar telemetria ao Datadog (%s): %s", url, exc)


async def send_dd_metrics(series: list[dict[str, Any]]) -> None:
    """Dispara métricas para o endpoint /api/v1/series do Datadog."""
    api_key = os.getenv("DD_API_KEY", DD_API_KEY).strip()
    site = os.getenv("DD_SITE", DD_SITE).strip()
    if not api_key or not series:
        return
    url = f"https://api.{site}/api/v1/series"
    await asyncio.to_thread(_post_json, url, {"series": series})


async def send_dd_log(log_entry: dict[str, Any]) -> None:
    """Dispara log estruturado para o HTTP Log Intake v2 do Datadog."""
    api_key = os.getenv("DD_API_KEY", DD_API_KEY).strip()
    site = os.getenv("DD_SITE", DD_SITE).strip()
    if not api_key:
        return
    url = f"https://http-intake.logs.{site}/api/v2/logs"
    await asyncio.to_thread(_post_json, url, [log_entry])


class DatadogTelemetryMiddleware(BaseHTTPMiddleware):
    """Intercepta requisições HTTP para contabilizar total, sucesso/erro, latência e logs."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            now_ts = int(time.time())
            path = request.url.path
            method = request.method
            status_class = f"{status_code // 100}xx"
            outcome = "success" if status_code < 400 else "error"
            log_status = (
                "error"
                if status_code >= 500
                else ("warn" if status_code >= 400 else "info")
            )

            tags = [
                f"env:{DD_ENV}",
                f"service:{DD_SERVICE}",
                f"method:{method}",
                f"endpoint:{path}",
                f"status_code:{status_code}",
                f"status_class:{status_class}",
                f"outcome:{outcome}",
            ]

            series: list[dict[str, Any]] = [
                {
                    "metric": "acordos.api.requests.total",
                    "points": [[now_ts, 1]],
                    "type": "count",
                    "tags": tags,
                },
                {
                    "metric": "acordos.api.requests.latency_ms",
                    "points": [[now_ts, duration_ms]],
                    "type": "gauge",
                    "tags": tags,
                },
            ]

            log_payload: dict[str, Any] = {
                "ddsource": "fastapi",
                "ddtags": ",".join(tags),
                "hostname": HOSTNAME,
                "service": DD_SERVICE,
                "status": log_status,
                "message": f"{method} {path} -> {status_code} ({duration_ms}ms)",
                "http": {
                    "method": method,
                    "status_code": status_code,
                    "status_class": status_class,
                    "outcome": outcome,
                    "url_details": {"path": path},
                    "duration_ms": duration_ms,
                },
            }

            asyncio.create_task(send_dd_metrics(series))
            asyncio.create_task(send_dd_log(log_payload))


def _collect_infra_metrics_sync(db_engine: Optional[Engine]) -> list[dict[str, Any]]:
    """Coleta CPU/Memória do Fargate, tamanho do RDS (PostgreSQL) e mensagens nas filas SQS e DLQ."""
    now_ts = int(time.time())
    base_tags = [f"env:{DD_ENV}", f"service:{DD_SERVICE}"]
    series: list[dict[str, Any]] = _collect_ecs_fargate_stats(now_ts, base_tags)

    # 1. Métricas do Banco de Dados RDS PostgreSQL
    if db_engine is not None:
        try:
            with db_engine.connect() as conn:
                db_size_bytes = (
                    conn.execute(
                        text("SELECT pg_database_size(current_database())")
                    ).scalar()
                    or 0
                )
                db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

                active_conns = (
                    conn.execute(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                        )
                    ).scalar()
                    or 0
                )

                series.extend(
                    [
                        {
                            "metric": "acordos.rds.db_size_bytes",
                            "points": [[now_ts, float(db_size_bytes)]],
                            "type": "gauge",
                            "tags": base_tags,
                        },
                        {
                            "metric": "acordos.rds.db_size_mb",
                            "points": [[now_ts, float(db_size_mb)]],
                            "type": "gauge",
                            "tags": base_tags,
                        },
                        {
                            "metric": "acordos.rds.active_connections",
                            "points": [[now_ts, float(active_conns)]],
                            "type": "gauge",
                            "tags": base_tags,
                        },
                    ]
                )

                for table_name in ("autores", "acordos", "documentos"):
                    try:
                        t_size = (
                            conn.execute(
                                text(f"SELECT pg_total_relation_size('{table_name}')")
                            ).scalar()
                            or 0
                        )
                        series.append(
                            {
                                "metric": "acordos.rds.table_size_bytes",
                                "points": [[now_ts, float(t_size)]],
                                "type": "gauge",
                                "tags": base_tags + [f"table:{table_name}"],
                            }
                        )
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("Erro ao coletar métricas do RDS: %s", exc)

    # 2. Métricas das Filas SQS (Fila Principal e DLQ)
    try:
        sqs = boto3.client("sqs", region_name=AWS_REGION)
        queues_to_check = [
            ("main", SQS_MAIN_QUEUE_NAME),
            ("dlq", SQS_DLQ_QUEUE_NAME),
        ]

        for q_type, q_name in queues_to_check:
            if not q_name:
                continue
            try:
                q_url = sqs.get_queue_url(QueueName=q_name)["QueueUrl"]
                attrs = sqs.get_queue_attributes(
                    QueueUrl=q_url,
                    AttributeNames=[
                        "ApproximateNumberOfMessages",
                        "ApproximateNumberOfMessagesNotVisible",
                        "ApproximateNumberOfMessagesDelayed",
                        "RedrivePolicy",
                    ],
                ).get("Attributes", {})

                visible = float(attrs.get("ApproximateNumberOfMessages", 0))
                in_flight = float(attrs.get("ApproximateNumberOfMessagesNotVisible", 0))
                delayed = float(attrs.get("ApproximateNumberOfMessagesDelayed", 0))

                q_tags = base_tags + [f"queue_type:{q_type}", f"queue_name:{q_name}"]
                series.extend(
                    [
                        {
                            "metric": "acordos.sqs.messages_visible",
                            "points": [[now_ts, visible]],
                            "type": "gauge",
                            "tags": q_tags,
                        },
                        {
                            "metric": "acordos.sqs.messages_in_flight",
                            "points": [[now_ts, in_flight]],
                            "type": "gauge",
                            "tags": q_tags,
                        },
                        {
                            "metric": "acordos.sqs.messages_delayed",
                            "points": [[now_ts, delayed]],
                            "type": "gauge",
                            "tags": q_tags,
                        },
                    ]
                )
            except Exception as q_exc:
                logger.debug(
                    "Fila SQS %s não encontrada ou sem permissão: %s", q_name, q_exc
                )
    except Exception as exc:
        logger.debug("Erro ao inicializar cliente SQS: %s", exc)

    return series


async def _infra_metrics_loop(
    db_engine: Optional[Engine], interval_seconds: int = 30
) -> None:
    """Loop em background que envia métricas de SQS/DLQ e RDS a cada 30 segundos."""
    while True:
        api_key = os.getenv("DD_API_KEY", DD_API_KEY).strip()
        if api_key:
            series = await asyncio.to_thread(_collect_infra_metrics_sync, db_engine)
            await send_dd_metrics(series)
        await asyncio.sleep(interval_seconds)


def setup_datadog_telemetry(app: FastAPI, db_engine: Optional[Engine] = None) -> None:
    """Registra o middleware de requisições/logs na aplicação FastAPI."""
    app.add_middleware(DatadogTelemetryMiddleware)
