"""Tests for the Digest Engine — report generation and storage."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.digest_engine import DigestEngine, DIGEST_DB


@pytest.fixture
def digest_engine(tmp_path):
    db_path = tmp_path / "test_digests.db"
    with patch("backend.core.digest_engine.DIGEST_DB", db_path):
        engine = DigestEngine()
        engine.start()
        yield engine
        engine.stop()


class TestDigestGeneration:
    @pytest.mark.asyncio
    async def test_generate_daily(self, digest_engine):
        digest = await digest_engine.generate_daily()
        assert digest.id.startswith("digest_")
        assert digest.digest_type == "daily"
        assert "Daily Digest" in digest.title

    @pytest.mark.asyncio
    async def test_generate_weekly(self, digest_engine):
        digest = await digest_engine.generate_weekly()
        assert digest.digest_type == "weekly"
        assert "Weekly" in digest.title

    @pytest.mark.asyncio
    async def test_generate_alert_digest(self, digest_engine):
        alerts = ["Memory count is low", "Agent hermes not responding"]
        digest = await digest_engine.generate_alert_digest(alerts)
        assert digest.digest_type == "alert"
        assert len(digest.highlights) == 2


class TestDigestStorage:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, digest_engine):
        await digest_engine.generate_daily()
        digests = digest_engine.get_digests("daily")
        assert len(digests) == 1

    @pytest.mark.asyncio
    async def test_get_latest(self, digest_engine):
        await digest_engine.generate_daily()
        latest = digest_engine.get_latest("daily")
        assert latest is not None
        assert latest.digest_type == "daily"

    @pytest.mark.asyncio
    async def test_stats(self, digest_engine):
        await digest_engine.generate_daily()
        await digest_engine.generate_weekly()
        stats = digest_engine.stats()
        assert stats["total_digests"] == 2
        assert stats["by_type"]["daily"] == 1
        assert stats["by_type"]["weekly"] == 1
