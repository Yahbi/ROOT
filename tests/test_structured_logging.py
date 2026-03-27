"""Tests for backend.core.structured_logging — JSON structured log output."""

import json
import logging
import sys

import pytest

from backend.core.structured_logging import (
    StructuredFormatter,
    get_logger,
    setup_structured_logging,
)


# ------------------------------------------------------------------
# StructuredFormatter — JSON output
# ------------------------------------------------------------------


class TestStructuredFormatter:
    @pytest.fixture()
    def formatter(self):
        return StructuredFormatter()

    def _make_record(
        self,
        msg: str = "test message",
        level: int = logging.INFO,
        name: str = "test.logger",
        **extra,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="test_file.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_produces_valid_json(self, formatter):
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_required_fields(self, formatter):
        record = self._make_record()
        parsed = json.loads(formatter.format(record))

        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed
        assert "module" in parsed
        assert "funcName" in parsed
        assert "lineno" in parsed

    def test_message_content(self, formatter):
        record = self._make_record(msg="hello world")
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "hello world"

    def test_level_info(self, formatter):
        record = self._make_record(level=logging.INFO)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "INFO"

    def test_level_warning(self, formatter):
        record = self._make_record(level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "WARNING"

    def test_level_error(self, formatter):
        record = self._make_record(level=logging.ERROR)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "ERROR"

    def test_level_debug(self, formatter):
        record = self._make_record(level=logging.DEBUG)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "DEBUG"

    def test_logger_name(self, formatter):
        record = self._make_record(name="myapp.module")
        parsed = json.loads(formatter.format(record))
        assert parsed["logger"] == "myapp.module"

    def test_lineno(self, formatter):
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert parsed["lineno"] == 42

    def test_timestamp_is_iso_format(self, formatter):
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        ts = parsed["timestamp"]
        # ISO 8601 contains "T" separator and "+00:00" or "Z" for UTC
        assert "T" in ts

    def test_extra_fields_included(self, formatter):
        record = self._make_record(request_id="abc-123", user_id=99)
        parsed = json.loads(formatter.format(record))
        assert parsed["request_id"] == "abc-123"
        assert parsed["user_id"] == 99

    def test_internal_attrs_excluded(self, formatter):
        """Internal LogRecord attributes should NOT appear in JSON output."""
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        # These are internal and should be handled explicitly, not leaked
        for attr in ("args", "exc_info", "exc_text", "stack_info", "msg",
                      "pathname", "thread", "process"):
            assert attr not in parsed

    def test_exception_info_included(self, formatter):
        try:
            raise ValueError("boom")
        except ValueError:
            record = self._make_record()
            record.exc_info = sys.exc_info()

        parsed = json.loads(formatter.format(record))
        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]
        assert "boom" in parsed["exc_info"]

    def test_no_exception_info_when_absent(self, formatter):
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "exc_info" not in parsed

    def test_stack_info_included(self, formatter):
        record = self._make_record()
        record.stack_info = "Stack trace here"
        parsed = json.loads(formatter.format(record))
        assert parsed["stack_info"] == "Stack trace here"

    def test_output_is_single_line(self, formatter):
        record = self._make_record(msg="line one\nline two")
        output = formatter.format(record)
        # json.dumps produces a single line by default (newlines are escaped)
        assert "\n" not in output


# ------------------------------------------------------------------
# get_logger
# ------------------------------------------------------------------


class TestGetLogger:
    def test_returns_logger_instance(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_correct_name(self):
        logger = get_logger("myapp.service")
        assert logger.name == "myapp.service"

    def test_same_name_returns_same_logger(self):
        a = get_logger("same.name")
        b = get_logger("same.name")
        assert a is b


# ------------------------------------------------------------------
# setup_structured_logging
# ------------------------------------------------------------------


class TestSetupStructuredLogging:
    @pytest.fixture(autouse=True)
    def _restore_root_logger(self):
        """Save and restore root logger state to avoid test pollution."""
        root = logging.getLogger()
        original_level = root.level
        original_handlers = list(root.handlers)
        yield
        root.setLevel(original_level)
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in original_handlers:
            root.addHandler(h)

    def test_configures_root_logger_level(self):
        setup_structured_logging(level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_adds_stream_handler_to_stderr(self):
        setup_structured_logging(level="INFO")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr

    def test_handler_uses_structured_formatter(self):
        setup_structured_logging(level="INFO")
        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)

    def test_removes_existing_handlers(self):
        root = logging.getLogger()
        dummy = logging.StreamHandler()
        root.addHandler(dummy)
        assert dummy in root.handlers

        setup_structured_logging(level="INFO")
        assert dummy not in root.handlers
        assert len(root.handlers) == 1

    def test_invalid_level_falls_back_to_info(self):
        setup_structured_logging(level="NONSENSE")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_produces_json_output(self, capsys):
        setup_structured_logging(level="WARNING")
        logger = logging.getLogger("test.json.output")
        logger.warning("check json")

        captured = capsys.readouterr()
        # Output goes to stderr
        parsed = json.loads(captured.err.strip())
        assert parsed["message"] == "check json"
        assert parsed["level"] == "WARNING"
