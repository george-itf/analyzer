"""Configuration management for Seller Opportunity Scanner."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_dir = Path.home() / ".seller-opportunity-scanner"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Get the data directory path."""
    data_dir = get_config_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Get the SQLite database file path."""
    return get_data_dir() / "scanner.db"


class ShippingTierConfig(BaseModel):
    """Shipping tier configuration."""

    max_weight_kg: Decimal = Decimal("0.75")
    cost_gbp: Decimal = Decimal("2.00")


class ShippingConfig(BaseModel):
    """Shipping cost configuration."""

    tier_small: ShippingTierConfig = Field(
        default_factory=lambda: ShippingTierConfig(
            max_weight_kg=Decimal("0.75"), cost_gbp=Decimal("2.00")
        )
    )
    tier_medium_max_kg: Decimal = Decimal("20.0")
    tier_medium_cost_gbp: Decimal = Decimal("3.00")
    default_unknown_weight_cost_gbp: Decimal = Decimal("3.00")


class ScoringWeights(BaseModel):
    """Scoring weight configuration."""

    velocity: Decimal = Decimal("0.45")
    profit: Decimal = Decimal("0.20")
    margin: Decimal = Decimal("0.20")
    stability: Decimal = Decimal("0.10")
    viability: Decimal = Decimal("0.05")

    def total(self) -> Decimal:
        """Calculate total weight (should sum to 1.0)."""
        return self.velocity + self.profit + self.margin + self.stability + self.viability


class ScoringPenalties(BaseModel):
    """Scoring penalty configuration."""

    restricted: Decimal = Decimal("100.0")  # Forces score to 0 when >= 100
    amazon_retail_present: Decimal = Decimal("15.0")
    weight_unknown: Decimal = Decimal("5.0")
    overweight: Decimal = Decimal("100.0")  # Forces score to 0
    low_mapping_confidence: Decimal = Decimal("10.0")
    high_offer_count: Decimal = Decimal("8.0")
    offer_count_rising: Decimal = Decimal("5.0")
    below_min_sales: Decimal = Decimal("20.0")
    below_min_margin: Decimal = Decimal("15.0")
    below_min_profit: Decimal = Decimal("15.0")


class BrandSettings(BaseModel):
    """Per-brand configuration settings."""

    min_sales_proxy_30d: int = 20
    min_margin_ex_vat: Decimal = Decimal("0.10")
    min_profit_ex_vat_gbp: Decimal = Decimal("5.00")
    safe_price_buffer_pct: Decimal = Decimal("0.03")
    vat_rate: Decimal | None = None  # None means use global
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    penalties: ScoringPenalties = Field(default_factory=ScoringPenalties)
    enabled: bool = True


class RefreshConfig(BaseModel):
    """Refresh scheduler configuration."""

    continuous_enabled: bool = True
    pass1_interval_seconds: int = 30
    pass2_interval_seconds: int = 300
    target_tokens_per_minute: int | None = None  # None = use Keepa refillRate
    pass2_shortlist_size: int = 50
    spapi_cache_ttl_minutes: int = 60
    max_concurrent_requests: int = 3


class AlertConfig(BaseModel):
    """Alert configuration."""

    enabled: bool = True
    score_increase_threshold: int = 10  # Alert when score increases by this much
    score_decrease_threshold: int = 15  # Alert when score decreases by this much
    score_above_threshold: int = 70  # Alert when score crosses above this
    profit_increase_threshold: Decimal = Decimal("5.00")  # Alert when profit increases by £
    new_opportunity_min_score: int = 60  # Alert for new items scoring above this
    play_sound: bool = True
    show_notification: bool = True


class ApiConfig(BaseModel):
    """API configuration."""

    keepa_api_key: str = ""
    spapi_refresh_token: str = ""
    spapi_client_id: str = ""
    spapi_client_secret: str = ""
    spapi_aws_access_key: str = ""
    spapi_aws_secret_key: str = ""
    spapi_role_arn: str = ""
    mock_mode: bool = False


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=str(get_config_dir() / ".env"),
        env_file_encoding="utf-8",
        env_prefix="SOS_",
        extra="ignore",
    )

    # Global settings
    vat_rate: Decimal = Decimal("0.20")
    marketplace_id: str = "A1F83G8C2ARO7P"  # Amazon.co.uk
    marketplace_domain: str = "amazon.co.uk"
    condition: str = "NEW"
    fulfilment: str = "FBM"  # "FBM" or "FBA"
    fba_mode: bool = False  # When True, calculate FBA fees instead of FBM

    # Shipping
    shipping: ShippingConfig = Field(default_factory=ShippingConfig)

    # Brand-specific settings
    brand_makita: BrandSettings = Field(default_factory=BrandSettings)
    brand_dewalt: BrandSettings = Field(default_factory=BrandSettings)
    brand_timco: BrandSettings = Field(default_factory=BrandSettings)

    # Refresh settings
    refresh: RefreshConfig = Field(default_factory=RefreshConfig)

    # Alert settings
    alerts: AlertConfig = Field(default_factory=AlertConfig)

    # API settings
    api: ApiConfig = Field(default_factory=ApiConfig)

    # UI settings
    log_level: str = "INFO"
    debug_mode: bool = False
    dark_mode: bool = False

    def get_brand_settings(self, brand: str) -> BrandSettings:
        """Get settings for a specific brand."""
        brand_lower = brand.lower()
        if brand_lower == "makita":
            return self.brand_makita
        elif brand_lower == "dewalt":
            return self.brand_dewalt
        elif brand_lower == "timco":
            return self.brand_timco
        else:
            raise ValueError(f"Unknown brand: {brand}")

    def get_effective_vat_rate(self, brand: str | None = None) -> Decimal:
        """Get the effective VAT rate for a brand (or global if not specified)."""
        if brand:
            brand_settings = self.get_brand_settings(brand)
            if brand_settings.vat_rate is not None:
                return brand_settings.vat_rate
        return self.vat_rate

    def save(self) -> None:
        """Save settings to the config file."""
        config_path = get_config_dir() / "settings.json"
        data = self.model_dump(mode="json")
        # Convert Decimal to string for JSON serialization
        data = self._convert_decimals(data)
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)

    def _convert_decimals(self, obj: Any) -> Any:
        """Recursively convert Decimal to string for JSON serialization."""
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals(item) for item in obj]
        return obj

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from the config file or create defaults."""
        config_path = get_config_dir() / "settings.json"
        env_path = get_config_dir() / ".env"

        # Start with defaults
        settings = cls()

        # Load from JSON if exists
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                settings = cls.model_validate(data)
            except Exception:
                pass  # Use defaults on error

        # Override API settings from .env if present
        if env_path.exists():
            from dotenv import dotenv_values

            env_vars = dotenv_values(env_path)
            if env_vars.get("SOS_KEEPA_API_KEY"):
                settings.api.keepa_api_key = env_vars["SOS_KEEPA_API_KEY"]
            if env_vars.get("SOS_SPAPI_REFRESH_TOKEN"):
                settings.api.spapi_refresh_token = env_vars["SOS_SPAPI_REFRESH_TOKEN"]
            if env_vars.get("SOS_SPAPI_CLIENT_ID"):
                settings.api.spapi_client_id = env_vars["SOS_SPAPI_CLIENT_ID"]
            if env_vars.get("SOS_SPAPI_CLIENT_SECRET"):
                settings.api.spapi_client_secret = env_vars["SOS_SPAPI_CLIENT_SECRET"]
            if env_vars.get("SOS_SPAPI_AWS_ACCESS_KEY"):
                settings.api.spapi_aws_access_key = env_vars["SOS_SPAPI_AWS_ACCESS_KEY"]
            if env_vars.get("SOS_SPAPI_AWS_SECRET_KEY"):
                settings.api.spapi_aws_secret_key = env_vars["SOS_SPAPI_AWS_SECRET_KEY"]
            if env_vars.get("SOS_SPAPI_ROLE_ARN"):
                settings.api.spapi_role_arn = env_vars["SOS_SPAPI_ROLE_ARN"]
            if env_vars.get("SOS_MOCK_MODE"):
                settings.api.mock_mode = env_vars["SOS_MOCK_MODE"].lower() in (
                    "true",
                    "1",
                    "yes",
                )

        return settings


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from disk."""
    global _settings
    _settings = Settings.load()
    return _settings
