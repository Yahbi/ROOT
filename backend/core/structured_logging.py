"""
JSON structured logging — configures the stdlib logging module to emit
machine-readable JSON lines on stderr.

This module complements the existing ``structured_logger.py`` by providing
a simpler, opinionated setup function that always outputs JSON.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Every line includes: timestamp, level, logger, message, module,
    funcName, lineno, plus any extra fields attached to the record.
    """

    # LogRecord attributes that are handled explicitly or should never
    # leak into the ``extra`` section of the JSON output.
    _INTERNAL_ATTRS: frozenset[str] = frozenset({
        "name", "msg", "args", "created", "relativeCreated",
        "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "pathname", "filename", "module", "levelno", "levelname",
        "thread", "threadName", "process", "processName", "msecs",
        "message", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON-serialised representation of *record*."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)

        payload: dict[str, Any] = {
            "timestamp": dt.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        # Merge caller-supplied extra fields.
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in self._INTERNAL_ATTRS:
                continue
            payload[key] = value

        # Include exception info when present.
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc_info"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        # Include stack info if provided.
        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure the root logger with :class:`StructuredFormatter` on stderr.

    Parameters
    ----------
    level:
        Minimum log level as a string (e.g. ``"INFO"``, ``"DEBUG"``).
        Invalid values fall back to ``INFO``.
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate output.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setLevel(numeric_level)
    handler.setFormatter(StructuredFormatter())

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper around :func:`logging.getLogger`.

    Returns a logger with the given *name*. Call
    :func:`setup_structured_logging` once at application startup to
    ensure the root logger uses JSON output.
    """
    return logging.getLogger(name)
