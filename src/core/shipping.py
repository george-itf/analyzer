"""Shipping cost calculation for Seller Opportunity Scanner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings


class ShippingTier(str, Enum):
    """Shipping tier classification."""

    SMALL = "small"  # <= 0.75kg
    MEDIUM = "medium"  # 0.75kg - 20kg
    OVERWEIGHT = "overweight"  # > 20kg
    UNKNOWN = "unknown"  # No weight data


@dataclass
class ShippingResult:
    """Result of shipping cost calculation."""

    tier: ShippingTier
    cost_gbp: Decimal
    weight_kg: Decimal | None
    is_valid: bool
    notes: str = ""


class ShippingCalculator:
    """Calculates shipping costs based on weight."""

    def __init__(self, settings: Settings) -> None:
        """Initialize with settings."""
        self.settings = settings
        self.shipping_config = settings.shipping

    def calculate(self, weight_kg: Decimal | None) -> ShippingResult:
        """Calculate shipping cost for given weight."""
        # Handle unknown weight
        if weight_kg is None:
            return ShippingResult(
                tier=ShippingTier.UNKNOWN,
                cost_gbp=self.shipping_config.default_unknown_weight_cost_gbp,
                weight_kg=None,
                is_valid=True,
                notes="Weight unknown, using default medium tier cost",
            )

        # Small tier: <= 0.75kg
        if weight_kg <= self.shipping_config.tier_small.max_weight_kg:
            return ShippingResult(
                tier=ShippingTier.SMALL,
                cost_gbp=self.shipping_config.tier_small.cost_gbp,
                weight_kg=weight_kg,
                is_valid=True,
                notes=f"Small parcel: {weight_kg}kg",
            )

        # Medium tier: 0.75kg - 20kg
        if weight_kg <= self.shipping_config.tier_medium_max_kg:
            return ShippingResult(
                tier=ShippingTier.MEDIUM,
                cost_gbp=self.shipping_config.tier_medium_cost_gbp,
                weight_kg=weight_kg,
                is_valid=True,
                notes=f"Medium parcel: {weight_kg}kg",
            )

        # Overweight: > 20kg
        return ShippingResult(
            tier=ShippingTier.OVERWEIGHT,
            cost_gbp=Decimal("0"),  # Invalid for normal operations
            weight_kg=weight_kg,
            is_valid=False,
            notes=f"Overweight: {weight_kg}kg exceeds 20kg limit",
        )

    def get_tier(self, weight_kg: Decimal | None) -> ShippingTier:
        """Get the shipping tier for a weight without calculating cost."""
        if weight_kg is None:
            return ShippingTier.UNKNOWN
        if weight_kg <= self.shipping_config.tier_small.max_weight_kg:
            return ShippingTier.SMALL
        if weight_kg <= self.shipping_config.tier_medium_max_kg:
            return ShippingTier.MEDIUM
        return ShippingTier.OVERWEIGHT

    def is_valid_weight(self, weight_kg: Decimal | None) -> bool:
        """Check if weight is valid for shipping."""
        if weight_kg is None:
            return True  # Unknown weight is accepted with penalty
        return weight_kg <= self.shipping_config.tier_medium_max_kg
