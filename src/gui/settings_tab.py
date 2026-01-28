"""Settings tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config import BrandSettings, Settings, get_settings, reload_settings
from src.core.models import Brand


class BrandSettingsWidget(QWidget):
    """Widget for editing per-brand settings."""

    def __init__(self, brand: str, settings: BrandSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.brand = brand
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Thresholds
        thresh_group = QGroupBox("Minimum Thresholds")
        thresh_layout = QFormLayout(thresh_group)

        self.min_sales = QSpinBox()
        self.min_sales.setRange(0, 10000)
        self.min_sales.setValue(self._settings.min_sales_proxy_30d)
        thresh_layout.addRow("Min Sales Proxy 30d:", self.min_sales)

        self.min_margin = QDoubleSpinBox()
        self.min_margin.setRange(0, 1)
        self.min_margin.setDecimals(2)
        self.min_margin.setSingleStep(0.01)
        self.min_margin.setValue(float(self._settings.min_margin_ex_vat))
        thresh_layout.addRow("Min Margin ExVAT:", self.min_margin)

        self.min_profit = QDoubleSpinBox()
        self.min_profit.setRange(0, 1000)
        self.min_profit.setDecimals(2)
        self.min_profit.setSingleStep(0.50)
        self.min_profit.setValue(float(self._settings.min_profit_ex_vat_gbp))
        thresh_layout.addRow("Min Profit ExVAT (£):", self.min_profit)

        self.safe_buffer = QDoubleSpinBox()
        self.safe_buffer.setRange(0, 0.50)
        self.safe_buffer.setDecimals(2)
        self.safe_buffer.setSingleStep(0.01)
        self.safe_buffer.setValue(float(self._settings.safe_price_buffer_pct))
        thresh_layout.addRow("Safe Price Buffer %:", self.safe_buffer)

        layout.addWidget(thresh_group)

        # Scoring weights
        weights_group = QGroupBox("Scoring Weights (must sum to 1.0)")
        weights_layout = QFormLayout(weights_group)

        self.w_velocity = QDoubleSpinBox()
        self.w_velocity.setRange(0, 1)
        self.w_velocity.setDecimals(2)
        self.w_velocity.setSingleStep(0.05)
        self.w_velocity.setValue(float(self._settings.weights.velocity))
        weights_layout.addRow("Velocity:", self.w_velocity)

        self.w_profit = QDoubleSpinBox()
        self.w_profit.setRange(0, 1)
        self.w_profit.setDecimals(2)
        self.w_profit.setSingleStep(0.05)
        self.w_profit.setValue(float(self._settings.weights.profit))
        weights_layout.addRow("Profit:", self.w_profit)

        self.w_margin = QDoubleSpinBox()
        self.w_margin.setRange(0, 1)
        self.w_margin.setDecimals(2)
        self.w_margin.setSingleStep(0.05)
        self.w_margin.setValue(float(self._settings.weights.margin))
        weights_layout.addRow("Margin:", self.w_margin)

        self.w_stability = QDoubleSpinBox()
        self.w_stability.setRange(0, 1)
        self.w_stability.setDecimals(2)
        self.w_stability.setSingleStep(0.05)
        self.w_stability.setValue(float(self._settings.weights.stability))
        weights_layout.addRow("Stability:", self.w_stability)

        self.w_viability = QDoubleSpinBox()
        self.w_viability.setRange(0, 1)
        self.w_viability.setDecimals(2)
        self.w_viability.setSingleStep(0.05)
        self.w_viability.setValue(float(self._settings.weights.viability))
        weights_layout.addRow("FBM Viability:", self.w_viability)

        layout.addWidget(weights_group)

        # Penalties
        penalties_group = QGroupBox("Penalties (points deducted)")
        penalties_layout = QFormLayout(penalties_group)

        self.p_restricted = QDoubleSpinBox()
        self.p_restricted.setRange(0, 100)
        self.p_restricted.setValue(float(self._settings.penalties.restricted))
        penalties_layout.addRow("Restricted:", self.p_restricted)

        self.p_amazon = QDoubleSpinBox()
        self.p_amazon.setRange(0, 100)
        self.p_amazon.setValue(float(self._settings.penalties.amazon_retail_present))
        penalties_layout.addRow("Amazon Retail:", self.p_amazon)

        self.p_weight_unknown = QDoubleSpinBox()
        self.p_weight_unknown.setRange(0, 100)
        self.p_weight_unknown.setValue(float(self._settings.penalties.weight_unknown))
        penalties_layout.addRow("Weight Unknown:", self.p_weight_unknown)

        self.p_low_confidence = QDoubleSpinBox()
        self.p_low_confidence.setRange(0, 100)
        self.p_low_confidence.setValue(float(self._settings.penalties.low_mapping_confidence))
        penalties_layout.addRow("Low Confidence:", self.p_low_confidence)

        self.p_high_offers = QDoubleSpinBox()
        self.p_high_offers.setRange(0, 100)
        self.p_high_offers.setValue(float(self._settings.penalties.high_offer_count))
        penalties_layout.addRow("High Offers:", self.p_high_offers)

        self.p_below_sales = QDoubleSpinBox()
        self.p_below_sales.setRange(0, 100)
        self.p_below_sales.setValue(float(self._settings.penalties.below_min_sales))
        penalties_layout.addRow("Below Min Sales:", self.p_below_sales)

        self.p_below_margin = QDoubleSpinBox()
        self.p_below_margin.setRange(0, 100)
        self.p_below_margin.setValue(float(self._settings.penalties.below_min_margin))
        penalties_layout.addRow("Below Min Margin:", self.p_below_margin)

        self.p_below_profit = QDoubleSpinBox()
        self.p_below_profit.setRange(0, 100)
        self.p_below_profit.setValue(float(self._settings.penalties.below_min_profit))
        penalties_layout.addRow("Below Min Profit:", self.p_below_profit)

        layout.addWidget(penalties_group)
        layout.addStretch()

    def get_settings(self) -> BrandSettings:
        """Get the current settings from the UI."""
        from src.core.config import ScoringPenalties, ScoringWeights

        return BrandSettings(
            min_sales_proxy_30d=self.min_sales.value(),
            min_margin_ex_vat=Decimal(str(self.min_margin.value())),
            min_profit_ex_vat_gbp=Decimal(str(self.min_profit.value())),
            safe_price_buffer_pct=Decimal(str(self.safe_buffer.value())),
            weights=ScoringWeights(
                velocity=Decimal(str(self.w_velocity.value())),
                profit=Decimal(str(self.w_profit.value())),
                margin=Decimal(str(self.w_margin.value())),
                stability=Decimal(str(self.w_stability.value())),
                viability=Decimal(str(self.w_viability.value())),
            ),
            penalties=ScoringPenalties(
                restricted=Decimal(str(self.p_restricted.value())),
                amazon_retail_present=Decimal(str(self.p_amazon.value())),
                weight_unknown=Decimal(str(self.p_weight_unknown.value())),
                low_mapping_confidence=Decimal(str(self.p_low_confidence.value())),
                high_offer_count=Decimal(str(self.p_high_offers.value())),
                below_min_sales=Decimal(str(self.p_below_sales.value())),
                below_min_margin=Decimal(str(self.p_below_margin.value())),
                below_min_profit=Decimal(str(self.p_below_profit.value())),
            ),
        )


class SettingsTab(QWidget):
    """Settings tab for configuring the application."""

    settings_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = get_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Global settings
        global_group = QGroupBox("Global Settings")
        global_layout = QFormLayout(global_group)

        self.vat_rate = QDoubleSpinBox()
        self.vat_rate.setRange(0, 1)
        self.vat_rate.setDecimals(2)
        self.vat_rate.setSingleStep(0.01)
        self.vat_rate.setValue(float(self._settings.vat_rate))
        global_layout.addRow("VAT Rate:", self.vat_rate)

        content_layout.addWidget(global_group)

        # Shipping settings
        shipping_group = QGroupBox("Shipping Model")
        shipping_layout = QFormLayout(shipping_group)

        self.ship_small_max = QDoubleSpinBox()
        self.ship_small_max.setRange(0, 50)
        self.ship_small_max.setDecimals(2)
        self.ship_small_max.setValue(float(self._settings.shipping.tier_small.max_weight_kg))
        shipping_layout.addRow("Small Parcel Max (kg):", self.ship_small_max)

        self.ship_small_cost = QDoubleSpinBox()
        self.ship_small_cost.setRange(0, 50)
        self.ship_small_cost.setDecimals(2)
        self.ship_small_cost.setValue(float(self._settings.shipping.tier_small.cost_gbp))
        shipping_layout.addRow("Small Parcel Cost (£):", self.ship_small_cost)

        self.ship_medium_max = QDoubleSpinBox()
        self.ship_medium_max.setRange(0, 100)
        self.ship_medium_max.setDecimals(1)
        self.ship_medium_max.setValue(float(self._settings.shipping.tier_medium_max_kg))
        shipping_layout.addRow("Medium Parcel Max (kg):", self.ship_medium_max)

        self.ship_medium_cost = QDoubleSpinBox()
        self.ship_medium_cost.setRange(0, 50)
        self.ship_medium_cost.setDecimals(2)
        self.ship_medium_cost.setValue(float(self._settings.shipping.tier_medium_cost_gbp))
        shipping_layout.addRow("Medium Parcel Cost (£):", self.ship_medium_cost)

        content_layout.addWidget(shipping_group)

        # Refresh settings
        refresh_group = QGroupBox("Refresh / Scheduler")
        refresh_layout = QFormLayout(refresh_group)

        self.refresh_enabled = QCheckBox("Continuous Refresh Enabled")
        self.refresh_enabled.setChecked(self._settings.refresh.continuous_enabled)
        refresh_layout.addRow(self.refresh_enabled)

        self.pass1_interval = QSpinBox()
        self.pass1_interval.setRange(5, 3600)
        self.pass1_interval.setValue(self._settings.refresh.pass1_interval_seconds)
        refresh_layout.addRow("Pass 1 Interval (s):", self.pass1_interval)

        self.pass2_interval = QSpinBox()
        self.pass2_interval.setRange(30, 7200)
        self.pass2_interval.setValue(self._settings.refresh.pass2_interval_seconds)
        refresh_layout.addRow("Pass 2 Interval (s):", self.pass2_interval)

        self.shortlist_size = QSpinBox()
        self.shortlist_size.setRange(5, 500)
        self.shortlist_size.setValue(self._settings.refresh.pass2_shortlist_size)
        refresh_layout.addRow("Pass 2 Shortlist Size:", self.shortlist_size)

        self.spapi_ttl = QSpinBox()
        self.spapi_ttl.setRange(5, 1440)
        self.spapi_ttl.setValue(self._settings.refresh.spapi_cache_ttl_minutes)
        refresh_layout.addRow("SP-API Cache TTL (min):", self.spapi_ttl)

        content_layout.addWidget(refresh_group)

        # Mock mode
        mock_group = QGroupBox("Development")
        mock_layout = QFormLayout(mock_group)

        self.mock_mode = QCheckBox("Mock Mode (use fixture data)")
        self.mock_mode.setChecked(self._settings.api.mock_mode)
        mock_layout.addRow(self.mock_mode)

        content_layout.addWidget(mock_group)

        # Brand tabs
        brand_tabs = QTabWidget()
        self.brand_widgets: dict[str, BrandSettingsWidget] = {}
        for brand_name in Brand.values():
            brand_settings = self._settings.get_brand_settings(brand_name)
            widget = BrandSettingsWidget(brand_name, brand_settings)
            brand_tabs.addTab(widget, brand_name)
            self.brand_widgets[brand_name] = widget

        content_layout.addWidget(brand_tabs)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Save button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        """Save current settings."""
        settings = get_settings()

        # Update global settings
        settings.vat_rate = Decimal(str(self.vat_rate.value()))

        # Update shipping
        settings.shipping.tier_small.max_weight_kg = Decimal(str(self.ship_small_max.value()))
        settings.shipping.tier_small.cost_gbp = Decimal(str(self.ship_small_cost.value()))
        settings.shipping.tier_medium_max_kg = Decimal(str(self.ship_medium_max.value()))
        settings.shipping.tier_medium_cost_gbp = Decimal(str(self.ship_medium_cost.value()))

        # Update refresh settings
        settings.refresh.continuous_enabled = self.refresh_enabled.isChecked()
        settings.refresh.pass1_interval_seconds = self.pass1_interval.value()
        settings.refresh.pass2_interval_seconds = self.pass2_interval.value()
        settings.refresh.pass2_shortlist_size = self.shortlist_size.value()
        settings.refresh.spapi_cache_ttl_minutes = self.spapi_ttl.value()

        # Update mock mode
        settings.api.mock_mode = self.mock_mode.isChecked()

        # Update brand settings
        for brand_name, widget in self.brand_widgets.items():
            brand_settings = widget.get_settings()
            if brand_name == "Makita":
                settings.brand_makita = brand_settings
            elif brand_name == "DeWalt":
                settings.brand_dewalt = brand_settings
            elif brand_name == "Timco":
                settings.brand_timco = brand_settings

        # Validate weights
        for brand_name, widget in self.brand_widgets.items():
            bs = widget.get_settings()
            total = bs.weights.total()
            if abs(total - Decimal("1.0")) > Decimal("0.01"):
                QMessageBox.warning(
                    self,
                    "Invalid Weights",
                    f"{brand_name} scoring weights sum to {total:.2f}, should be 1.00",
                )
                return

        settings.save()
        self.settings_changed.emit()
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")

    def _on_reset(self) -> None:
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            settings = Settings()
            settings.save()
            reload_settings()
            # Rebuild UI with defaults
            # For simplicity, just reload the values
            self._settings = get_settings()
            self.settings_changed.emit()
