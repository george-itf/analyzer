"""GUI tests for Seller Opportunity Scanner using pytest-qt."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.core.config import Settings
from src.core.models import Brand, ScoreResult, ProfitScenario, ScoreBreakdown
from src.gui.widgets import ScoreRingWidget, SparklineWidget, TokenStatusWidget


# Fixtures

@pytest.fixture
def score_result():
    """Create a sample ScoreResult for testing."""
    return ScoreResult(
        asin_candidate_id=1,
        supplier_item_id=1,
        asin="B001234567",
        brand=Brand.MAKITA,
        supplier="Test Supplier",
        part_number="TEST-001",
        score=75,
        winning_scenario="cost_1",
        scenario_cost_1=ProfitScenario(
            scenario_name="cost_1",
            cost_ex_vat=Decimal("10.00"),
            sell_gross_safe=Decimal("25.00"),
            sell_net=Decimal("20.83"),
            fees_gross=Decimal("3.75"),
            fees_net=Decimal("3.13"),
            shipping_cost=Decimal("2.00"),
            profit_net=Decimal("5.70"),
            margin_net=Decimal("0.27"),
            is_profitable=True,
        ),
        scenario_cost_5plus=ProfitScenario(
            scenario_name="cost_5plus",
            cost_ex_vat=Decimal("8.00"),
            sell_gross_safe=Decimal("25.00"),
            sell_net=Decimal("20.83"),
            fees_gross=Decimal("3.75"),
            fees_net=Decimal("3.13"),
            shipping_cost=Decimal("2.00"),
            profit_net=Decimal("7.70"),
            margin_net=Decimal("0.37"),
            is_profitable=True,
        ),
        breakdown=ScoreBreakdown(),
        flags=[],
        sales_proxy_30d=50,
        offer_count=5,
        amazon_present=False,
        is_restricted=False,
        mapping_confidence=Decimal("0.9"),
    )


# Widget Tests

class TestScoreRingWidget:
    """Tests for ScoreRingWidget."""

    def test_initial_score_is_zero(self, qtbot):
        """Test that initial score is 0."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        assert widget.score == 0

    def test_set_score(self, qtbot):
        """Test setting score value."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        
        widget.score = 75
        assert widget.score == 75

    def test_score_clamped_to_0(self, qtbot):
        """Test that negative scores are clamped to 0."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        
        widget.score = -10
        assert widget.score == 0

    def test_score_clamped_to_100(self, qtbot):
        """Test that scores > 100 are clamped to 100."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        
        widget.score = 150
        assert widget.score == 100

    def test_score_color_low(self, qtbot):
        """Test color for low scores (red spectrum)."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        
        color = widget.get_score_color(25)
        # Should be in red spectrum
        assert color.red() > color.green()

    def test_score_color_medium(self, qtbot):
        """Test color for medium scores (orange/yellow spectrum)."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        
        color = widget.get_score_color(65)
        # Should be in orange/yellow spectrum
        assert color.red() > 150
        assert color.green() > 100

    def test_score_color_high(self, qtbot):
        """Test color for high scores (green spectrum)."""
        widget = ScoreRingWidget()
        qtbot.addWidget(widget)
        
        color = widget.get_score_color(90)
        # Should be in green spectrum
        assert color.green() > color.red()


class TestSparklineWidget:
    """Tests for SparklineWidget."""

    def test_initial_values_empty(self, qtbot):
        """Test that initial values list is empty."""
        widget = SparklineWidget()
        qtbot.addWidget(widget)
        assert widget.values == []

    def test_set_values(self, qtbot):
        """Test setting sparkline values."""
        widget = SparklineWidget()
        qtbot.addWidget(widget)
        
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        widget.values = values
        assert widget.values == values

    def test_values_truncated_to_20(self, qtbot):
        """Test that values are truncated to last 20 points."""
        widget = SparklineWidget()
        qtbot.addWidget(widget)
        
        values = list(range(30))  # 30 values
        widget.values = [float(v) for v in values]
        assert len(widget.values) == 20
        assert widget.values[0] == 10.0  # Should keep last 20

    def test_trend_color_upward(self, qtbot):
        """Test trend color for upward trend (green)."""
        widget = SparklineWidget()
        qtbot.addWidget(widget)
        
        widget.values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        color = widget.get_trend_color()
        # Upward trend should be green
        assert color.green() > color.red()

    def test_trend_color_downward(self, qtbot):
        """Test trend color for downward trend (red)."""
        widget = SparklineWidget()
        qtbot.addWidget(widget)
        
        widget.values = [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        color = widget.get_trend_color()
        # Downward trend should be red
        assert color.red() > color.green()

    def test_trend_color_flat(self, qtbot):
        """Test trend color for flat trend (gray)."""
        widget = SparklineWidget()
        qtbot.addWidget(widget)
        
        widget.values = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        color = widget.get_trend_color()
        # Flat trend should be gray (R ≈ G ≈ B)
        assert abs(color.red() - color.green()) < 20


class TestTokenStatusWidget:
    """Tests for TokenStatusWidget."""

    def test_initial_state(self, qtbot):
        """Test initial token status state."""
        widget = TokenStatusWidget()
        qtbot.addWidget(widget)
        
        assert widget._tokens_left == 0
        assert widget._refill_rate == 20
        assert widget._refill_in == 60

    def test_update_status(self, qtbot):
        """Test updating token status."""
        widget = TokenStatusWidget()
        qtbot.addWidget(widget)
        
        widget.update_status(250, 30, 45)
        
        assert widget._tokens_left == 250
        assert widget._refill_rate == 30
        assert widget._refill_in == 45


# Integration-style tests (with mocked dependencies)

class TestBrandTab:
    """Tests for BrandTab widget."""

    def test_brand_tab_creation(self, qtbot):
        """Test BrandTab can be created for each brand."""
        from src.gui.brand_tab import BrandTab
        
        for brand in Brand:
            tab = BrandTab(brand)
            qtbot.addWidget(tab)
            assert tab.brand == brand

    def test_brand_tab_update_results(self, qtbot, score_result):
        """Test updating BrandTab with results."""
        from src.gui.brand_tab import BrandTab
        
        tab = BrandTab(Brand.MAKITA)
        qtbot.addWidget(tab)
        
        results = [score_result]
        titles = {"B001234567": "Test Product"}
        
        tab.update_results(results, titles)
        
        assert tab.model.rowCount() == 1
        assert tab.count_label.text() == "1 items"

    def test_brand_tab_empty_results(self, qtbot):
        """Test BrandTab with no results."""
        from src.gui.brand_tab import BrandTab
        
        tab = BrandTab(Brand.DEWALT)
        qtbot.addWidget(tab)
        
        tab.update_results([], {})
        
        assert tab.model.rowCount() == 0
        assert tab.count_label.text() == "0 items"

    def test_brand_tab_filter(self, qtbot, score_result):
        """Test filtering in BrandTab."""
        from src.gui.brand_tab import BrandTab
        
        tab = BrandTab(Brand.MAKITA)
        qtbot.addWidget(tab)
        
        tab.update_results([score_result], {})
        
        # Filter by part number
        tab.filter_input.setText("TEST-001")
        assert tab.proxy_model.rowCount() == 1
        
        # Filter with no match
        tab.filter_input.setText("NONEXISTENT")
        assert tab.proxy_model.rowCount() == 0


class TestScoreTableModel:
    """Tests for ScoreTableModel."""

    def test_model_columns(self, qtbot):
        """Test model has correct columns."""
        from src.gui.brand_tab import ScoreTableModel
        
        model = ScoreTableModel()
        
        # Check column count
        assert model.columnCount() > 10
        
        # Check column headers exist
        for i in range(model.columnCount()):
            header = model.headerData(i, Qt.Orientation.Horizontal)
            assert header is not None

    def test_model_set_results(self, qtbot, score_result):
        """Test setting results in model."""
        from src.gui.brand_tab import ScoreTableModel
        
        model = ScoreTableModel()
        model.set_results([score_result], {"B001234567": "Test"})
        
        assert model.rowCount() == 1

    def test_model_get_result(self, qtbot, score_result):
        """Test getting result from model."""
        from src.gui.brand_tab import ScoreTableModel
        
        model = ScoreTableModel()
        model.set_results([score_result])
        
        result = model.get_result(0)
        assert result is not None
        assert result.asin == "B001234567"

    def test_model_get_result_invalid_row(self, qtbot):
        """Test getting result with invalid row."""
        from src.gui.brand_tab import ScoreTableModel
        
        model = ScoreTableModel()
        result = model.get_result(999)
        assert result is None


class TestSettingsTab:
    """Tests for SettingsTab widget."""

    def test_settings_tab_creation(self, qtbot):
        """Test SettingsTab can be created."""
        from src.gui.settings_tab import SettingsTab
        
        with patch('src.gui.settings_tab.get_settings') as mock_settings:
            mock_settings.return_value = Settings()
            tab = SettingsTab()
            qtbot.addWidget(tab)
            
            # Check key widgets exist
            assert hasattr(tab, 'vat_rate')
            assert hasattr(tab, 'refresh_enabled')
            assert hasattr(tab, 'brand_widgets')

    def test_settings_tab_vat_rate(self, qtbot):
        """Test VAT rate spinbox."""
        from src.gui.settings_tab import SettingsTab
        
        with patch('src.gui.settings_tab.get_settings') as mock_settings:
            settings = Settings()
            settings.vat_rate = Decimal("0.20")
            mock_settings.return_value = settings
            
            tab = SettingsTab()
            qtbot.addWidget(tab)
            
            assert tab.vat_rate.value() == 0.20


class TestDashboardTab:
    """Tests for DashboardTab widget."""

    def test_dashboard_tab_creation(self, qtbot):
        """Test DashboardTab can be created."""
        from src.gui.dashboard_tab import DashboardTab
        
        with patch('src.gui.dashboard_tab.Repository'):
            tab = DashboardTab()
            qtbot.addWidget(tab)
            
            # Check key widgets exist
            assert hasattr(tab, 'total_items_card')
            assert hasattr(tab, 'active_opportunities_card')
            assert hasattr(tab, 'brand_widgets')


class TestImportsTab:
    """Tests for ImportsTab widget."""

    def test_imports_tab_creation(self, qtbot):
        """Test ImportsTab can be created."""
        from src.gui.imports_tab import ImportsTab
        
        with patch('src.gui.imports_tab.Repository'):
            tab = ImportsTab()
            qtbot.addWidget(tab)
            
            # Check key widgets exist
            assert hasattr(tab, 'import_btn')
            assert hasattr(tab, 'cancel_btn')
            assert tab.import_btn.isEnabled() == False  # No file selected


class TestMappingsTab:
    """Tests for MappingsTab widget."""

    def test_mappings_tab_creation(self, qtbot):
        """Test MappingsTab can be created."""
        from src.gui.mappings_tab import MappingsTab
        
        with patch('src.gui.mappings_tab.Repository'):
            tab = MappingsTab()
            qtbot.addWidget(tab)
            
            # Check key widgets exist
            assert hasattr(tab, 'brand_filter')
            assert hasattr(tab, 'items_tree')
