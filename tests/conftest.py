"""Pytest configuration and fixtures."""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from src.core.config import Settings, BrandSettings, ScoringWeights, ScoringPenalties, ShippingConfig, ShippingTierConfig, RefreshConfig, ApiConfig
from src.core.models import (
    AsinCandidate,
    Brand,
    CandidateSource,
    KeepaSnapshot,
    SpApiSnapshot,
    SupplierItem,
)


@pytest.fixture
def settings() -> Settings:
    """Create default settings for testing."""
    s = Settings()
    s.api.mock_mode = True
    return s


@pytest.fixture
def sample_item() -> SupplierItem:
    """Create a sample supplier item."""
    return SupplierItem(
        id=1,
        brand=Brand.MAKITA,
        supplier="Makita Dist A",
        part_number="DHP482Z",
        description="18V LXT Combi Drill Body Only",
        ean="0088381694049",
        mpn="DHP482Z",
        asin_hint="B07RBJYQQN",
        cost_ex_vat_1=Decimal("45.99"),
        cost_ex_vat_5plus=Decimal("42.50"),
        pack_qty=1,
    )


@pytest.fixture
def sample_candidate() -> AsinCandidate:
    """Create a sample ASIN candidate."""
    return AsinCandidate(
        id=1,
        supplier_item_id=1,
        brand=Brand.MAKITA,
        supplier="Makita Dist A",
        part_number="DHP482Z",
        asin="B07RBJYQQN",
        title="Makita DHP482Z 18V LXT Combi Drill",
        confidence_score=Decimal("0.95"),
        source=CandidateSource.MANUAL_CSV,
        is_active=True,
        is_primary=True,
    )


@pytest.fixture
def sample_keepa_snapshot() -> KeepaSnapshot:
    """Create a sample Keepa snapshot."""
    return KeepaSnapshot(
        id=1,
        asin="B07RBJYQQN",
        fbm_price_current=Decimal("75.50"),
        fbm_price_median_30d=Decimal("75.50"),
        fbm_price_mean_30d=Decimal("76.00"),
        fbm_price_min_30d=Decimal("72.00"),
        fbm_price_max_30d=Decimal("79.00"),
        sales_rank_drops_30d=45,
        sales_rank_current=15000,
        offer_count_fbm=5,
        offer_count_fba=2,
        offer_count_trend="stable",
        amazon_on_listing=False,
        price_volatility_cv=Decimal("0.05"),
    )


@pytest.fixture
def sample_spapi_snapshot() -> SpApiSnapshot:
    """Create a sample SP-API snapshot."""
    return SpApiSnapshot(
        id=1,
        asin="B07RBJYQQN",
        sell_price_used=Decimal("73.24"),
        is_restricted=False,
        fee_total_gross=Decimal("11.49"),
        fee_referral=Decimal("10.99"),
        fee_variable_closing=Decimal("0.50"),
        weight_kg=Decimal("1.5"),
        weight_source="catalog",
        product_title="Makita DHP482Z 18V LXT Combi Drill",
        product_brand="Makita",
    )


@pytest.fixture
def sample_csv_path(tmp_path: Path) -> Path:
    """Create a sample CSV file for testing."""
    csv_content = (
        "Brand,Supplier,PartNumber,Description,EAN,MPN,ASIN,CostExVAT_1,CostExVAT_5Plus,PackQty\n"
        "Makita,Makita Dist A,DHP482Z,18V LXT Combi Drill,0088381694049,DHP482Z,B07RBJYQQN,45.99,42.50,1\n"
        "DeWalt,DeWalt Direct,DCD776C2,18V XR Combi Drill Kit,5035048641811,DCD776C2,,79.99,72.50,1\n"
        "Timco,Timco Supply,SCRW-50,Woodscrew 5.0x50,,SCRW-50,,8.99,7.50,1\n"
    )
    csv_file = tmp_path / "test_import.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return csv_file


@pytest.fixture
def invalid_csv_path(tmp_path: Path) -> Path:
    """Create a CSV file with invalid headers."""
    csv_content = "Name,Price,SKU\nTest,10.00,ABC123\n"
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return csv_file
