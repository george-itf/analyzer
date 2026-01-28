"""Tests for scoring engine."""

from decimal import Decimal

import pytest

from src.core.config import Settings
from src.core.models import (
    AsinCandidate,
    Brand,
    CandidateSource,
    KeepaSnapshot,
    ProfitScenario,
    SpApiSnapshot,
    SupplierItem,
)
from src.core.scoring import ScoringEngine


@pytest.fixture
def engine(settings: Settings) -> ScoringEngine:
    return ScoringEngine(settings)


class TestProfitCalculation:
    """Tests for profit/margin calculations."""

    def test_basic_profit(self, engine: ScoringEngine) -> None:
        scenario = engine.calculate_profit_scenario(
            scenario_name="cost_1",
            cost_ex_vat=Decimal("45.99"),
            sell_gross_safe=Decimal("73.24"),
            fees_gross=Decimal("11.49"),
            shipping_cost=Decimal("3.00"),
            vat_rate=Decimal("0.20"),
        )

        # sell_net = 73.24 / 1.20 = 61.0333...
        assert scenario.sell_net == pytest.approx(Decimal("61.033"), abs=Decimal("0.01"))
        # fees_net = 11.49 / 1.20 = 9.575
        assert scenario.fees_net == pytest.approx(Decimal("9.575"), abs=Decimal("0.01"))
        # profit = 61.033 - 45.99 - 9.575 - 3.00 = 2.468
        assert scenario.profit_net == pytest.approx(Decimal("2.47"), abs=Decimal("0.1"))
        assert scenario.is_profitable is True

    def test_negative_profit(self, engine: ScoringEngine) -> None:
        scenario = engine.calculate_profit_scenario(
            scenario_name="cost_1",
            cost_ex_vat=Decimal("80.00"),
            sell_gross_safe=Decimal("73.24"),
            fees_gross=Decimal("11.49"),
            shipping_cost=Decimal("3.00"),
            vat_rate=Decimal("0.20"),
        )

        assert scenario.profit_net < 0
        assert scenario.is_profitable is False

    def test_zero_sell_price(self, engine: ScoringEngine) -> None:
        scenario = engine.calculate_profit_scenario(
            scenario_name="cost_1",
            cost_ex_vat=Decimal("45.99"),
            sell_gross_safe=Decimal("0"),
            fees_gross=None,
            shipping_cost=Decimal("3.00"),
            vat_rate=Decimal("0.20"),
        )

        assert scenario.sell_net == 0
        assert scenario.margin_net == 0


class TestVatConversions:
    """Tests for VAT conversion logic."""

    def test_vat_20pct(self, engine: ScoringEngine) -> None:
        gross = Decimal("120.00")
        vat_rate = Decimal("0.20")
        net = gross / (1 + vat_rate)
        assert net == Decimal("100")

    def test_sell_price_vat(self, engine: ScoringEngine) -> None:
        scenario = engine.calculate_profit_scenario(
            scenario_name="test",
            cost_ex_vat=Decimal("10.00"),
            sell_gross_safe=Decimal("24.00"),
            fees_gross=Decimal("0"),
            shipping_cost=Decimal("0"),
            vat_rate=Decimal("0.20"),
        )

        assert scenario.sell_net == Decimal("20")  # 24 / 1.2

    def test_fees_vat(self, engine: ScoringEngine) -> None:
        scenario = engine.calculate_profit_scenario(
            scenario_name="test",
            cost_ex_vat=Decimal("0"),
            sell_gross_safe=Decimal("120.00"),
            fees_gross=Decimal("18.00"),
            shipping_cost=Decimal("0"),
            vat_rate=Decimal("0.20"),
        )

        assert scenario.fees_net == Decimal("15")  # 18 / 1.2


class TestSellGrossSafe:
    """Tests for safe sell price calculation."""

    def test_uses_minimum(self, engine: ScoringEngine) -> None:
        result = engine.calculate_sell_gross_safe(
            fbm_price_now=Decimal("80.00"),
            fbm_price_median_30d=Decimal("75.00"),
            safe_price_buffer_pct=Decimal("0.03"),
        )
        # Should use 75.00 * (1 - 0.03) = 72.75
        assert result == Decimal("72.75")

    def test_with_only_current(self, engine: ScoringEngine) -> None:
        result = engine.calculate_sell_gross_safe(
            fbm_price_now=Decimal("80.00"),
            fbm_price_median_30d=None,
            safe_price_buffer_pct=Decimal("0.03"),
        )
        assert result == Decimal("77.60")

    def test_with_no_prices(self, engine: ScoringEngine) -> None:
        result = engine.calculate_sell_gross_safe(
            fbm_price_now=None,
            fbm_price_median_30d=None,
            safe_price_buffer_pct=Decimal("0.03"),
        )
        assert result == Decimal("0")


class TestScoreNormalization:
    """Tests for sub-score normalization."""

    def test_velocity_zero(self, engine: ScoringEngine) -> None:
        assert engine.normalize_velocity(0) == 0
        assert engine.normalize_velocity(None) == 0

    def test_velocity_capped(self, engine: ScoringEngine) -> None:
        assert engine.normalize_velocity(1000) == Decimal("100")

    def test_velocity_linear(self, engine: ScoringEngine) -> None:
        result = engine.normalize_velocity(100)
        assert Decimal("40") < result < Decimal("60")  # ~50

    def test_profit_negative(self, engine: ScoringEngine) -> None:
        assert engine.normalize_profit(Decimal("-5.00")) == 0

    def test_margin_negative(self, engine: ScoringEngine) -> None:
        assert engine.normalize_margin(Decimal("-0.10")) == 0

    def test_margin_capped(self, engine: ScoringEngine) -> None:
        assert engine.normalize_margin(Decimal("0.80")) == Decimal("100")


class TestFullScoring:
    """Tests for full score calculation."""

    def test_score_range(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
        sample_keepa_snapshot: KeepaSnapshot,
        sample_spapi_snapshot: SpApiSnapshot,
    ) -> None:
        result = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        assert 0 <= result.score <= 100
        assert result.winning_scenario in ("cost_1", "cost_5plus")
        assert result.asin == "B07RBJYQQN"

    def test_restricted_forces_zero(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
        sample_keepa_snapshot: KeepaSnapshot,
        sample_spapi_snapshot: SpApiSnapshot,
    ) -> None:
        sample_spapi_snapshot.is_restricted = True

        result = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        assert result.score == 0
        assert result.has_flag("RESTRICTED")

    def test_overweight_forces_zero(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
        sample_keepa_snapshot: KeepaSnapshot,
        sample_spapi_snapshot: SpApiSnapshot,
    ) -> None:
        sample_spapi_snapshot.weight_kg = Decimal("25.0")

        result = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        assert result.score == 0
        assert result.has_flag("OVERWEIGHT")

    def test_no_data_graceful(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
    ) -> None:
        result = engine.calculate(sample_item, sample_candidate, None, None)
        assert result.score == 0  # No price data means score ~0

    def test_both_scenarios(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
        sample_keepa_snapshot: KeepaSnapshot,
        sample_spapi_snapshot: SpApiSnapshot,
    ) -> None:
        result = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        # 5+ cost is lower, so should produce higher profit
        assert result.scenario_cost_5plus.profit_net >= result.scenario_cost_1.profit_net
        assert result.winning_scenario == "cost_5plus"

    def test_amazon_present_penalty(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
        sample_keepa_snapshot: KeepaSnapshot,
        sample_spapi_snapshot: SpApiSnapshot,
    ) -> None:
        # Without Amazon
        sample_keepa_snapshot.amazon_on_listing = False
        result_no_amazon = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        # With Amazon
        sample_keepa_snapshot.amazon_on_listing = True
        result_with_amazon = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        assert result_with_amazon.score < result_no_amazon.score
        assert result_with_amazon.has_flag("AMAZON_RETAIL")

    def test_weights_sum_to_100(
        self,
        engine: ScoringEngine,
        sample_item: SupplierItem,
        sample_candidate: AsinCandidate,
        sample_keepa_snapshot: KeepaSnapshot,
        sample_spapi_snapshot: SpApiSnapshot,
    ) -> None:
        result = engine.calculate(
            sample_item, sample_candidate, sample_keepa_snapshot, sample_spapi_snapshot
        )

        b = result.breakdown
        weighted_sum = (
            b.velocity_weighted + b.profit_weighted + b.margin_weighted
            + b.stability_weighted + b.viability_weighted
        )
        assert weighted_sum == pytest.approx(b.weighted_sum, abs=Decimal("0.01"))
