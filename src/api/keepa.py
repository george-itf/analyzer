"""Keepa API client with token management."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests

from src.core.config import Settings
from src.core.models import KeepaSnapshot, TokenStatus


# Keepa domain codes
KEEPA_DOMAIN_UK = 2  # amazon.co.uk

# Keepa price type indices
KEEPA_PRICE_AMAZON = 0
KEEPA_PRICE_NEW = 1
KEEPA_PRICE_USED = 2
KEEPA_PRICE_NEW_FBM = 7  # New 3rd party FBM shipping
KEEPA_PRICE_BUY_BOX = 18


@dataclass
class KeepaResponse:
    """Response from Keepa API."""

    success: bool = False
    products: list[dict] = field(default_factory=list)
    token_status: TokenStatus = field(default_factory=TokenStatus)
    error_message: str = ""
    raw_json: str = ""


class KeepaClient:
    """Keepa API client with token-aware rate limiting."""

    BASE_URL = "https://api.keepa.com"

    def __init__(self, settings: Settings) -> None:
        """Initialize the Keepa client."""
        self.settings = settings
        self.api_key = settings.api.keepa_api_key
        self.mock_mode = settings.api.mock_mode

        # Session with keep-alive
        self.session = requests.Session()
        self.session.headers.update({
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

        # Token state
        self._token_status = TokenStatus()
        self._last_request_time: float = 0

    @property
    def token_status(self) -> TokenStatus:
        """Get the current token status."""
        return self._token_status

    def _update_token_status(self, response_data: dict) -> None:
        """Update token status from API response."""
        self._token_status = TokenStatus(
            tokens_left=response_data.get("tokensLeft", 0),
            refill_rate=response_data.get("refillRate", 20),
            refill_in_seconds=response_data.get("refillIn", 60),
            tokens_consumed_last=response_data.get("tokensConsumed", 0),
            token_flow_reduction=response_data.get("tokenFlowReduction", 0.0),
            last_updated=datetime.now(),
        )

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any],
        timeout: int = 30,
    ) -> tuple[dict, int]:
        """Make a request to the Keepa API.

        Returns tuple of (response_data, status_code).
        """
        if self.mock_mode:
            return self._mock_response(endpoint, params), 200

        params["key"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"

        start_time = time.time()
        response = self.session.get(url, params=params, timeout=timeout)
        duration_ms = int((time.time() - start_time) * 1000)

        self._last_request_time = time.time()

        if response.status_code == 200:
            data = response.json()
            self._update_token_status(data)
            return data, response.status_code

        if response.status_code == 429:
            # Rate limited - parse refill time from response
            try:
                data = response.json()
                self._update_token_status(data)
            except Exception:
                pass
            raise KeepaRateLimitError(
                f"Rate limited. Retry in {self._token_status.refill_in_seconds}s"
            )

        response.raise_for_status()
        return {}, response.status_code

    def _mock_response(self, endpoint: str, params: dict) -> dict:
        """Generate a mock response for testing."""
        from src.utils.mock_data import get_mock_keepa_response
        return get_mock_keepa_response(params.get("asin", "").split(","))

    def can_make_request(self, tokens_needed: int = 1) -> bool:
        """Check if we have enough tokens for a request.
        
        Returns True if we haven't made any requests yet (token count unknown)
        or if we have enough tokens.
        """
        # If we haven't made any requests yet, assume we can (API will tell us if not)
        if self._token_status.last_updated is None:
            return True
        return self._token_status.tokens_left >= tokens_needed

    def wait_for_tokens(self, tokens_needed: int = 1) -> float:
        """Calculate wait time until enough tokens are available.

        Returns wait time in seconds, or 0 if tokens available now.
        """
        if self.can_make_request(tokens_needed):
            return 0.0

        # Estimate wait time based on refill rate
        tokens_deficit = tokens_needed - self._token_status.tokens_left
        if self._token_status.refill_rate > 0:
            refill_cycles = tokens_deficit / self._token_status.refill_rate
            wait_seconds = refill_cycles * self._token_status.refill_in_seconds
            return max(wait_seconds, 0.0)

        return float(self._token_status.refill_in_seconds)

    def get_products(
        self,
        asins: list[str],
        days: int = 90,
        include_buy_box: bool = False,
    ) -> KeepaResponse:
        """Fetch product data for ASINs.

        Args:
            asins: List of ASINs to fetch (max 100 per request)
            days: Number of days of history to include
            include_buy_box: Whether to include buy box data (costs more tokens)

        Returns:
            KeepaResponse with product data and token status
        """
        if not asins:
            return KeepaResponse(success=True, products=[])

        # Keepa allows up to 100 ASINs per request
        asins = asins[:100]

        # Build stats parameter
        # Format: days (90), out-of-stock percentage, demand
        stats = f"{days},1,1"

        params = {
            "domain": KEEPA_DOMAIN_UK,
            "asin": ",".join(asins),
            "stats": stats,
            "offers": 20,  # Number of offers to include
        }

        # Buy box data costs more tokens
        if include_buy_box:
            params["buybox"] = 1

        try:
            data, status = self._make_request("product", params)
        except KeepaRateLimitError:
            return KeepaResponse(
                success=False,
                error_message="Rate limited",
                token_status=self._token_status,
            )
        except Exception as e:
            return KeepaResponse(
                success=False,
                error_message=str(e),
                token_status=self._token_status,
            )

        products = data.get("products", [])

        return KeepaResponse(
            success=True,
            products=products,
            token_status=self._token_status,
            raw_json=json.dumps(data),
        )

    def parse_product_to_snapshot(self, product: dict) -> KeepaSnapshot:
        """Parse a Keepa product response into a KeepaSnapshot.

        Note: Product title is available via get_product_title() method
        to update ASIN candidates separately.
        """
        asin = product.get("asin", "")

        # Parse price data
        csv = product.get("csv", [])
        stats = product.get("stats", {})

        # FBM pricing (index 7 in csv array)
        fbm_price_current = None
        fbm_prices = []

        if csv and len(csv) > KEEPA_PRICE_NEW_FBM:
            fbm_data = csv[KEEPA_PRICE_NEW_FBM]
            if fbm_data:
                # Keepa prices are in cents, convert to pounds
                prices = [p / 100 for i, p in enumerate(fbm_data) if i % 2 == 1 and p > 0]
                if prices:
                    fbm_price_current = Decimal(str(prices[-1]))
                    fbm_prices = prices

        # Calculate 30d stats from stats object or prices
        fbm_price_median = None
        fbm_price_mean = None
        fbm_price_min = None
        fbm_price_max = None
        price_volatility_cv = None

        # Check stats object first
        if stats:
            current_stats = stats.get("current", [])
            avg_stats = stats.get("avg30", [])
            min_stats = stats.get("min30", [])
            max_stats = stats.get("max30", [])

            # Index 7 is NEW_FBM
            if len(avg_stats) > KEEPA_PRICE_NEW_FBM and avg_stats[KEEPA_PRICE_NEW_FBM]:
                fbm_price_mean = Decimal(str(avg_stats[KEEPA_PRICE_NEW_FBM] / 100))
            if len(min_stats) > KEEPA_PRICE_NEW_FBM and min_stats[KEEPA_PRICE_NEW_FBM]:
                fbm_price_min = Decimal(str(min_stats[KEEPA_PRICE_NEW_FBM] / 100))
            if len(max_stats) > KEEPA_PRICE_NEW_FBM and max_stats[KEEPA_PRICE_NEW_FBM]:
                fbm_price_max = Decimal(str(max_stats[KEEPA_PRICE_NEW_FBM] / 100))

        # Calculate median from prices if we have data
        if fbm_prices:
            fbm_price_median = Decimal(str(statistics.median(fbm_prices)))
            if len(fbm_prices) > 1:
                mean = statistics.mean(fbm_prices)
                if mean > 0:
                    stdev = statistics.stdev(fbm_prices)
                    price_volatility_cv = Decimal(str(stdev / mean))

        # Sales rank drops (from stats or calculated)
        sales_rank_drops = None
        sales_rank_current = None

        if stats:
            drops_30 = stats.get("salesRankDrops30", [])
            if drops_30 and len(drops_30) > 0:
                sales_rank_drops = drops_30[0] if drops_30[0] else None

            current_rank = stats.get("current", [])
            # Sales rank is typically at index 3 in current array
            if current_rank and len(current_rank) > 3 and current_rank[3]:
                sales_rank_current = current_rank[3]

        # Offer counts
        offer_count_fbm = None
        offer_count_fba = None
        offer_count_trend = ""

        live_offers = product.get("liveOffersOrder", [])
        offers = product.get("offers", [])

        if live_offers:
            # Count FBM vs FBA offers
            fbm_count = 0
            fba_count = 0
            for offer_id in live_offers:
                for offer in offers:
                    if offer.get("offerId") == offer_id:
                        if offer.get("isFBA"):
                            fba_count += 1
                        else:
                            fbm_count += 1
                        break
            offer_count_fbm = fbm_count
            offer_count_fba = fba_count

        # Determine offer trend from history (simplified)
        offer_counts = product.get("offerCountNew", [])
        if offer_counts and len(offer_counts) >= 4:
            recent = offer_counts[-2:]  # Last 2 data points
            older = offer_counts[-4:-2]  # Previous 2 data points
            recent_avg = sum(r for i, r in enumerate(recent) if i % 2 == 1) / max(len(recent) // 2, 1)
            older_avg = sum(r for i, r in enumerate(older) if i % 2 == 1) / max(len(older) // 2, 1)
            if recent_avg > older_avg * 1.2:
                offer_count_trend = "rising"
            elif recent_avg < older_avg * 0.8:
                offer_count_trend = "falling"
            else:
                offer_count_trend = "stable"

        # Buy box data
        buy_box_price = None
        buy_box_is_fba = None
        buy_box_is_amazon = None

        buybox_data = product.get("buyBoxSellerIdHistory", [])
        if buybox_data:
            # Check if Amazon is in buy box (seller ID 'A' prefix is Amazon)
            last_seller = buybox_data[-1] if len(buybox_data) > 1 else None
            if last_seller and isinstance(last_seller, str):
                buy_box_is_amazon = last_seller.startswith("A")

        if csv and len(csv) > KEEPA_PRICE_BUY_BOX:
            bb_data = csv[KEEPA_PRICE_BUY_BOX]
            if bb_data:
                prices = [p / 100 for i, p in enumerate(bb_data) if i % 2 == 1 and p > 0]
                if prices:
                    buy_box_price = Decimal(str(prices[-1]))

        # Amazon presence
        amazon_on_listing = False
        if csv and len(csv) > KEEPA_PRICE_AMAZON:
            amazon_data = csv[KEEPA_PRICE_AMAZON]
            if amazon_data:
                # Check if Amazon has recent pricing (not -1)
                recent_prices = [p for i, p in enumerate(amazon_data[-10:]) if i % 2 == 1]
                amazon_on_listing = any(p > 0 for p in recent_prices)

        return KeepaSnapshot(
            asin=asin,
            snapshot_time=datetime.now(),
            fbm_price_current=fbm_price_current,
            fbm_price_median_30d=fbm_price_median or fbm_price_mean,
            fbm_price_mean_30d=fbm_price_mean,
            fbm_price_min_30d=fbm_price_min,
            fbm_price_max_30d=fbm_price_max,
            sales_rank_drops_30d=sales_rank_drops,
            sales_rank_current=sales_rank_current,
            offer_count_fbm=offer_count_fbm,
            offer_count_fba=offer_count_fba,
            offer_count_trend=offer_count_trend,
            buy_box_price=buy_box_price,
            buy_box_is_fba=buy_box_is_fba,
            buy_box_is_amazon=buy_box_is_amazon,
            amazon_on_listing=amazon_on_listing,
            price_volatility_cv=price_volatility_cv,
            tokens_consumed=self._token_status.tokens_consumed_last,
            raw_json=json.dumps(product),
        )

    def fetch_and_parse(
        self,
        asins: list[str],
        days: int = 90,
        include_buy_box: bool = False,
    ) -> tuple[list[KeepaSnapshot], KeepaResponse]:
        """Fetch product data and parse to snapshots.

        Returns tuple of (snapshots, response).
        """
        response = self.get_products(asins, days=days, include_buy_box=include_buy_box)

        if not response.success:
            return [], response

        snapshots = []
        for product in response.products:
            try:
                snapshot = self.parse_product_to_snapshot(product)
                snapshots.append(snapshot)
            except Exception as e:
                # Log but continue with other products
                continue

        return snapshots, response

    @staticmethod
    def get_product_title(product: dict) -> str:
        """Extract product title from Keepa product data.

        Keepa stores the title in the 'title' field of the product object.
        """
        return product.get("title", "")

    @staticmethod
    def get_product_brand(product: dict) -> str:
        """Extract product brand from Keepa product data."""
        return product.get("brand", "")


class KeepaRateLimitError(Exception):
    """Raised when Keepa rate limit is hit."""

    pass
