"""
Structured JSON logging — pure Python, no external dependencies.

Provides a JSON formatter for the stdlib logging module and a setup
function to wire it into the root logger.
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional


class StructuredFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    # Fields from the LogRecord that we always include.
    _BASE_FIELDS = ("timestamp", "level", "logger", "message")

    # LogRecord attributes we never want to leak into extra fields.
    _RESERVED = frozenset({
        "name", "msg", "args", "created", "relativeCreated",
        "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "pathname", "filename", "module", "levelno", "levelname",
        "thread", "threadName", "process", "processName", "msecs",
        "message", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # Build the base payload — new dict each call (immutable style).
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        payload = {
            "timestamp": dt.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge any extra fields the caller passed.
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in self._RESERVED:
                continue
            payload[key] = value

        # Include exception info when present.
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Include stack_info if provided.
        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_structured_logging(
    json_mode: bool = False,
    level: int = logging.INFO,
    logger_name: Optional[str] = None,
) -> logging.Logger:
    """Configure structured logging on the specified (or root) logger.

    Parameters
    ----------
    json_mode:
        When ``True``, replaces the default formatter with the JSON
        :class:`StructuredFormatter`. When ``False``, uses a concise
        human-readable format suitable for local development.
    level:
        Minimum log level.
    logger_name:
        Logger name. ``None`` targets the root logger.

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicate output.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if json_mode:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    logger.addHandler(handler)
    return logger
