from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from threading import Lock

from fastapi import FastAPI, Request

_HISTOGRAM_BUCKETS = [
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
]


@dataclass
class _HistogramSeries:
    bucket_counts: list[int] = field(
        default_factory=lambda: [0] * len(_HISTOGRAM_BUCKETS)
    )
    total_count: int = 0
    total_sum: float = 0.0


class _MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: dict[tuple[str, str, str], int] = {}
        self._duration_histograms: dict[tuple[str, str], _HistogramSeries] = {}
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._ms_summaries: dict[str, tuple[int, float]] = {}

    def observe_request(
        self, *, method: str, path: str, status: str, duration_seconds: float
    ) -> None:
        request_key = (method, path, status)
        hist_key = (method, path)

        with self._lock:
            self._request_counts[request_key] = (
                self._request_counts.get(request_key, 0) + 1
            )

            series = self._duration_histograms.get(hist_key)
            if series is None:
                series = _HistogramSeries()
                self._duration_histograms[hist_key] = series

            series.total_count += 1
            series.total_sum += duration_seconds

            for index, bound in enumerate(_HISTOGRAM_BUCKETS):
                if duration_seconds <= bound:
                    series.bucket_counts[index] += 1

    def render_prometheus_text(self) -> str:
        lines: list[str] = [
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]

        with self._lock:
            for (method, path, status), count in sorted(self._request_counts.items()):
                lines.append(
                    "http_requests_total{"
                    f'method="{method}",path="{path}",status="{status}"'
                    f"}} {count}"
                )

            lines.append(
                "# HELP http_request_duration_seconds HTTP request duration in seconds"
            )
            lines.append("# TYPE http_request_duration_seconds histogram")

            for (method, path), series in sorted(self._duration_histograms.items()):
                cumulative = 0
                for index, bound in enumerate(_HISTOGRAM_BUCKETS):
                    cumulative += series.bucket_counts[index]
                    lines.append(
                        "http_request_duration_seconds_bucket{"
                        f'method="{method}",path="{path}",le="{bound:g}"'
                        f"}} {cumulative}"
                    )

                lines.append(
                    "http_request_duration_seconds_bucket{"
                    f'method="{method}",path="{path}",le="+Inf"'
                    f"}} {series.total_count}"
                )
                lines.append(
                    "http_request_duration_seconds_sum{"
                    f'method="{method}",path="{path}"'
                    f"}} {series.total_sum}"
                )
                lines.append(
                    "http_request_duration_seconds_count{"
                    f'method="{method}",path="{path}"'
                    f"}} {series.total_count}"
                )

            if self._counters:
                lines.append("# TYPE caseflow_counter_total counter")
                for name, value in sorted(self._counters.items()):
                    lines.append(f"{name} {value}")

            if self._ms_summaries:
                lines.append("# TYPE caseflow_ms_summary summary")
                for name, (count, total_ms) in sorted(self._ms_summaries.items()):
                    lines.append(f"{name}_count {count}")
                    lines.append(f"{name}_sum {total_ms}")

            if self._gauges:
                lines.append("# TYPE caseflow_gauge gauge")
                for name, value in sorted(self._gauges.items()):
                    lines.append(f"{name} {value}")

        lines.append("")
        return "\n".join(lines)

    def clear(self) -> None:
        with self._lock:
            self._request_counts.clear()
            self._duration_histograms.clear()
            self._counters.clear()
            self._gauges.clear()
            self._ms_summaries.clear()

    def increment(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def observe_ms(self, name: str, value_ms: float) -> None:
        with self._lock:
            count, total = self._ms_summaries.get(name, (0, 0.0))
            self._ms_summaries[name] = (count + 1, total + value_ms)


_metrics_store = _MetricsStore()


def render_metrics_text() -> str:
    return _metrics_store.render_prometheus_text()


def clear_metrics() -> None:
    _metrics_store.clear()


def increment_metric(name: str, value: float = 1.0) -> None:
    _metrics_store.increment(name, value)


def set_gauge_metric(name: str, value: float) -> None:
    _metrics_store.set_gauge(name, value)


def observe_ms_metric(name: str, value_ms: float) -> None:
    _metrics_store.observe_ms(name, value_ms)


def install_metrics_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        method = request.method
        path = request.url.path
        started_at = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - started_at
        if math.isfinite(duration):
            _metrics_store.observe_request(
                method=method,
                path=path,
                status=str(response.status_code),
                duration_seconds=duration,
            )

        return response
