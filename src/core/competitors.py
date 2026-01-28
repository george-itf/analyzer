"""Competitor tracking for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompetitorOffer:
    """A single competitor offer on an ASIN."""

    seller_id: str = ""
    seller_name: str = ""
    is_fba: bool = False
    is_amazon: bool = False
    price: Decimal = Decimal("0")
    shipping: Decimal = Decimal("0")
    total_price: Decimal = Decimal("0")
    condition: str = "New"
    rating: float | None = None
    rating_count: int | None = None
    is_buy_box: bool = False
    snapshot_time: datetime = field(default_factory=datetime.now)

    @property
    def landed_price(self) -> Decimal:
        """Get the total landed price (price + shipping)."""
        return self.price + self.shipping


@dataclass
class CompetitorSnapshot:
    """Snapshot of all competitors on an ASIN at a point in time."""

    asin: str = ""
    snapshot_time: datetime = field(default_factory=datetime.now)
    offers: list[CompetitorOffer] = field(default_factory=list)
    total_offers: int = 0
    fba_offers: int = 0
    fbm_offers: int = 0
    amazon_present: bool = False
    buy_box_price: Decimal | None = None
    buy_box_seller: str = ""
    lowest_price: Decimal | None = None
    lowest_fba_price: Decimal | None = None
    lowest_fbm_price: Decimal | None = None

    def analyze(self) -> None:
        """Analyze the offers and populate summary fields."""
        if not self.offers:
            return

        self.total_offers = len(self.offers)
        self.fba_offers = sum(1 for o in self.offers if o.is_fba)
        self.fbm_offers = sum(1 for o in self.offers if not o.is_fba)
        self.amazon_present = any(o.is_amazon for o in self.offers)

        # Find buy box
        buy_box = next((o for o in self.offers if o.is_buy_box), None)
        if buy_box:
            self.buy_box_price = buy_box.landed_price
            self.buy_box_seller = buy_box.seller_name

        # Find lowest prices
        all_prices = [o.landed_price for o in self.offers if o.landed_price > 0]
        fba_prices = [o.landed_price for o in self.offers if o.is_fba and o.landed_price > 0]
        fbm_prices = [o.landed_price for o in self.offers if not o.is_fba and o.landed_price > 0]

        if all_prices:
            self.lowest_price = min(all_prices)
        if fba_prices:
            self.lowest_fba_price = min(fba_prices)
        if fbm_prices:
            self.lowest_fbm_price = min(fbm_prices)


@dataclass
class CompetitorTrend:
    """Trend analysis for competitors over time."""

    asin: str = ""
    period_days: int = 7
    snapshots: list[CompetitorSnapshot] = field(default_factory=list)

    # Computed trends
    avg_total_offers: float = 0.0
    offer_count_trend: str = ""  # "rising", "stable", "falling"
    avg_buy_box_price: Decimal | None = None
    price_volatility: float = 0.0  # Coefficient of variation
    amazon_presence_pct: float = 0.0
    new_sellers_count: int = 0
    left_sellers_count: int = 0

    def analyze(self) -> None:
        """Analyze trends across snapshots."""
        if len(self.snapshots) < 2:
            return

        # Sort by time
        sorted_snapshots = sorted(self.snapshots, key=lambda s: s.snapshot_time)

        # Calculate averages
        offer_counts = [s.total_offers for s in sorted_snapshots]
        self.avg_total_offers = sum(offer_counts) / len(offer_counts)

        # Determine trend
        first_half = offer_counts[: len(offer_counts) // 2]
        second_half = offer_counts[len(offer_counts) // 2 :]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        if avg_second > avg_first * 1.1:
            self.offer_count_trend = "rising"
        elif avg_second < avg_first * 0.9:
            self.offer_count_trend = "falling"
        else:
            self.offer_count_trend = "stable"

        # Buy box price analysis
        buy_box_prices = [s.buy_box_price for s in sorted_snapshots if s.buy_box_price]
        if buy_box_prices:
            self.avg_buy_box_price = sum(buy_box_prices) / len(buy_box_prices)

            # Calculate volatility (coefficient of variation)
            if self.avg_buy_box_price > 0:
                variance = sum((p - self.avg_buy_box_price) ** 2 for p in buy_box_prices) / len(buy_box_prices)
                std_dev = variance ** Decimal("0.5")
                self.price_volatility = float(std_dev / self.avg_buy_box_price)

        # Amazon presence percentage
        amazon_present_count = sum(1 for s in sorted_snapshots if s.amazon_present)
        self.amazon_presence_pct = amazon_present_count / len(sorted_snapshots) * 100

        # Track seller churn
        if len(sorted_snapshots) >= 2:
            first_sellers = {o.seller_id for o in sorted_snapshots[0].offers}
            last_sellers = {o.seller_id for o in sorted_snapshots[-1].offers}

            self.new_sellers_count = len(last_sellers - first_sellers)
            self.left_sellers_count = len(first_sellers - last_sellers)


class CompetitorTracker:
    """Tracks competitors for ASINs over time."""

    def __init__(self) -> None:
        self._snapshots: dict[str, list[CompetitorSnapshot]] = {}  # asin -> list of snapshots

    def add_snapshot(self, snapshot: CompetitorSnapshot) -> None:
        """Add a competitor snapshot for an ASIN."""
        snapshot.analyze()
        if snapshot.asin not in self._snapshots:
            self._snapshots[snapshot.asin] = []
        self._snapshots[snapshot.asin].append(snapshot)

        # Keep only last 100 snapshots per ASIN
        if len(self._snapshots[snapshot.asin]) > 100:
            self._snapshots[snapshot.asin] = self._snapshots[snapshot.asin][-100:]

    def get_latest_snapshot(self, asin: str) -> CompetitorSnapshot | None:
        """Get the most recent snapshot for an ASIN."""
        snapshots = self._snapshots.get(asin, [])
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.snapshot_time)

    def get_trend(self, asin: str, days: int = 7) -> CompetitorTrend:
        """Get competitor trend analysis for an ASIN."""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        snapshots = self._snapshots.get(asin, [])
        recent = [s for s in snapshots if s.snapshot_time >= cutoff]

        trend = CompetitorTrend(asin=asin, period_days=days, snapshots=recent)
        trend.analyze()
        return trend

    def get_all_asins(self) -> list[str]:
        """Get all tracked ASINs."""
        return list(self._snapshots.keys())

    def clear_asin(self, asin: str) -> None:
        """Clear all snapshots for an ASIN."""
        self._snapshots.pop(asin, None)

    def clear_all(self) -> None:
        """Clear all tracked data."""
        self._snapshots.clear()

    @staticmethod
    def parse_keepa_offers(keepa_data: dict) -> list[CompetitorOffer]:
        """Parse competitor offers from Keepa product data.
        
        Keepa offers are in the 'offers' array with seller info.
        """
        offers = []
        
        for offer_data in keepa_data.get("offers", []):
            try:
                offer = CompetitorOffer(
                    seller_id=offer_data.get("sellerId", ""),
                    seller_name=offer_data.get("sellerName", ""),
                    is_fba=offer_data.get("isFBA", False),
                    is_amazon=offer_data.get("isAmazon", False),
                    price=Decimal(str(offer_data.get("price", 0))) / 100,  # Keepa uses cents
                    shipping=Decimal(str(offer_data.get("shipping", 0))) / 100,
                    condition=offer_data.get("condition", "New"),
                    rating=offer_data.get("sellerRating"),
                    rating_count=offer_data.get("sellerRatingCount"),
                    is_buy_box=offer_data.get("isBuyBox", False),
                )
                offer.total_price = offer.price + offer.shipping
                offers.append(offer)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Failed to parse offer: {e}")
                continue

        return offers

    def create_snapshot_from_keepa(self, asin: str, keepa_data: dict) -> CompetitorSnapshot:
        """Create a competitor snapshot from Keepa product data."""
        offers = self.parse_keepa_offers(keepa_data)

        snapshot = CompetitorSnapshot(
            asin=asin,
            snapshot_time=datetime.now(),
            offers=offers,
        )
        snapshot.analyze()

        return snapshot
