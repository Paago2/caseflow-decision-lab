from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from caseflow.core.settings import get_settings

logger = logging.getLogger(__name__)


class AuditSink(Protocol):
    def emit_decision_event(self, event: dict) -> None: ...


@dataclass
class LogAuditSink:
    def emit_decision_event(self, event: dict) -> None:
        logger.info(
            "decision_event",
            extra={
                "event": "decision_event",
                "request_id": event.get("request_id", ""),
                "model_id": event.get("model_id", ""),
                "decision": event.get("decision", ""),
                "score": event.get("score", 0.0),
            },
        )


@dataclass
class JsonlAuditSink:
    path: Path

    def emit_decision_event(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as sink_file:
            sink_file.write(json.dumps(event, separators=(",", ":")) + "\n")


_audit_sink: AuditSink | None = None


def get_audit_sink() -> AuditSink:
    global _audit_sink
    if _audit_sink is not None:
        return _audit_sink

    settings = get_settings()
    if settings.audit_sink == "jsonl":
        _audit_sink = JsonlAuditSink(path=Path(settings.audit_jsonl_path))
    else:
        _audit_sink = LogAuditSink()

    return _audit_sink


def clear_audit_sink_cache() -> None:
    global _audit_sink
    _audit_sink = None
