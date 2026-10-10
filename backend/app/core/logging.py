"""Structured (JSON-lines) logging.

Never pass passwords, tokens or message text into log records.
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                data[key] = value
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str, ensure_ascii=False)


_TICKET_RE = re.compile(r"(ticket=)[^\s&\"']+")


class RedactTicketsFilter(logging.Filter):
    """Uvicorn logs WebSocket request lines with the query string; never keep the auth ticket."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args and isinstance(record.args, tuple):
            record.args = tuple(_TICKET_RE.sub(r"\1[redacted]", a) if isinstance(a, str) else a
                                for a in record.args)
        if isinstance(record.msg, str) and "ticket=" in record.msg:
            record.msg = _TICKET_RE.sub(r"\1[redacted]", record.msg)
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn access logs include query strings; our WS ticket is single-use and short-lived,
    # but keep access logs quiet anyway.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    redact = RedactTicketsFilter()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addFilter(redact)
    handler.addFilter(redact)
