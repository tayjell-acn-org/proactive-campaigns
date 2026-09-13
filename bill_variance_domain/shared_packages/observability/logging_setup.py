"""Structured JSON logging helper for consistent, queryable log events."""
from __future__ import annotations

import json
import logging
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
    logging.getLogger().setLevel(level)

    noisy_loggers = [
        "azure",
        "azure.core",
        "azure.cosmos",
        "azure.servicebus",
        "uamqp",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)



def log_event(
    logger: logging.Logger,
    level: int,
    msg: str,
    **fields: Any,
) -> None:
    context = " | ".join(
        f"{key}={value}"
        for key, value in fields.items()
        if value is not None
    )

    message = f"{msg} | {context}" if context else msg

    logger.log(level, message)