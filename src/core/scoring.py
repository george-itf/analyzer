"""Scoring engine for Seller Opportunity Scanner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from .models import (
    AsinCandidate,
    Brand,
    KeepaSnapshot,
    ProfitScenario,
    ScoreBreakdown,
    ScoreFlag,
    ScoreResult,
    SpApiSnapshot,
    SupplierItem,
)
from .shipping import ShippingCalculator, ShippingTier

if TYPE_CHECKING:
    from .config import BrandSettings, Settings


class ScoringEngine:
    """Calculates opportunity scores for ASIN candidates."""

    # Score normalization constants
    SALES_PROXY_MAX = 200  # Normalize sales proxy to 0-100
    PROFIT_MAX_GBP = Decimal("50")  # Profit at which score maxes out
    MARGIN_MAX = Decimal("0.50")  # Margin at which score maxes out
    OFFER_COUNT_HIGH = 20  # Threshold for "high" offer count
    VOLATILITY_HIGH = Decimal("0.30")  # CV threshold for "volatile" pricing

    def __init__(self, settings: Settings) -> None:
        """Initialize the scoring engine."""
        self.settings = settings
        self.shipping_calculator = ShippingCalculator(settings)

    def calculate_profit_scenario(
        self,
        scenario_name: str,
        cost_ex_vat: Decimal,
        sell_gross_safe: Decimal,
        fees_gross: Decimal | None,
        shipping_cost: Decimal,
        vat_rate: Decimal,
    ) -> ProfitScenario:
        """Calculate profit for a single cost scenario."""
        # Convert sell price to ex-VAT
        sell_net = sell_gross_safe / (1 + vat_rate)

        # Convert fees to ex-VAT (assume fees are VAT-inclusive)
        fees_net = (fees_gross or Decimal("0")) / (1 + vat_rate)

        # Calculate profit
        profit_net = sell_net - cost_ex_vat - fees_net - shipping_cost

        # Calculate margin
        margin_net = profit_net / sell_net if sell_net > 0 else Decimal("0")

        return ProfitScenario(
            scenario_name=scenario_name,
            cost_ex_vat=cost_ex_vat,
            sell_gross_safe=sell_gross_safe,
            sell_net=sell_net,
            fees_gross=fees_gross or Decimal("0"),
            fees_net=fees_net,
            shipping_cost=shipping_cost,
            profit_net=profit_net,
            margin_net=margin_net,
            is_profitable=profit_net > 0,
        )

    def calculate_sell_gross_safe(
        self,
        fbm_price_now: Decimal | None,
        fbm_price_median_30d: Decimal | None,
        safe_price_buffer_pct: Decimal,
    ) -> Decimal:
        """Calculate the safe sell price (conservative estimate)."""
        if fbm_price_now is None and fbm_price_median_30d is None:
            return Decimal("0")

        prices = [p for p in [fbm_price_now, fbm_price_median_30d] if p is not None and p > 0]
        if not prices:
            return Decimal("0")

        # Use minimum of current and median, with buffer
        min_price = min(prices)
        return min_price * (1 - safe_price_buffer_pct)

    def normalize_velocity(self, sales_proxy_30d: int | None) -> Decimal:
        """Normalize sales velocity to 0-100 score."""
        if sales_proxy_30d is None or sales_proxy_30d <= 0:
            return Decimal("0")

        # Linear scale up to max, capped at 100
        raw_score = (sales_proxy_30d / self.SALES_PROXY_MAX) * 100
        return min(Decimal(str(raw_score)), Decimal("100"))

    def normalize_profit(self, profit_net: Decimal) -> Decimal:
        """Normalize profit to 0-100 score."""
        if profit_net <= 0:
            return Decimal("0")

        # Linear scale up to max, capped at 100
        raw_score = (profit_net / self.PROFIT_MAX_GBP) * 100
        return min(raw_score, Decimal("100"))

    def normalize_margin(self, margin_net: Decimal) -> Decimal:
        """Normalize margin to 0-100 score."""
        if margin_net <= 0:
            return Decimal("0")

        # Linear scale up to max, capped at 100
        raw_score = (margin_net / self.MARGIN_MAX) * 100
        return min(raw_score, Decimal("100"))

    def normalize_stability(
        self, volatility_cv: Decimal | None, offer_count_trend: str
    ) -> Decimal:
        """Normalize price stability to 0-100 score."""
        score = Decimal("70")  # Start at neutral-good

        # Penalize high volatility
        if volatility_cv is not None:
            if volatility_cv > self.VOLATILITY_HIGH:
                score -= Decimal("30")
            elif volatility_cv > Decimal("0.15"):
                score -= Decimal("15")

        # Penalize rising competition
        if offer_count_trend == "rising":
            score -= Decimal("20")
        elif offer_count_trend == "falling":
            score += Decimal("15")

        return max(min(score, Decimal("100")), Decimal("0"))

    def normalize_viability(
        self, fbm_price: Decimal | None, buy_box_price: Decimal | None
    ) -> Decimal:
        """Normalize FBM viability (vs buy box) to 0-100 score."""
        if fbm_price is None or buy_box_price is None or buy_box_price <= 0:
            return Decimal("50")  # Neutral if no data

        # Calculate gap percentage
        gap_pct = (fbm_price - buy_box_price) / buy_box_price

        # Close to buy box = good, far from = bad
        if gap_pct <= Decimal("0.05"):
            return Decimal("100")
        elif gap_pct <= Decimal("0.10"):
            return Decimal("80")
        elif gap_pct <= Decimal("0.15"):
            return Decimal("60")
        elif gap_pct <= Decimal("0.25"):
            return Decimal("40")
        else:
            return Decimal("20")

    def apply_penalties(
        self,
        brand_settings: BrandSettings,
        is_restricted: bool,
        amazon_present: bool,
        weight_tier: ShippingTier,
        mapping_confidence: Decimal,
        offer_count: int | None,
        offer_count_trend: str,
        sales_proxy_30d: int | None,
        margin_net: Decimal,
        profit_net: Decimal,
    ) -> tuple[Decimal, list[ScoreFlag]]:
        """Calculate total penalties and generate flags."""
        total_penalty = Decimal("0")
        flags: list[ScoreFlag] = []
        penalties = brand_settings.penalties

        # Restriction penalty
        if is_restricted:
            total_penalty += penalties.restricted
            flags.append(
                ScoreFlag(
                    code="RESTRICTED",
                    description="Account restricted from selling this ASIN",
                    penalty=penalties.restricted,
                    is_critical=penalties.restricted >= 100,
                )
            )

        # Amazon retail presence
        if amazon_present:
            total_penalty += penalties.amazon_retail_present
            flags.append(
                ScoreFlag(
                    code="AMAZON_RETAIL",
                    description="Amazon is selling this product",
                    penalty=penalties.amazon_retail_present,
                    is_critical=False,
                )
            )

        # Weight penalties
        if weight_tier == ShippingTier.UNKNOWN:
            total_penalty += penalties.weight_unknown
            flags.append(
                ScoreFlag(
                    code="WEIGHT_UNKNOWN",
                    description="Product weight not available",
                    penalty=penalties.weight_unknown,
                    is_critical=False,
                )
            )
        elif weight_tier == ShippingTier.OVERWEIGHT:
            total_penalty += penalties.overweight
            flags.append(
                ScoreFlag(
                    code="OVERWEIGHT",
                    description="Product exceeds 20kg shipping limit",
                    penalty=penalties.overweight,
                    is_critical=True,
                )
            )

        # Low mapping confidence
        if mapping_confidence < Decimal("0.7"):
            total_penalty += penalties.low_mapping_confidence
            flags.append(
                ScoreFlag(
                    code="LOW_CONFIDENCE",
                    description=f"Low ASIN mapping confidence ({mapping_confidence:.0%})",
                    penalty=penalties.low_mapping_confidence,
                    is_critical=False,
                )
            )

        # High offer count
        if offer_count is not None and offer_count > self.OFFER_COUNT_HIGH:
            total_penalty += penalties.high_offer_count
            flags.append(
                ScoreFlag(
                    code="HIGH_COMPETITION",
                    description=f"High number of competing offers ({offer_count})",
                    penalty=penalties.high_offer_count,
                    is_critical=False,
                )
            )

        # Rising competition
        if offer_count_trend == "rising":
            total_penalty += penalties.offer_count_rising
            flags.append(
                ScoreFlag(
                    code="RISING_COMPETITION",
                    description="Competition is increasing",
                    penalty=penalties.offer_count_rising,
                    is_critical=False,
                )
            )

        # Below minimum thresholds
        if sales_proxy_30d is not None and sales_proxy_30d < brand_settings.min_sales_proxy_30d:
            total_penalty += penalties.below_min_sales
            flags.append(
                ScoreFlag(
                    code="LOW_SALES",
                    description=f"Sales below threshold ({sales_proxy_30d} < {brand_settings.min_sales_proxy_30d})",
                    penalty=penalties.below_min_sales,
                    is_critical=False,
                )
            )

        if margin_net < brand_settings.min_margin_ex_vat:
            total_penalty += penalties.below_min_margin
            flags.append(
                ScoreFlag(
                    code="LOW_MARGIN",
                    description=f"Margin below threshold ({margin_net:.1%} < {brand_settings.min_margin_ex_vat:.1%})",
                    penalty=penalties.below_min_margin,
                    is_critical=False,
                )
            )

        if profit_net < brand_settings.min_profit_ex_vat_gbp:
            total_penalty += penalties.below_min_profit
            flags.append(
                ScoreFlag(
                    code="LOW_PROFIT",
                    description=f"Profit below threshold ({profit_net:.2f} < {brand_settings.min_profit_ex_vat_gbp})",
                    penalty=penalties.below_min_profit,
                    is_critical=False,
                )
            )

        return total_penalty, flags

    def calculate(
        self,
        item: SupplierItem,
        candidate: AsinCandidate,
        keepa: KeepaSnapshot | None,
        spapi: SpApiSnapshot | None,
    ) -> ScoreResult:
        """Calculate the full opportunity score for a candidate."""
        brand_settings = self.settings.get_brand_settings(item.brand.value)
        vat_rate = self.settings.get_effective_vat_rate(item.brand.value)

        # Calculate sell price
        fbm_price_now = keepa.fbm_price_current if keepa else None
        fbm_price_median = keepa.fbm_price_median_30d if keepa else None
        sell_gross_safe = self.calculate_sell_gross_safe(
            fbm_price_now, fbm_price_median, brand_settings.safe_price_buffer_pct
        )

        # Get shipping cost
        weight_kg = spapi.weight_kg if spapi else None
        shipping_result = self.shipping_calculator.calculate(weight_kg)
        shipping_cost = shipping_result.cost_gbp

        # Get fees
        fees_gross = spapi.fee_total_gross if spapi else None

        # Calculate both scenarios
        scenario_1 = self.calculate_profit_scenario(
            "cost_1",
            item.cost_per_unit_ex_vat_1,
            sell_gross_safe,
            fees_gross,
            shipping_cost,
            vat_rate,
        )

        scenario_5 = self.calculate_profit_scenario(
            "cost_5plus",
            item.cost_per_unit_ex_vat_5plus,
            sell_gross_safe,
            fees_gross,
            shipping_cost,
            vat_rate,
        )

        # Determine winning scenario (higher profit)
        if scenario_5.profit_net >= scenario_1.profit_net:
            winning_scenario = scenario_5
            winning_name = "cost_5plus"
        else:
            winning_scenario = scenario_1
            winning_name = "cost_1"

        # Calculate sub-scores
        sales_proxy = keepa.sales_rank_drops_30d if keepa else None
        velocity_raw = self.normalize_velocity(sales_proxy)

        profit_raw = self.normalize_profit(winning_scenario.profit_net)
        margin_raw = self.normalize_margin(winning_scenario.margin_net)

        volatility_cv = keepa.price_volatility_cv if keepa else None
        offer_trend = keepa.offer_count_trend if keepa else ""
        stability_raw = self.normalize_stability(volatility_cv, offer_trend)

        buy_box = keepa.buy_box_price if keepa else None
        viability_raw = self.normalize_viability(fbm_price_now, buy_box)

        # Apply weights
        weights = brand_settings.weights
        velocity_weighted = velocity_raw * weights.velocity
        profit_weighted = profit_raw * weights.profit
        margin_weighted = margin_raw * weights.margin
        stability_weighted = stability_raw * weights.stability
        viability_weighted = viability_raw * weights.viability

        weighted_sum = (
            velocity_weighted
            + profit_weighted
            + margin_weighted
            + stability_weighted
            + viability_weighted
        )

        # Apply penalties
        is_restricted = spapi.is_restricted if spapi else False
        amazon_present = keepa.amazon_on_listing if keepa else False
        offer_count = keepa.offer_count_fbm if keepa else None

        total_penalty, flags = self.apply_penalties(
            brand_settings,
            is_restricted=is_restricted,
            amazon_present=amazon_present,
            weight_tier=shipping_result.tier,
            mapping_confidence=candidate.confidence_score,
            offer_count=offer_count,
            offer_count_trend=offer_trend,
            sales_proxy_30d=sales_proxy,
            margin_net=winning_scenario.margin_net,
            profit_net=winning_scenario.profit_net,
        )

        # Calculate final score
        score_raw = weighted_sum - total_penalty
        score = max(min(round(score_raw), 100), 0)

        # Check for critical flags that force score to 0
        if any(f.is_critical for f in flags):
            score = 0

        # Build breakdown
        breakdown = ScoreBreakdown(
            velocity_raw=velocity_raw,
            velocity_weighted=velocity_weighted,
            profit_raw=profit_raw,
            profit_weighted=profit_weighted,
            margin_raw=margin_raw,
            margin_weighted=margin_weighted,
            stability_raw=stability_raw,
            stability_weighted=stability_weighted,
            viability_raw=viability_raw,
            viability_weighted=viability_weighted,
            weighted_sum=weighted_sum,
            total_penalties=total_penalty,
            score_raw=score_raw,
        )

        return ScoreResult(
            asin_candidate_id=candidate.id or 0,
            supplier_item_id=item.id or 0,
            asin=candidate.asin,
            brand=item.brand,
            supplier=item.supplier,
            part_number=item.part_number,
            score=score,
            winning_scenario=winning_name,
            scenario_cost_1=scenario_1,
            scenario_cost_5plus=scenario_5,
            breakdown=breakdown,
            flags=flags,
            sales_proxy_30d=sales_proxy,
            offer_count=offer_count,
            amazon_present=amazon_present,
            is_restricted=is_restricted,
            mapping_confidence=candidate.confidence_score,
            weight_kg=weight_kg,
            keepa_snapshot_id=keepa.id if keepa else None,
            spapi_snapshot_id=spapi.id if spapi else None,
            keepa_data_time=keepa.snapshot_time if keepa else None,
            spapi_data_time=spapi.snapshot_time if spapi else None,
        )
