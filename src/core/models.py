"""Core data models for Seller Opportunity Scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class Brand(str, Enum):
    """Supported brands."""

    MAKITA = "Makita"
    DEWALT = "DeWalt"
    TIMCO = "Timco"

    @classmethod
    def from_string(cls, value: str) -> "Brand":
        """Convert string to Brand enum."""
        value_lower = value.lower()
        for brand in cls:
            if brand.value.lower() == value_lower:
                return brand
        raise ValueError(f"Unknown brand: {value}")

    @classmethod
    def values(cls) -> list[str]:
        """Get list of brand values."""
        return [b.value for b in cls]


class CandidateSource(str, Enum):
    """Source of ASIN candidate mapping."""

    MANUAL_CSV = "manual_csv"
    SPAPI_EAN = "spapi_ean"
    SPAPI_KEYWORD = "spapi_keyword"
    USER_ADDED = "user_added"


@dataclass
class SupplierItem:
    """Supplier item from CSV import."""

    id: int | None = None
    brand: Brand = Brand.MAKITA
    supplier: str = ""
    part_number: str = ""
    description: str = ""
    ean: str = ""
    mpn: str = ""
    asin_hint: str = ""  # ASIN from CSV if provided
    cost_ex_vat_1: Decimal = Decimal("0")
    cost_ex_vat_5plus: Decimal = Decimal("0")
    pack_qty: int = 1
    cost_per_unit_ex_vat_1: Decimal = Decimal("0")
    cost_per_unit_ex_vat_5plus: Decimal = Decimal("0")
    import_date: datetime = field(default_factory=datetime.now)
    import_batch_id: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Calculate per-unit costs after initialization."""
        if self.pack_qty > 0:
            self.cost_per_unit_ex_vat_1 = self.cost_ex_vat_1 / self.pack_qty
            self.cost_per_unit_ex_vat_5plus = self.cost_ex_vat_5plus / self.pack_qty


@dataclass
class AsinCandidate:
    """ASIN candidate mapping for a supplier item."""

    id: int | None = None
    supplier_item_id: int = 0
    brand: Brand = Brand.MAKITA
    supplier: str = ""
    part_number: str = ""
    asin: str = ""
    title: str = ""
    amazon_brand: str = ""
    match_reason: str = ""
    confidence_score: Decimal = Decimal("0.5")
    source: CandidateSource = CandidateSource.SPAPI_KEYWORD
    is_active: bool = True
    is_primary: bool = False
    is_locked: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class KeepaSnapshot:
    """Keepa data snapshot for an ASIN."""

    id: int | None = None
    asin: str = ""
    snapshot_time: datetime = field(default_factory=datetime.now)

    # FBM pricing
    fbm_price_current: Decimal | None = None
    fbm_price_median_30d: Decimal | None = None
    fbm_price_mean_30d: Decimal | None = None
    fbm_price_min_30d: Decimal | None = None
    fbm_price_max_30d: Decimal | None = None

    # Sales velocity
    sales_rank_drops_30d: int | None = None
    sales_rank_current: int | None = None

    # Offers
    offer_count_fbm: int | None = None
    offer_count_fba: int | None = None
    offer_count_trend: str = ""  # "rising", "stable", "falling"

    # Buy box (for pass 2)
    buy_box_price: Decimal | None = None
    buy_box_is_fba: bool | None = None
    buy_box_is_amazon: bool | None = None

    # Amazon presence
    amazon_on_listing: bool = False

    # Price volatility
    price_volatility_cv: Decimal | None = None  # Coefficient of variation

    # Token info from response
    tokens_consumed: int = 0

    # Raw data
    raw_json: str = ""

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SpApiSnapshot:
    """SP-API data snapshot for an ASIN."""

    id: int | None = None
    asin: str = ""
    snapshot_time: datetime = field(default_factory=datetime.now)
    sell_price_used: Decimal = Decimal("0")

    # Restrictions
    is_restricted: bool = False
    restriction_reasons: str = ""

    # Fees
    fee_total_gross: Decimal | None = None
    fee_referral: Decimal | None = None
    fee_fba: Decimal | None = None  # Should be 0 for FBM
    fee_variable_closing: Decimal | None = None

    # Weight
    weight_kg: Decimal | None = None
    weight_source: str = ""  # "catalog", "estimated"

    # Catalog info
    product_title: str = ""
    product_brand: str = ""
    product_category: str = ""

    # Raw data
    raw_json: str = ""

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProfitScenario:
    """Profit calculation for a specific cost scenario."""

    scenario_name: str = ""  # "cost_1" or "cost_5plus"
    cost_ex_vat: Decimal = Decimal("0")
    sell_gross_safe: Decimal = Decimal("0")
    sell_net: Decimal = Decimal("0")
    fees_gross: Decimal = Decimal("0")
    fees_net: Decimal = Decimal("0")
    shipping_cost: Decimal = Decimal("0")
    profit_net: Decimal = Decimal("0")
    margin_net: Decimal = Decimal("0")
    is_profitable: bool = False


@dataclass
class ScoreBreakdown:
    """Breakdown of score components."""

    velocity_raw: Decimal = Decimal("0")
    velocity_weighted: Decimal = Decimal("0")
    profit_raw: Decimal = Decimal("0")
    profit_weighted: Decimal = Decimal("0")
    margin_raw: Decimal = Decimal("0")
    margin_weighted: Decimal = Decimal("0")
    stability_raw: Decimal = Decimal("0")
    stability_weighted: Decimal = Decimal("0")
    viability_raw: Decimal = Decimal("0")
    viability_weighted: Decimal = Decimal("0")
    weighted_sum: Decimal = Decimal("0")
    total_penalties: Decimal = Decimal("0")
    score_raw: Decimal = Decimal("0")


@dataclass
class ScoreFlag:
    """A flag/reason affecting the score."""

    code: str = ""
    description: str = ""
    penalty: Decimal = Decimal("0")
    is_critical: bool = False  # Forces score to 0


@dataclass
class ScoreResult:
    """Complete scoring result for a candidate."""

    id: int | None = None
    asin_candidate_id: int = 0
    supplier_item_id: int = 0
    asin: str = ""
    brand: Brand = Brand.MAKITA
    supplier: str = ""
    part_number: str = ""

    # Final score
    score: int = 0
    winning_scenario: str = ""  # "cost_1" or "cost_5plus"

    # Scenarios
    scenario_cost_1: ProfitScenario = field(default_factory=ProfitScenario)
    scenario_cost_5plus: ProfitScenario = field(default_factory=ProfitScenario)

    # Score breakdown
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)

    # Flags
    flags: list[ScoreFlag] = field(default_factory=list)

    # Key metrics for display
    sales_proxy_30d: int | None = None
    offer_count: int | None = None
    amazon_present: bool = False
    is_restricted: bool = False
    mapping_confidence: Decimal = Decimal("0.5")
    weight_kg: Decimal | None = None

    # Keepa/SPAPI snapshot IDs
    keepa_snapshot_id: int | None = None
    spapi_snapshot_id: int | None = None

    # Timestamps
    calculated_at: datetime = field(default_factory=datetime.now)
    keepa_data_time: datetime | None = None
    spapi_data_time: datetime | None = None

    def has_flag(self, code: str) -> bool:
        """Check if a specific flag is present."""
        return any(f.code == code for f in self.flags)

    def get_best_profit(self) -> Decimal:
        """Get the best profit between scenarios."""
        if self.winning_scenario == "cost_1":
            return self.scenario_cost_1.profit_net
        return self.scenario_cost_5plus.profit_net

    def get_best_margin(self) -> Decimal:
        """Get the best margin between scenarios."""
        if self.winning_scenario == "cost_1":
            return self.scenario_cost_1.margin_net
        return self.scenario_cost_5plus.margin_net


@dataclass
class ScoreHistory:
    """Historical score record."""

    id: int | None = None
    asin_candidate_id: int = 0
    asin: str = ""
    score: int = 0
    profit_net: Decimal = Decimal("0")
    margin_net: Decimal = Decimal("0")
    sales_proxy_30d: int | None = None
    flags_json: str = ""
    calculated_at: datetime = field(default_factory=datetime.now)


class AlertType(str, Enum):
    """Types of alerts."""

    SCORE_INCREASE = "score_increase"
    SCORE_DECREASE = "score_decrease"
    SCORE_THRESHOLD = "score_threshold"
    PROFIT_INCREASE = "profit_increase"
    NEW_OPPORTUNITY = "new_opportunity"
    RESTRICTION_CHANGE = "restriction_change"


@dataclass
class Alert:
    """A price/score alert."""

    id: int | None = None
    alert_type: AlertType = AlertType.SCORE_INCREASE
    asin: str = ""
    part_number: str = ""
    brand: str = ""
    title: str = ""
    message: str = ""
    old_value: Decimal | None = None
    new_value: Decimal | None = None
    created_at: datetime = field(default_factory=datetime.now)
    is_read: bool = False
    is_dismissed: bool = False


@dataclass
class TokenStatus:
    """Keepa token status."""

    tokens_left: int = 0
    refill_rate: int = 20
    refill_in_seconds: int = 60
    tokens_consumed_last: int = 0
    token_flow_reduction: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def tokens_per_minute(self) -> int:
        """Estimated tokens per minute based on refill rate."""
        if self.refill_in_seconds > 0:
            return int(self.refill_rate * 60 / self.refill_in_seconds)
        return self.refill_rate


@dataclass
class RefreshStats:
    """Statistics for refresh operations."""

    items_refreshed: int = 0
    items_failed: int = 0
    tokens_used: int = 0
    api_calls: int = 0
    last_error: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = 0.0


@dataclass
class ImportResult:
    """Result of a CSV import operation."""

    success: bool = False
    batch_id: str = ""
    items_imported: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
