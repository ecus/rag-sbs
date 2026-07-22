"""Logging estructurado JSON con correlation ID por request (RNF-016).

- Cada log sale como una línea JSON (timestamp, level, logger, msg, request_id, …).
- El request_id se propaga por un contextvar, así todos los logs de un mismo
  request comparten el mismo ID (trazabilidad punta a punta).
- Queda en los logs de Docker (almacenamiento local) y se envía a Loki.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar

# Correlation ID del request en curso (vacío fuera de un request)
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    """Formatea cada registro de log como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        # Atributos extra pasados via logger.x(..., extra={...})
        for k, v in getattr(record, "__dict__", {}).items():
            if k in ("method", "path", "status_code", "latency_ms", "client_ip",
                     "alias", "trace_id"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configurar_logging() -> None:
    """Configura el root logger con salida JSON a stdout.

    Idempotente: reemplaza handlers previos para no duplicar líneas.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(level)
    # Limpiar handlers previos (uvicorn/streamlit pueden haber puesto los suyos)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # Alinear los loggers de uvicorn/gunicorn al mismo formato
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
