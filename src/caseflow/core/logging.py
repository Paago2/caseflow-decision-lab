from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

_EXTRA_KEYS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "event",
    "active_model_id",
    "model_registry_dir",
    "error_type",
    "error_message",
    "decision",
    "score",
    "model_id",
    "policy_version",
    "policy_id",
)
_KV_PATTERN = re.compile(
    r"(?P<key>request_id|method|path|status_code|duration_ms)=(?P<value>[^\s]+)"
)
_CONFIGURED_ATTR = "_caseflow_json_logging_configured"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if "request_id" not in payload:
            for match in _KV_PATTERN.finditer(payload["message"]):
                key = match.group("key")
                value = match.group("value")
                if key == "status_code":
                    payload[key] = int(value)
                elif key == "duration_ms":
                    payload[key] = float(value)
                else:
                    payload[key] = value

        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, _CONFIGURED_ATTR, False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    setattr(root_logger, _CONFIGURED_ATTR, True)
