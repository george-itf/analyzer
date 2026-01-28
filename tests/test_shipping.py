"""Tests for shipping calculator."""

from decimal import Decimal

import pytest

from src.core.config import Settings
from src.core.shipping import ShippingCalculator, ShippingTier


@pytest.fixture
def calculator(settings: Settings) -> ShippingCalculator:
    return ShippingCalculator(settings)


class TestShippingCalculator:
    """Tests for shipping cost calculation."""

    def test_small_parcel(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(Decimal("0.5"))
        assert result.tier == ShippingTier.SMALL
        assert result.cost_gbp == Decimal("2.00")
        assert result.is_valid is True

    def test_small_parcel_boundary(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(Decimal("0.75"))
        assert result.tier == ShippingTier.SMALL
        assert result.cost_gbp == Decimal("2.00")

    def test_medium_parcel(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(Decimal("1.5"))
        assert result.tier == ShippingTier.MEDIUM
        assert result.cost_gbp == Decimal("3.00")
        assert result.is_valid is True

    def test_medium_parcel_boundary(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(Decimal("20.0"))
        assert result.tier == ShippingTier.MEDIUM
        assert result.cost_gbp == Decimal("3.00")

    def test_overweight(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(Decimal("25.0"))
        assert result.tier == ShippingTier.OVERWEIGHT
        assert result.is_valid is False

    def test_unknown_weight(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(None)
        assert result.tier == ShippingTier.UNKNOWN
        assert result.cost_gbp == Decimal("3.00")
        assert result.is_valid is True

    def test_zero_weight(self, calculator: ShippingCalculator) -> None:
        result = calculator.calculate(Decimal("0"))
        assert result.tier == ShippingTier.SMALL
        assert result.cost_gbp == Decimal("2.00")

    def test_get_tier(self, calculator: ShippingCalculator) -> None:
        assert calculator.get_tier(None) == ShippingTier.UNKNOWN
        assert calculator.get_tier(Decimal("0.3")) == ShippingTier.SMALL
        assert calculator.get_tier(Decimal("5.0")) == ShippingTier.MEDIUM
        assert calculator.get_tier(Decimal("30.0")) == ShippingTier.OVERWEIGHT
