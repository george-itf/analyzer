"""SQLAlchemy database models for Seller Opportunity Scanner."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class SupplierItemDB(Base):
    """Supplier item from CSV import."""

    __tablename__ = "supplier_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    ean: Mapped[str] = mapped_column(String(20), default="", index=True)
    mpn: Mapped[str] = mapped_column(String(100), default="")
    asin_hint: Mapped[str] = mapped_column(String(20), default="")

    cost_ex_vat_1: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    cost_ex_vat_5plus: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    pack_qty: Mapped[int] = mapped_column(Integer, default=1)
    cost_per_unit_ex_vat_1: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    cost_per_unit_ex_vat_5plus: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0")
    )

    import_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    import_batch_id: Mapped[str] = mapped_column(String(50), default="", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    candidates: Mapped[list[AsinCandidateDB]] = relationship(
        "AsinCandidateDB", back_populates="supplier_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("brand", "supplier", "part_number", "import_batch_id", name="uq_item_batch"),
        Index("ix_supplier_items_brand_active", "brand", "is_active"),
    )


class AsinCandidateDB(Base):
    """ASIN candidate mapping for a supplier item."""

    __tablename__ = "asin_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("supplier_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier: Mapped[str] = mapped_column(String(200), nullable=False)
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    asin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    title: Mapped[str] = mapped_column(Text, default="")
    amazon_brand: Mapped[str] = mapped_column(String(200), default="")
    match_reason: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.5"))
    source: Mapped[str] = mapped_column(String(50), default="spapi_keyword")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    supplier_item: Mapped[SupplierItemDB] = relationship("SupplierItemDB", back_populates="candidates")
    keepa_snapshots: Mapped[list[KeepaSnapshotDB]] = relationship(
        "KeepaSnapshotDB", back_populates="candidate", cascade="all, delete-orphan"
    )
    spapi_snapshots: Mapped[list[SpApiSnapshotDB]] = relationship(
        "SpApiSnapshotDB", back_populates="candidate", cascade="all, delete-orphan"
    )
    score_history: Mapped[list[ScoreHistoryDB]] = relationship(
        "ScoreHistoryDB", back_populates="candidate", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("supplier_item_id", "asin", name="uq_candidate_asin"),
        Index("ix_asin_candidates_part_asin", "part_number", "asin"),
    )


class KeepaSnapshotDB(Base):
    """Keepa data snapshot for an ASIN."""

    __tablename__ = "keepa_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("asin_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    # FBM pricing
    fbm_price_current: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fbm_price_median_30d: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fbm_price_mean_30d: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fbm_price_min_30d: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fbm_price_max_30d: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Sales velocity
    sales_rank_drops_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_rank_current: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Offers
    offer_count_fbm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_count_fba: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_count_trend: Mapped[str] = mapped_column(String(20), default="")

    # Buy box
    buy_box_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    buy_box_is_fba: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    buy_box_is_amazon: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Amazon presence
    amazon_on_listing: Mapped[bool] = mapped_column(Boolean, default=False)

    # Price volatility
    price_volatility_cv: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    # Token info
    tokens_consumed: Mapped[int] = mapped_column(Integer, default=0)

    # Raw data
    raw_json: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    candidate: Mapped[AsinCandidateDB] = relationship("AsinCandidateDB", back_populates="keepa_snapshots")

    __table_args__ = (Index("ix_keepa_snapshots_asin_time", "asin", "snapshot_time"),)


class SpApiSnapshotDB(Base):
    """SP-API data snapshot for an ASIN."""

    __tablename__ = "spapi_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("asin_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    sell_price_used: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    # Restrictions
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    restriction_reasons: Mapped[str] = mapped_column(Text, default="")

    # Fees
    fee_total_gross: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    fee_referral: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    fee_fba: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    fee_variable_closing: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Weight
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    weight_source: Mapped[str] = mapped_column(String(50), default="")

    # Catalog info
    product_title: Mapped[str] = mapped_column(Text, default="")
    product_brand: Mapped[str] = mapped_column(String(200), default="")
    product_category: Mapped[str] = mapped_column(String(200), default="")

    # Raw data
    raw_json: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    candidate: Mapped[AsinCandidateDB] = relationship("AsinCandidateDB", back_populates="spapi_snapshots")

    __table_args__ = (Index("ix_spapi_snapshots_asin_time", "asin", "snapshot_time"),)


class ScoreHistoryDB(Base):
    """Historical score records."""

    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("asin_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    score: Mapped[int] = mapped_column(Integer, default=0)
    winning_scenario: Mapped[str] = mapped_column(String(20), default="")
    profit_net: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    margin_net: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    sales_proxy_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Score breakdown JSON
    breakdown_json: Mapped[str] = mapped_column(Text, default="")
    flags_json: Mapped[str] = mapped_column(Text, default="")

    # Snapshot references
    keepa_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spapi_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    # Relationships
    candidate: Mapped[AsinCandidateDB] = relationship("AsinCandidateDB", back_populates="score_history")

    __table_args__ = (Index("ix_score_history_candidate_time", "candidate_id", "calculated_at"),)


class BrandSettingsDB(Base):
    """Per-brand settings stored in database."""

    __tablename__ = "brand_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    min_sales_proxy_30d: Mapped[int] = mapped_column(Integer, default=20)
    min_margin_ex_vat: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.10"))
    min_profit_ex_vat_gbp: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("5.00"))
    safe_price_buffer_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.03"))
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    # Weights JSON
    weights_json: Mapped[str] = mapped_column(Text, default="{}")

    # Penalties JSON
    penalties_json: Mapped[str] = mapped_column(Text, default="{}")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class GlobalSettingsDB(Base):
    """Global application settings stored in database."""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, default="")
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string, int, decimal, bool, json

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class ApiLogDB(Base):
    """API call log for diagnostics."""

    __tablename__ = "api_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # keepa, spapi
    endpoint: Mapped[str] = mapped_column(String(200), default="")
    method: Mapped[str] = mapped_column(String(10), default="GET")

    request_params: Mapped[str] = mapped_column(Text, default="")
    response_status: Mapped[int] = mapped_column(Integer, default=0)
    response_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    tokens_consumed: Mapped[int] = mapped_column(Integer, default=0)

    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    __table_args__ = (Index("ix_api_logs_api_time", "api_name", "created_at"),)
