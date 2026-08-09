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

        # 1. Automatically extract any evt_ attributes into the root JSON payload
        for key, value in getattr(record, "__dict__", {}).items():
            if key.startswith("evt_"):
                clean_key = key[4:]  # Strip 'evt_' prefix
                payload[clean_key] = value

        # 2. Extract operation_Name if passed via evt_ or standard extra attributes
        op_name = (
            getattr(record, "evt_operation_Name", None)
            or getattr(record, "evt_function_name", None)
            or getattr(record, "operation_Name", None)
        )

        if op_name:
            # Setting it on record ensures standard Azure/App Insights handlers read it
            setattr(record, "operation_Name", op_name)
            # Include in JSON payload so it appears at top-level JSON in customDimensions
            payload["operation_Name"] = op_name

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()

    # Prevent duplicate StreamHandlers on stdout while keeping Azure background handlers intact
    has_stdout_handler = any(
        isinstance(h, logging.StreamHandler) and h.stream == sys.stdout
        for h in root.handlers
    )

    if not has_stdout_handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)

    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    msg: str,
    function_name: str | None = None,
    **kwargs: Any,
) -> None:
    """Convenience helper to emit events with automatic evt_ prefixing and operation_Name binding."""
    extra = {f"evt_{k}": v for k, v in kwargs.items()}

    if function_name:
        extra["evt_operation_Name"] = function_name

    logger.log(level, msg, extra=extra)