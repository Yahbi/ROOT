"""
Prometheus-compatible metrics system — pure Python, no external dependencies.

Supports Counter, Gauge, and Histogram metric types with labels,
thread-safe operations, and Prometheus text exposition format output.
"""

import threading
import time
import math
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Metric value containers
# ---------------------------------------------------------------------------

LabelKey = Tuple[Tuple[str, str], ...]


def _label_key(labels: Optional[Dict[str, str]]) -> LabelKey:
    """Convert a labels dict to a hashable, sorted tuple key."""
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _label_str(key: LabelKey) -> str:
    """Format a label key as Prometheus label string: {k1="v1",k2="v2"}."""
    if not key:
        return ""
    parts = ",".join(f'{k}="{v}"' for k, v in key)
    return "{" + parts + "}"


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, help_text: str, label_names: Tuple[str, ...]) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = label_names
        self._values: Dict[LabelKey, float] = {}
        self._lock = threading.Lock()

    def inc(self, labels: Optional[Dict[str, str]] = None, value: float = 1) -> None:
        if value < 0:
            raise ValueError("Counter value cannot decrease")
        key = _label_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def collect_text(self) -> str:
        lines: List[str] = []
        lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} counter")
        with self._lock:
            snapshot = dict(self._values)
        for key, val in sorted(snapshot.items()):
            lines.append(f"{self.name}{_label_str(key)} {val}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        with self._lock:
            snapshot = dict(self._values)
        return {
            "name": self.name,
            "type": "counter",
            "help": self.help_text,
            "values": [
                {"labels": dict(k), "value": v}
                for k, v in sorted(snapshot.items())
            ],
        }


class Gauge:
    """Value that can go up and down."""

    def __init__(self, name: str, help_text: str, label_names: Tuple[str, ...]) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = label_names
        self._values: Dict[LabelKey, float] = {}
        self._lock = threading.Lock()

    def inc(self, labels: Optional[Dict[str, str]] = None, value: float = 1) -> None:
        key = _label_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def dec(self, labels: Optional[Dict[str, str]] = None, value: float = 1) -> None:
        key = _label_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - value

    def set(self, labels: Optional[Dict[str, str]] = None, value: float = 0) -> None:
        key = _label_key(labels)
        with self._lock:
            self._values[key] = value

    def collect_text(self) -> str:
        lines: List[str] = []
        lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} gauge")
        with self._lock:
            snapshot = dict(self._values)
        for key, val in sorted(snapshot.items()):
            lines.append(f"{self.name}{_label_str(key)} {val}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        with self._lock:
            snapshot = dict(self._values)
        return {
            "name": self.name,
            "type": "gauge",
            "help": self.help_text,
            "values": [
                {"labels": dict(k), "value": v}
                for k, v in sorted(snapshot.items())
            ],
        }


_DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf"))


class Histogram:
    """Tracks value distributions across configurable buckets."""

    def __init__(
        self,
        name: str,
        help_text: str,
        label_names: Tuple[str, ...],
        buckets: Optional[List[float]] = None,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = label_names
        raw = list(buckets) if buckets else list(_DEFAULT_BUCKETS)
        if raw[-1] != float("inf"):
            raw.append(float("inf"))
        self._buckets: Tuple[float, ...] = tuple(sorted(raw))
        # Per label-key: {bucket_bound: count}, plus _sum and _count
        self._bucket_counts: Dict[LabelKey, Dict[float, int]] = {}
        self._sums: Dict[LabelKey, float] = {}
        self._counts: Dict[LabelKey, int] = {}
        self._lock = threading.Lock()

    def _ensure_key(self, key: LabelKey) -> None:
        if key not in self._bucket_counts:
            self._bucket_counts[key] = {b: 0 for b in self._buckets}
            self._sums[key] = 0.0
            self._counts[key] = 0

    def observe(self, labels: Optional[Dict[str, str]] = None, value: float = 0) -> None:
        key = _label_key(labels)
        with self._lock:
            self._ensure_key(key)
            self._sums[key] += value
            self._counts[key] += 1
            for bound in self._buckets:
                if value <= bound:
                    self._bucket_counts[key][bound] += 1

    def collect_text(self) -> str:
        lines: List[str] = []
        lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} histogram")
        with self._lock:
            keys = sorted(self._bucket_counts.keys())
            snapshot = [
                (k, dict(self._bucket_counts[k]), self._sums[k], self._counts[k])
                for k in keys
            ]
        for key, buckets, total_sum, total_count in snapshot:
            label_base = dict(key)
            for bound in self._buckets:
                le_labels = {**label_base, "le": "+Inf" if math.isinf(bound) else str(bound)}
                le_key = _label_key(le_labels)
                lines.append(f"{self.name}_bucket{_label_str(le_key)} {buckets[bound]}")
            sum_lbl = _label_str(key)
            lines.append(f"{self.name}_sum{sum_lbl} {total_sum}")
            lines.append(f"{self.name}_count{sum_lbl} {total_count}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        with self._lock:
            keys = sorted(self._bucket_counts.keys())
            snapshot = [
                (k, dict(self._bucket_counts[k]), self._sums[k], self._counts[k])
                for k in keys
            ]
        values = []
        for key, buckets, total_sum, total_count in snapshot:
            values.append({
                "labels": dict(key),
                "buckets": {
                    ("+Inf" if math.isinf(b) else str(b)): c
                    for b, c in sorted(buckets.items())
                },
                "sum": total_sum,
                "count": total_count,
            })
        return {
            "name": self.name,
            "type": "histogram",
            "help": self.help_text,
            "values": values,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class MetricsRegistry:
    """Thread-safe singleton registry for all metrics."""

    _instance: Optional["MetricsRegistry"] = None
    _init_lock = threading.Lock()

    def __new__(cls) -> "MetricsRegistry":
        with cls._init_lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._metrics: Dict[str, Counter | Gauge | Histogram] = {}
                inst._lock = threading.Lock()
                cls._instance = inst
            return cls._instance

    # -- registration -------------------------------------------------------

    def counter(self, name: str, help_text: str, labels: Tuple[str, ...] = ()) -> Counter:
        with self._lock:
            if name in self._metrics:
                return self._metrics[name]  # type: ignore[return-value]
            metric = Counter(name, help_text, labels)
            self._metrics[name] = metric
            return metric

    def gauge(self, name: str, help_text: str, labels: Tuple[str, ...] = ()) -> Gauge:
        with self._lock:
            if name in self._metrics:
                return self._metrics[name]  # type: ignore[return-value]
            metric = Gauge(name, help_text, labels)
            self._metrics[name] = metric
            return metric

    def histogram(
        self,
        name: str,
        help_text: str,
        labels: Tuple[str, ...] = (),
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        with self._lock:
            if name in self._metrics:
                return self._metrics[name]  # type: ignore[return-value]
            metric = Histogram(name, help_text, labels, buckets)
            self._metrics[name] = metric
            return metric

    # -- convenience mutation methods ---------------------------------------

    def inc(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 1) -> None:
        metric = self._metrics.get(name)
        if metric is None:
            raise KeyError(f"Metric '{name}' not registered")
        if isinstance(metric, (Counter, Gauge)):
            metric.inc(labels, value)
        else:
            raise TypeError(f"inc() not supported on {type(metric).__name__}")

    def dec(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 1) -> None:
        metric = self._metrics.get(name)
        if metric is None:
            raise KeyError(f"Metric '{name}' not registered")
        if isinstance(metric, Gauge):
            metric.dec(labels, value)
        else:
            raise TypeError(f"dec() not supported on {type(metric).__name__}")

    def set(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 0) -> None:
        metric = self._metrics.get(name)
        if metric is None:
            raise KeyError(f"Metric '{name}' not registered")
        if isinstance(metric, Gauge):
            metric.set(labels, value)
        else:
            raise TypeError(f"set() not supported on {type(metric).__name__}")

    def observe(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 0) -> None:
        metric = self._metrics.get(name)
        if metric is None:
            raise KeyError(f"Metric '{name}' not registered")
        if isinstance(metric, Histogram):
            metric.observe(labels, value)
        else:
            raise TypeError(f"observe() not supported on {type(metric).__name__}")

    # -- exposition ----------------------------------------------------------

    def collect(self) -> str:
        with self._lock:
            metrics = list(self._metrics.values())
        blocks = [m.collect_text() for m in metrics]
        return "\n\n".join(blocks) + "\n"

    def to_dict(self) -> Dict:
        with self._lock:
            metrics = list(self._metrics.values())
        return {
            "metrics": [m.to_dict() for m in metrics],
            "collected_at": time.time(),
        }

    # -- testing helper ------------------------------------------------------

    @classmethod
    def _reset(cls) -> None:
        """Reset singleton — only for tests."""
        with cls._init_lock:
            cls._instance = None


# ---------------------------------------------------------------------------
# Default metrics setup
# ---------------------------------------------------------------------------

def setup_default_metrics() -> MetricsRegistry:
    """Register all pre-defined ROOT metrics and return the registry."""
    registry = MetricsRegistry()

    registry.counter(
        "root_llm_requests_total",
        "Total LLM API requests",
        ("model", "tier", "agent"),
    )
    registry.counter(
        "root_llm_tokens_total",
        "Total LLM tokens consumed",
        ("model", "direction"),
    )
    registry.histogram(
        "root_llm_latency_seconds",
        "LLM request latency in seconds",
        ("model", "tier"),
        buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
    )
    registry.counter(
        "root_agent_tasks_total",
        "Total agent tasks executed",
        ("agent_id", "status"),
    )
    registry.gauge(
        "root_memory_count",
        "Current number of stored memories",
    )
    registry.gauge(
        "root_websocket_connections",
        "Current active WebSocket connections",
    )
    registry.counter(
        "root_proactive_actions_total",
        "Total proactive actions executed",
        ("action_name", "status"),
    )
    registry.counter(
        "root_cost_usd_total",
        "Total cost in USD",
        ("model",),
    )
    registry.counter(
        "root_approval_requests_total",
        "Total approval requests",
        ("risk_level", "status"),
    )
    registry.gauge(
        "root_goal_count",
        "Current goal count by status",
        ("status",),
    )

    return registry
