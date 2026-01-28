"""Main window for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from decimal import Decimal

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config import Settings, get_settings
from src.core.models import Brand, ScoreResult
from src.core.scheduler import RefreshController
from src.db.repository import Repository

from .brand_tab import BrandTab
from .diagnostics_tab import DiagnosticsTab
from .imports_tab import ImportsTab
from .mappings_tab import MappingsTab
from .settings_tab import SettingsTab
from .widgets import TokenStatusWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._repo = Repository()
        self._refresh_controller: RefreshController | None = None

        self.setWindowTitle("Seller Opportunity Scanner")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self._build_ui()
        self._connect_signals()
        self._load_initial_data()

    def _build_ui(self) -> None:
        """Build the main window UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Top status bar with token info
        top_bar = QHBoxLayout()

        # Token status widget
        self.token_widget = TokenStatusWidget()
        top_bar.addWidget(self.token_widget)

        # Last refresh time
        self.last_refresh_label = QLabel("Last refresh: —")
        top_bar.addWidget(self.last_refresh_label)

        top_bar.addStretch()

        # Refresh toggle
        self.refresh_btn = QPushButton("Start Refresh")
        self.refresh_btn.setCheckable(True)
        self.refresh_btn.clicked.connect(self._on_toggle_refresh)
        top_bar.addWidget(self.refresh_btn)

        main_layout.addLayout(top_bar)

        # Tab widget
        self.tabs = QTabWidget()

        # Brand tabs
        self.brand_tabs: dict[str, BrandTab] = {}
        for brand in Brand:
            tab = BrandTab(brand)
            self.tabs.addTab(tab, brand.value)
            self.brand_tabs[brand.value] = tab

        # Mappings tab
        self.mappings_tab = MappingsTab()
        self.tabs.addTab(self.mappings_tab, "Mappings")

        # Imports tab
        self.imports_tab = ImportsTab()
        self.tabs.addTab(self.imports_tab, "Imports")

        # Settings tab
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.settings_tab, "Settings")

        # Diagnostics tab
        self.diagnostics_tab = DiagnosticsTab()
        self.tabs.addTab(self.diagnostics_tab, "Diagnostics")

        main_layout.addWidget(self.tabs)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # Import completed -> refresh mappings and data
        self.imports_tab.import_completed.connect(self._on_import_completed)

        # Mapping updated -> refresh brand tabs
        self.mappings_tab.mapping_updated.connect(self._on_mapping_updated)

        # Settings changed -> reload
        self.settings_tab.settings_changed.connect(self._on_settings_changed)

    def _load_initial_data(self) -> None:
        """Load initial data from database into UI."""
        for brand in Brand:
            self._refresh_brand_tab(brand)

        self.mappings_tab.refresh_data()
        self.diagnostics_tab.refresh_data()

    def _refresh_brand_tab(self, brand: Brand) -> None:
        """Refresh data for a brand tab."""
        tab = self.brand_tabs.get(brand.value)
        if not tab:
            return

        # Get all active candidates with latest scores
        candidates = self._repo.get_candidates_by_brand(brand, active_only=True)

        results: list[ScoreResult] = []
        titles: dict[str, str] = {}

        for candidate in candidates:
            if candidate.id:
                # Get latest score
                latest = self._repo.get_latest_score(candidate.id)
                if latest:
                    # Get supplier item for this candidate
                    item = self._repo.get_supplier_item_by_id(candidate.supplier_item_id)
                    if item:
                        # Get latest snapshots
                        keepa = self._repo.get_latest_keepa_snapshot(candidate.id)
                        spapi = self._repo.get_latest_spapi_snapshot(candidate.id)

                        # Recompute score with latest data
                        from src.core.scoring import ScoringEngine

                        engine = ScoringEngine(self._settings)
                        result = engine.calculate(item, candidate, keepa, spapi)
                        results.append(result)

                        if candidate.title:
                            titles[candidate.asin] = candidate.title

        tab.update_results(results, titles)

    def _on_toggle_refresh(self, checked: bool) -> None:
        """Toggle background refresh."""
        if checked:
            self._start_refresh()
            self.refresh_btn.setText("Stop Refresh")
        else:
            self._stop_refresh()
            self.refresh_btn.setText("Start Refresh")

    def _start_refresh(self) -> None:
        """Start background data refresh."""
        if self._refresh_controller and self._refresh_controller.is_running:
            return

        self._refresh_controller = RefreshController(self._settings, parent=self)

        # Connect refresh signals
        self._refresh_controller.token_status_updated.connect(self._on_token_update)
        self._refresh_controller.score_updated.connect(self._on_score_updated)
        self._refresh_controller.batch_completed.connect(self._on_batch_completed)
        self._refresh_controller.error_occurred.connect(self._on_refresh_error)
        self._refresh_controller.log_message.connect(self._on_refresh_log)

        self._refresh_controller.start()
        self.status_bar.showMessage("Refresh started")
        logger.info("Background refresh started")

    def _stop_refresh(self) -> None:
        """Stop background data refresh."""
        if self._refresh_controller:
            self._refresh_controller.stop()
            self._refresh_controller = None

        self.status_bar.showMessage("Refresh stopped")
        logger.info("Background refresh stopped")

    def _on_token_update(self, tokens_left: int, refill_rate: int, refill_in: int) -> None:
        """Handle token status update from refresh worker."""
        self.token_widget.update_status(tokens_left, refill_rate, refill_in)

    def _on_score_updated(self, brand: str, asin: str, score: int) -> None:
        """Handle individual score update."""
        # Refresh the brand tab periodically (debounced)
        # For now just track that we need refresh
        pass

    def _on_batch_completed(self, pass_name: str, success: int, fail: int) -> None:
        """Handle batch completion."""
        from datetime import datetime

        now = datetime.now().strftime("%H:%M:%S")
        self.last_refresh_label.setText(f"Last refresh: {now}")
        self.status_bar.showMessage(f"{pass_name}: {success} ok, {fail} failed")

        # Refresh all brand tabs
        for brand in Brand:
            self._refresh_brand_tab(brand)

    def _on_refresh_error(self, error: str) -> None:
        """Handle refresh error."""
        self.status_bar.showMessage(f"Error: {error}")
        self.diagnostics_tab.append_log(f"ERROR: {error}")

    def _on_refresh_log(self, message: str) -> None:
        """Handle refresh log message."""
        self.diagnostics_tab.append_log(message)

    def _on_import_completed(self, batch_id: str) -> None:
        """Handle CSV import completion."""
        self.status_bar.showMessage(f"Import completed: {batch_id}")

        # Refresh all tabs
        for brand in Brand:
            self._refresh_brand_tab(brand)
        self.mappings_tab.refresh_data()

        # If refresh is running, queue priority refresh for newly imported items
        if self._refresh_controller and self._refresh_controller.is_running:
            # Get ASINs from the import batch
            candidates = self._repo.get_candidates_by_batch(batch_id)
            asins = list({c.asin for c in candidates if c.asin})
            if asins:
                self._refresh_controller.queue_priority_refresh(asins)
                self.status_bar.showMessage(
                    f"Import completed: {batch_id}. Queued {len(asins)} ASINs for immediate refresh."
                )

    def _on_mapping_updated(self) -> None:
        """Handle mapping update."""
        for brand in Brand:
            self._refresh_brand_tab(brand)

    def _on_settings_changed(self) -> None:
        """Handle settings change."""
        from src.core.config import reload_settings

        self._settings = reload_settings()
        self.status_bar.showMessage("Settings updated")

        # Restart refresh if running
        if self._refresh_controller and self._refresh_controller.is_running:
            self._stop_refresh()
            self._start_refresh()

    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Stop refresh
        if self._refresh_controller:
            self._refresh_controller.stop()

        event.accept()
