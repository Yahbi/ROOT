"""Extended tests for Revenue Engine — financial calculations, auto-remediate, transactions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.core.revenue_engine import (
    RevenueEngine,
    RevenueProduct,
    RevenueStream,
    StreamStatus,
    FinancialSnapshot,
    STREAM_TARGETS,
)


@pytest.fixture
def rev(tmp_path):
    with patch("backend.core.revenue_engine.REVENUE_DB", tmp_path / "revenue.db"):
        engine = RevenueEngine()
        engine.start()
        yield engine
        engine.stop()


# ── RevenueStream Enum ────────────────────────────────────────────────


class TestRevenueStreamEnum:
    def test_all_streams_exist(self):
        assert RevenueStream.AUTOMATION_AGENCY == "automation_agency"
        assert RevenueStream.MICRO_SAAS == "micro_saas"
        assert RevenueStream.CONTENT_NETWORK == "content_network"
        assert RevenueStream.DATA_PRODUCTS == "data_products"
        assert RevenueStream.AI_CONSULTING == "ai_consulting"

    def test_stream_targets_defined_for_all(self):
        for stream in RevenueStream:
            assert stream in STREAM_TARGETS
            low, high = STREAM_TARGETS[stream]
            assert low > 0
            assert high > low


# ── StreamStatus Enum ─────────────────────────────────────────────────


class TestStreamStatusEnum:
    def test_all_statuses_exist(self):
        assert StreamStatus.IDEA == "idea"
        assert StreamStatus.BUILDING == "building"
        assert StreamStatus.LAUNCHED == "launched"
        assert StreamStatus.EARNING == "earning"
        assert StreamStatus.PAUSED == "paused"


# ── Product Lifecycle ─────────────────────────────────────────────────


class TestProductLifecycle:
    def test_add_product_all_streams(self, rev: RevenueEngine):
        for stream in RevenueStream:
            prod = rev.add_product(name=f"Product for {stream.value}", stream=stream.value)
            assert prod.stream == stream
            assert prod.status == StreamStatus.IDEA

    def test_status_transitions(self, rev: RevenueEngine):
        prod = rev.add_product(name="Lifecycle Product", stream="micro_saas")
        for status in ("building", "launched", "earning", "paused"):
            result = rev.update_status(prod.id, status)
            assert result is True

    def test_invalid_status_raises(self, rev: RevenueEngine):
        prod = rev.add_product(name="Error Test", stream="micro_saas")
        with pytest.raises(ValueError):
            rev.update_status(prod.id, "nonexistent_status")

    def test_product_id_format(self, rev: RevenueEngine):
        prod = rev.add_product(name="ID Test", stream="data_products")
        assert prod.id.startswith("prod_")

    def test_duplicate_name_stream_is_idempotent(self, rev: RevenueEngine):
        rev.add_product(name="Unique Tool", stream="micro_saas")
        rev.add_product(name="Unique Tool", stream="micro_saas")
        products = rev.get_products(stream="micro_saas")
        # INSERT OR IGNORE means second call is silently dropped
        assert len(products) == 1

    def test_same_name_different_stream_allowed(self, rev: RevenueEngine):
        rev.add_product(name="Multi Tool", stream="micro_saas")
        rev.add_product(name="Multi Tool", stream="ai_consulting")
        all_products = rev.get_products()
        assert len(all_products) == 2


# ── Revenue/Cost Calculations ─────────────────────────────────────────


class TestFinancialCalculations:
    def test_profit_calculation_correct(self, rev: RevenueEngine):
        prod = rev.add_product(name="Profitable SaaS", stream="micro_saas")
        rev.record_revenue(prod.id, 5000.0)
        rev.record_cost(prod.id, 800.0)
        snap = rev.get_financial_snapshot()
        assert snap.profit == pytest.approx(4200.0, abs=0.01)

    def test_negative_profit_triggers_emergency(self, rev: RevenueEngine):
        prod = rev.add_product(name="Loss Maker", stream="automation_agency")
        rev.record_cost(prod.id, 2000.0)
        rev.record_revenue(prod.id, 100.0)
        snap = rev.get_financial_snapshot()
        assert snap.emergency_mode is True
        assert snap.profit < 0

    def test_no_activity_no_emergency(self, rev: RevenueEngine):
        rev.add_product(name="Dormant", stream="content_network")
        snap = rev.get_financial_snapshot()
        assert snap.emergency_mode is False

    def test_by_stream_breakdown(self, rev: RevenueEngine):
        p1 = rev.add_product(name="SaaS A", stream="micro_saas")
        p2 = rev.add_product(name="Agency B", stream="automation_agency")
        rev.record_revenue(p1.id, 3000.0)
        rev.record_revenue(p2.id, 1000.0)
        snap = rev.get_financial_snapshot()
        assert snap.by_stream["micro_saas"] == pytest.approx(3000.0, abs=0.01)
        assert snap.by_stream["automation_agency"] == pytest.approx(1000.0, abs=0.01)

    def test_cost_subtracted_in_stream_breakdown(self, rev: RevenueEngine):
        prod = rev.add_product(name="Net SaaS", stream="micro_saas")
        rev.record_revenue(prod.id, 5000.0)
        rev.record_cost(prod.id, 1500.0)
        snap = rev.get_financial_snapshot()
        assert snap.by_stream["micro_saas"] == pytest.approx(3500.0, abs=0.01)

    def test_paused_products_excluded_from_snapshot(self, rev: RevenueEngine):
        prod = rev.add_product(name="Paused SaaS", stream="micro_saas")
        rev.record_revenue(prod.id, 5000.0)
        rev.update_status(prod.id, "paused")
        snap = rev.get_financial_snapshot()
        assert snap.total_revenue == 0.0

    def test_multiple_revenue_transactions(self, rev: RevenueEngine):
        prod = rev.add_product(name="Multi Rev", stream="data_products")
        for amount in [100.0, 200.0, 300.0, 400.0]:
            rev.record_revenue(prod.id, amount)
        products = rev.get_products()
        assert products[0].monthly_revenue == pytest.approx(1000.0, abs=0.01)

    def test_abs_value_for_negative_cost(self, rev: RevenueEngine):
        """record_cost uses abs() — negative amounts treated as positive."""
        prod = rev.add_product(name="Neg Cost", stream="micro_saas")
        rev.record_cost(prod.id, -500.0)  # negative input
        products = rev.get_products()
        assert products[0].monthly_cost == pytest.approx(500.0, abs=0.01)


# ── Auto-Remediate ────────────────────────────────────────────────────


class TestAutoRemediate:
    def test_no_emergency_returns_early(self, rev: RevenueEngine):
        prod = rev.add_product(name="Healthy", stream="micro_saas")
        rev.record_revenue(prod.id, 10000.0)
        result = rev.auto_remediate()
        assert result["emergency"] is False
        assert result["paused"] == []

    def test_emergency_remediation_runs(self, rev: RevenueEngine):
        prod = rev.add_product(name="Bleeding", stream="automation_agency")
        rev.record_cost(prod.id, 5000.0)
        result = rev.auto_remediate()
        assert result["emergency"] is True


# ── Queries ───────────────────────────────────────────────────────────


class TestRevenueQueries:
    def test_get_products_with_status_filter(self, rev: RevenueEngine):
        p1 = rev.add_product(name="Building SaaS", stream="micro_saas")
        p2 = rev.add_product(name="Launched SaaS", stream="micro_saas")
        rev.update_status(p2.id, "launched")
        launched = rev.get_products(status="launched")
        assert all(p.status == StreamStatus.LAUNCHED for p in launched)

    def test_get_products_respects_limit(self, rev: RevenueEngine):
        for i in range(10):
            rev.add_product(name=f"Product {i}", stream="micro_saas")
        results = rev.get_products(limit=3)
        assert len(results) <= 3

    def test_stats_includes_stream_info(self, rev: RevenueEngine):
        rev.add_product(name="A", stream="micro_saas")
        rev.add_product(name="B", stream="micro_saas")
        rev.add_product(name="C", stream="ai_consulting")
        stats = rev.stats()
        assert stats["total_products"] == 3
        assert "micro_saas" in stats["streams"]
        assert stats["streams"]["micro_saas"]["products"] == 2
        assert "targets" in stats


# ── Interest Engine Gate ──────────────────────────────────────────────


class TestInterestGate:
    def test_blocked_product_returns_blocked_id(self, rev: RevenueEngine):
        interest = MagicMock()
        interest.gate.return_value = (False, "Not aligned with Yohan's goals")
        rev.set_interest_engine(interest)

        prod = rev.add_product(name="Blocked Tool", stream="micro_saas")
        assert prod.id == "blocked"
        assert prod.status == StreamStatus.PAUSED

    def test_allowed_product_proceeds_normally(self, rev: RevenueEngine):
        interest = MagicMock()
        interest.gate.return_value = (True, "Aligned")
        rev.set_interest_engine(interest)

        prod = rev.add_product(name="Allowed Tool", stream="micro_saas")
        assert prod.id != "blocked"
        assert prod.id.startswith("prod_")
