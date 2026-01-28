"""Tests for competitor tracking functionality."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.core.competitors import (
    CompetitorOffer,
    CompetitorSnapshot,
    CompetitorTracker,
    CompetitorTrend,
)


class TestCompetitorOffer:
    """Tests for CompetitorOffer dataclass."""

    def test_landed_price(self):
        """Test landed price calculation."""
        offer = CompetitorOffer(
            price=Decimal("10.00"),
            shipping=Decimal("3.99"),
        )
        assert offer.landed_price == Decimal("13.99")

    def test_landed_price_free_shipping(self):
        """Test landed price with free shipping."""
        offer = CompetitorOffer(
            price=Decimal("25.00"),
            shipping=Decimal("0"),
        )
        assert offer.landed_price == Decimal("25.00")


class TestCompetitorSnapshot:
    """Tests for CompetitorSnapshot."""

    def test_analyze_empty(self):
        """Test analyzing empty snapshot."""
        snapshot = CompetitorSnapshot(asin="B001234567")
        snapshot.analyze()
        
        assert snapshot.total_offers == 0
        assert snapshot.fba_offers == 0
        assert snapshot.amazon_present is False

    def test_analyze_with_offers(self):
        """Test analyzing snapshot with offers."""
        offers = [
            CompetitorOffer(
                seller_id="S1",
                seller_name="Seller 1",
                is_fba=True,
                is_amazon=False,
                price=Decimal("20.00"),
                shipping=Decimal("0"),
                is_buy_box=True,
            ),
            CompetitorOffer(
                seller_id="S2",
                seller_name="Seller 2",
                is_fba=False,
                is_amazon=False,
                price=Decimal("18.00"),
                shipping=Decimal("3.00"),
            ),
            CompetitorOffer(
                seller_id="AMAZON",
                seller_name="Amazon",
                is_fba=True,
                is_amazon=True,
                price=Decimal("22.00"),
                shipping=Decimal("0"),
            ),
        ]

        snapshot = CompetitorSnapshot(asin="B001234567", offers=offers)
        snapshot.analyze()

        assert snapshot.total_offers == 3
        assert snapshot.fba_offers == 2
        assert snapshot.fbm_offers == 1
        assert snapshot.amazon_present is True
        assert snapshot.buy_box_price == Decimal("20.00")
        assert snapshot.buy_box_seller == "Seller 1"
        assert snapshot.lowest_price == Decimal("20.00")
        assert snapshot.lowest_fba_price == Decimal("20.00")
        assert snapshot.lowest_fbm_price == Decimal("21.00")


class TestCompetitorTrend:
    """Tests for CompetitorTrend."""

    def test_analyze_insufficient_data(self):
        """Test trend analysis with insufficient data."""
        trend = CompetitorTrend(asin="B001234567", snapshots=[])
        trend.analyze()
        
        assert trend.avg_total_offers == 0.0
        assert trend.offer_count_trend == ""

    def test_analyze_rising_trend(self):
        """Test detecting rising offer count trend."""
        snapshots = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i in range(6):
            snapshot = CompetitorSnapshot(
                asin="B001234567",
                snapshot_time=base_time + timedelta(days=i),
                total_offers=5 + i * 2,  # 5, 7, 9, 11, 13, 15
            )
            snapshots.append(snapshot)

        trend = CompetitorTrend(asin="B001234567", snapshots=snapshots)
        trend.analyze()

        assert trend.offer_count_trend == "rising"

    def test_analyze_falling_trend(self):
        """Test detecting falling offer count trend."""
        snapshots = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i in range(6):
            snapshot = CompetitorSnapshot(
                asin="B001234567",
                snapshot_time=base_time + timedelta(days=i),
                total_offers=15 - i * 2,  # 15, 13, 11, 9, 7, 5
            )
            snapshots.append(snapshot)

        trend = CompetitorTrend(asin="B001234567", snapshots=snapshots)
        trend.analyze()

        assert trend.offer_count_trend == "falling"

    def test_analyze_stable_trend(self):
        """Test detecting stable offer count trend."""
        snapshots = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i in range(6):
            snapshot = CompetitorSnapshot(
                asin="B001234567",
                snapshot_time=base_time + timedelta(days=i),
                total_offers=10,  # Constant
            )
            snapshots.append(snapshot)

        trend = CompetitorTrend(asin="B001234567", snapshots=snapshots)
        trend.analyze()

        assert trend.offer_count_trend == "stable"


class TestCompetitorTracker:
    """Tests for CompetitorTracker."""

    def test_add_and_get_snapshot(self):
        """Test adding and retrieving snapshots."""
        tracker = CompetitorTracker()
        
        snapshot = CompetitorSnapshot(asin="B001234567")
        tracker.add_snapshot(snapshot)

        retrieved = tracker.get_latest_snapshot("B001234567")
        assert retrieved is not None
        assert retrieved.asin == "B001234567"

    def test_get_nonexistent_snapshot(self):
        """Test getting snapshot for unknown ASIN."""
        tracker = CompetitorTracker()
        
        result = tracker.get_latest_snapshot("NONEXISTENT")
        assert result is None

    def test_get_all_asins(self):
        """Test getting all tracked ASINs."""
        tracker = CompetitorTracker()
        
        tracker.add_snapshot(CompetitorSnapshot(asin="B001"))
        tracker.add_snapshot(CompetitorSnapshot(asin="B002"))
        tracker.add_snapshot(CompetitorSnapshot(asin="B003"))

        asins = tracker.get_all_asins()
        assert set(asins) == {"B001", "B002", "B003"}

    def test_clear_asin(self):
        """Test clearing data for a specific ASIN."""
        tracker = CompetitorTracker()
        
        tracker.add_snapshot(CompetitorSnapshot(asin="B001"))
        tracker.add_snapshot(CompetitorSnapshot(asin="B002"))
        
        tracker.clear_asin("B001")

        assert tracker.get_latest_snapshot("B001") is None
        assert tracker.get_latest_snapshot("B002") is not None

    def test_clear_all(self):
        """Test clearing all data."""
        tracker = CompetitorTracker()
        
        tracker.add_snapshot(CompetitorSnapshot(asin="B001"))
        tracker.add_snapshot(CompetitorSnapshot(asin="B002"))
        
        tracker.clear_all()

        assert len(tracker.get_all_asins()) == 0

    def test_get_trend(self):
        """Test getting trend analysis."""
        tracker = CompetitorTracker()
        
        for i in range(5):
            snapshot = CompetitorSnapshot(
                asin="B001",
                snapshot_time=datetime.now() - timedelta(days=4-i),
                total_offers=10 + i,
            )
            tracker.add_snapshot(snapshot)

        trend = tracker.get_trend("B001", days=7)
        assert trend.asin == "B001"
        assert len(trend.snapshots) == 5

    def test_parse_keepa_offers(self):
        """Test parsing Keepa offer data."""
        keepa_data = {
            "offers": [
                {
                    "sellerId": "SELLER1",
                    "sellerName": "Test Seller",
                    "isFBA": True,
                    "isAmazon": False,
                    "price": 1999,  # Cents
                    "shipping": 0,
                    "condition": "New",
                    "isBuyBox": True,
                },
                {
                    "sellerId": "SELLER2",
                    "sellerName": "Another Seller",
                    "isFBA": False,
                    "isAmazon": False,
                    "price": 1799,
                    "shipping": 299,
                },
            ]
        }

        offers = CompetitorTracker.parse_keepa_offers(keepa_data)
        
        assert len(offers) == 2
        assert offers[0].seller_id == "SELLER1"
        assert offers[0].price == Decimal("19.99")
        assert offers[0].is_fba is True
        assert offers[1].shipping == Decimal("2.99")

    def test_create_snapshot_from_keepa(self):
        """Test creating snapshot from Keepa data."""
        tracker = CompetitorTracker()
        
        keepa_data = {
            "offers": [
                {
                    "sellerId": "S1",
                    "sellerName": "Seller",
                    "isFBA": True,
                    "price": 2000,
                    "shipping": 0,
                    "isBuyBox": True,
                },
            ]
        }

        snapshot = tracker.create_snapshot_from_keepa("B001234567", keepa_data)
        
        assert snapshot.asin == "B001234567"
        assert snapshot.total_offers == 1
        assert snapshot.buy_box_price == Decimal("20.00")
