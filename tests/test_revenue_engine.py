"""Tests for the Revenue Engine — 5-stream automated revenue system."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.revenue_engine import RevenueEngine, RevenueStream, StreamStatus


@pytest.fixture
def rev(tmp_path):
    with patch("backend.core.revenue_engine.REVENUE_DB", tmp_path / "revenue.db"):
        engine = RevenueEngine()
        engine.start()
        yield engine
        engine.stop()


class TestProductManagement:
    def test_add_product(self, rev: RevenueEngine):
        prod = rev.add_product(
            name="AI Writing Tool", stream="micro_saas",
            description="SaaS writing assistant",
        )
        assert prod.id.startswith("prod_")
        assert prod.stream == RevenueStream.MICRO_SAAS
        assert prod.status == StreamStatus.IDEA

    def test_update_status_to_launched(self, rev: RevenueEngine):
        prod = rev.add_product(name="Tool", stream="micro_saas")
        assert rev.update_status(prod.id, "launched") is True
        products = rev.get_products(status="launched")
        assert len(products) == 1
        assert products[0].launched_at is not None

    def test_invalid_stream_raises(self, rev: RevenueEngine):
        with pytest.raises(ValueError):
            rev.add_product(name="Bad", stream="invalid_stream")


class TestRevenueCost:
    def test_record_revenue(self, rev: RevenueEngine):
        prod = rev.add_product(name="Bot", stream="automation_agency")
        rev.record_revenue(prod.id, 1500.0, "Client payment")
        products = rev.get_products()
        assert products[0].monthly_revenue == 1500.0

    def test_record_cost(self, rev: RevenueEngine):
        prod = rev.add_product(name="Bot", stream="automation_agency")
        rev.record_cost(prod.id, 200.0, "Server costs")
        products = rev.get_products()
        assert products[0].monthly_cost == 200.0

    def test_multiple_revenues_accumulate(self, rev: RevenueEngine):
        prod = rev.add_product(name="API", stream="data_products")
        rev.record_revenue(prod.id, 500.0)
        rev.record_revenue(prod.id, 750.0)
        products = rev.get_products()
        assert products[0].monthly_revenue == 1250.0


class TestFinancialSnapshot:
    def test_empty_snapshot(self, rev: RevenueEngine):
        snap = rev.get_financial_snapshot()
        assert snap.total_revenue == 0.0
        assert snap.total_cost == 0.0
        assert snap.profit == 0.0
        assert snap.emergency_mode is False

    def test_snapshot_with_data(self, rev: RevenueEngine):
        p1 = rev.add_product(name="SaaS", stream="micro_saas")
        p2 = rev.add_product(name="Agency", stream="automation_agency")
        rev.record_revenue(p1.id, 5000.0)
        rev.record_revenue(p2.id, 3000.0)
        rev.record_cost(p1.id, 500.0)
        snap = rev.get_financial_snapshot()
        assert snap.total_revenue == 8000.0
        assert snap.total_cost == 500.0
        assert snap.profit == 7500.0

    def test_emergency_mode_triggers(self, rev: RevenueEngine):
        prod = rev.add_product(name="Failing", stream="content_network")
        rev.record_cost(prod.id, 1000.0)
        assert rev.check_emergency_mode() is True


class TestQueries:
    def test_filter_by_stream(self, rev: RevenueEngine):
        rev.add_product(name="A", stream="micro_saas")
        rev.add_product(name="B", stream="ai_consulting")
        results = rev.get_products(stream="micro_saas")
        assert len(results) == 1

    def test_stats(self, rev: RevenueEngine):
        rev.add_product(name="A", stream="micro_saas")
        rev.add_product(name="B", stream="automation_agency")
        stats = rev.stats()
        assert stats["total_products"] == 2
        assert "micro_saas" in stats["streams"]
        assert "targets" in stats
