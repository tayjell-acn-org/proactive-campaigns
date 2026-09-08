"""Structured JSON logging helper for consistent, queryable log events."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in getattr(record, "__dict__", {}).items():
            if key.startswith("evt_"):
                payload[key[4:]] = value

        op_name = (
            getattr(record, "evt_operation_Name", None)
            or getattr(record, "evt_function_name", None)
            or getattr(record, "operation_Name", None)
        )

        if op_name:
            setattr(record, "operation_Name", op_name)
            payload["operation_Name"] = op_name

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()

    has_stdout_handler = any(
        isinstance(h, logging.StreamHandler)
        and getattr(h, "stream", None) == sys.stdout
        for h in root.handlers
    )

    if not has_stdout_handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)

    root.setLevel(level)

    # Suppress Azure SDK noise
    noisy_loggers = [
        "azure",
        "azure.core",
        "azure.cosmos",
        "azure.servicebus",
        "uamqp",
        "azure.core.pipeline",
        "azure.core.pipeline.policies",
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.cosmos.cosmos_client",
        "azure.cosmos.http_logging_policy",
        "azure.messaging.servicebus",
        "azure.servicebus._base_handler",
    ]

    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False

    # Optional: completely disable HTTP request/response dumps
    logging.getLogger(
        "azure.core.pipeline.policies.http_logging_policy"
    ).disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    msg: str,
    function_name: str | None = None,
    **kwargs: Any,
) -> None:
    extra = {f"evt_{k}": v for k, v in kwargs.items()}

    if function_name:
        extra["evt_operation_Name"] = function_name

    logger.log(level, msg, extra=extra)