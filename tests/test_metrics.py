"""Tests for backend.core.metrics — Counter, Gauge, Histogram, MetricsRegistry."""

from __future__ import annotations

import math
import threading

import pytest

from backend.core.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    _label_key,
    _label_str,
)


# ── Helper function tests ──────────────────────────────────────


def test_label_key_none():
    assert _label_key(None) == ()


def test_label_key_empty():
    assert _label_key({}) == ()


def test_label_key_sorted():
    result = _label_key({"b": "2", "a": "1"})
    assert result == (("a", "1"), ("b", "2"))


def test_label_str_empty():
    assert _label_str(()) == ""


def test_label_str_formats():
    key = (("method", "GET"), ("path", "/api"))
    assert _label_str(key) == '{method="GET",path="/api"}'


# ── Counter Tests ───────────────────────────────────────────────


class TestCounter:
    def test_basic_increment(self):
        c = Counter("req_total", "Total requests", ())
        c.inc()
        c.inc()
        c.inc(value=3)
        data = c.to_dict()
        assert data["values"][0]["value"] == 5.0

    def test_increment_with_labels(self):
        c = Counter("req_total", "Total requests", ("method",))
        c.inc(labels={"method": "GET"})
        c.inc(labels={"method": "POST"}, value=2)
        c.inc(labels={"method": "GET"}, value=3)

        data = c.to_dict()
        values_by_label = {
            tuple(v["labels"].items()): v["value"] for v in data["values"]
        }
        assert values_by_label[(("method", "GET"),)] == 4.0
        assert values_by_label[(("method", "POST"),)] == 2.0

    def test_negative_increment_raises(self):
        c = Counter("bad", "Bad counter", ())
        with pytest.raises(ValueError, match="cannot decrease"):
            c.inc(value=-1)

    def test_collect_text_format(self):
        c = Counter("http_total", "HTTP requests", ())
        c.inc(value=42)
        text = c.collect_text()
        assert "# HELP http_total HTTP requests" in text
        assert "# TYPE http_total counter" in text
        assert "http_total 42" in text

    def test_to_dict_structure(self):
        c = Counter("test_c", "Test", ())
        c.inc(value=10)
        d = c.to_dict()
        assert d["name"] == "test_c"
        assert d["type"] == "counter"
        assert d["help"] == "Test"
        assert len(d["values"]) == 1


# ── Gauge Tests ─────────────────────────────────────────────────


class TestGauge:
    def test_set(self):
        g = Gauge("temp", "Temperature", ())
        g.set(value=37.5)
        data = g.to_dict()
        assert data["values"][0]["value"] == 37.5

    def test_inc(self):
        g = Gauge("conn", "Connections", ())
        g.inc()
        g.inc(value=4)
        data = g.to_dict()
        assert data["values"][0]["value"] == 5.0

    def test_dec(self):
        g = Gauge("conn", "Connections", ())
        g.set(value=10)
        g.dec(value=3)
        data = g.to_dict()
        assert data["values"][0]["value"] == 7.0

    def test_inc_dec_with_labels(self):
        g = Gauge("queue", "Queue size", ("name",))
        g.inc(labels={"name": "a"}, value=5)
        g.dec(labels={"name": "a"}, value=2)
        g.inc(labels={"name": "b"}, value=10)

        data = g.to_dict()
        values_by_label = {
            tuple(v["labels"].items()): v["value"] for v in data["values"]
        }
        assert values_by_label[(("name", "a"),)] == 3.0
        assert values_by_label[(("name", "b"),)] == 10.0

    def test_collect_text_format(self):
        g = Gauge("ws_conn", "WebSocket connections", ())
        g.set(value=5)
        text = g.collect_text()
        assert "# TYPE ws_conn gauge" in text
        assert "ws_conn 5" in text


# ── Histogram Tests ─────────────────────────────────────────────


class TestHistogram:
    def test_observe_basic(self):
        h = Histogram("latency", "Latency", (), buckets=[0.1, 0.5, 1.0])
        h.observe(value=0.3)
        h.observe(value=0.7)
        h.observe(value=0.05)

        data = h.to_dict()
        assert data["values"][0]["count"] == 3
        assert data["values"][0]["sum"] == pytest.approx(1.05)

    def test_bucket_counts(self):
        h = Histogram("dur", "Duration", (), buckets=[1.0, 5.0, 10.0])
        h.observe(value=0.5)   # fits in 1.0, 5.0, 10.0, +Inf
        h.observe(value=3.0)   # fits in 5.0, 10.0, +Inf
        h.observe(value=7.0)   # fits in 10.0, +Inf
        h.observe(value=15.0)  # fits in +Inf only

        data = h.to_dict()
        buckets = data["values"][0]["buckets"]
        assert buckets["1.0"] == 1
        assert buckets["5.0"] == 2
        assert buckets["10.0"] == 3
        assert buckets["+Inf"] == 4

    def test_inf_bucket_always_added(self):
        h = Histogram("test_h", "Test", (), buckets=[1.0, 5.0])
        # +Inf should be auto-appended
        assert h._buckets[-1] == float("inf")

    def test_observe_with_labels(self):
        h = Histogram("req_dur", "Request duration", ("method",), buckets=[0.5, 1.0])
        h.observe(labels={"method": "GET"}, value=0.3)
        h.observe(labels={"method": "POST"}, value=0.8)

        data = h.to_dict()
        assert len(data["values"]) == 2

    def test_collect_text_format(self):
        h = Histogram("lat", "Latency", (), buckets=[0.5, 1.0])
        h.observe(value=0.3)
        text = h.collect_text()
        assert "# TYPE lat histogram" in text
        assert "lat_bucket" in text
        assert "lat_sum" in text
        assert "lat_count" in text

    def test_to_dict_structure(self):
        h = Histogram("h_test", "Help", (), buckets=[1.0])
        h.observe(value=0.5)
        d = h.to_dict()
        assert d["name"] == "h_test"
        assert d["type"] == "histogram"
        assert "buckets" in d["values"][0]
        assert "sum" in d["values"][0]
        assert "count" in d["values"][0]


# ── MetricsRegistry Tests ──────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset singleton before each test."""
    MetricsRegistry._reset()
    yield
    MetricsRegistry._reset()


class TestMetricsRegistry:
    def test_singleton(self):
        r1 = MetricsRegistry()
        r2 = MetricsRegistry()
        assert r1 is r2

    def test_register_counter(self):
        reg = MetricsRegistry()
        c = reg.counter("test_counter", "A test counter")
        assert isinstance(c, Counter)

    def test_register_gauge(self):
        reg = MetricsRegistry()
        g = reg.gauge("test_gauge", "A test gauge")
        assert isinstance(g, Gauge)

    def test_register_histogram(self):
        reg = MetricsRegistry()
        h = reg.histogram("test_hist", "A test histogram", buckets=[1.0, 5.0])
        assert isinstance(h, Histogram)

    def test_duplicate_registration_returns_same(self):
        reg = MetricsRegistry()
        c1 = reg.counter("dup", "first")
        c2 = reg.counter("dup", "second")
        assert c1 is c2

    def test_inc_counter_via_registry(self):
        reg = MetricsRegistry()
        reg.counter("rc", "counter")
        reg.inc("rc", value=5)
        data = reg.to_dict()
        metric = next(m for m in data["metrics"] if m["name"] == "rc")
        assert metric["values"][0]["value"] == 5.0

    def test_inc_gauge_via_registry(self):
        reg = MetricsRegistry()
        reg.gauge("rg", "gauge")
        reg.inc("rg", value=3)
        reg.dec("rg", value=1)
        data = reg.to_dict()
        metric = next(m for m in data["metrics"] if m["name"] == "rg")
        assert metric["values"][0]["value"] == 2.0

    def test_set_gauge_via_registry(self):
        reg = MetricsRegistry()
        reg.gauge("sg", "gauge")
        reg.set("sg", value=42)
        data = reg.to_dict()
        metric = next(m for m in data["metrics"] if m["name"] == "sg")
        assert metric["values"][0]["value"] == 42.0

    def test_observe_histogram_via_registry(self):
        reg = MetricsRegistry()
        reg.histogram("oh", "histogram", buckets=[1.0])
        reg.observe("oh", value=0.5)
        data = reg.to_dict()
        metric = next(m for m in data["metrics"] if m["name"] == "oh")
        assert metric["values"][0]["count"] == 1

    def test_inc_nonexistent_raises(self):
        reg = MetricsRegistry()
        with pytest.raises(KeyError):
            reg.inc("nonexistent")

    def test_dec_on_counter_raises(self):
        reg = MetricsRegistry()
        reg.counter("c_no_dec", "counter")
        with pytest.raises(TypeError):
            reg.dec("c_no_dec")

    def test_set_on_counter_raises(self):
        reg = MetricsRegistry()
        reg.counter("c_no_set", "counter")
        with pytest.raises(TypeError):
            reg.set("c_no_set", value=5)

    def test_observe_on_counter_raises(self):
        reg = MetricsRegistry()
        reg.counter("c_no_obs", "counter")
        with pytest.raises(TypeError):
            reg.observe("c_no_obs", value=1)

    def test_collect_prometheus_format(self):
        reg = MetricsRegistry()
        reg.counter("prom_counter", "A counter")
        reg.inc("prom_counter", value=10)

        text = reg.collect()
        assert "# HELP prom_counter A counter" in text
        assert "# TYPE prom_counter counter" in text
        assert "prom_counter 10" in text

    def test_to_dict_contains_collected_at(self):
        reg = MetricsRegistry()
        reg.counter("ts_test", "timestamp test")
        data = reg.to_dict()
        assert "collected_at" in data
        assert "metrics" in data


class TestMetricsThreadSafety:
    """Verify concurrent increments are safe."""

    def test_concurrent_counter_increments(self):
        reg = MetricsRegistry()
        c = reg.counter("thread_counter", "Thread-safe counter")
        num_threads = 10
        increments_per_thread = 1000

        def worker():
            for _ in range(increments_per_thread):
                c.inc()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        data = c.to_dict()
        assert data["values"][0]["value"] == num_threads * increments_per_thread

    def test_concurrent_gauge_operations(self):
        reg = MetricsRegistry()
        g = reg.gauge("thread_gauge", "Thread-safe gauge")
        g.set(value=0)

        num_threads = 10
        ops_per_thread = 500

        def worker():
            for _ in range(ops_per_thread):
                g.inc()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        data = g.to_dict()
        assert data["values"][0]["value"] == num_threads * ops_per_thread
