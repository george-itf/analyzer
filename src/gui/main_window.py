"""Main window for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from decimal import Decimal

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QIcon

from src.core.config import Settings, get_settings
from src.core.models import Alert, Brand, ScoreResult
from src.core.scheduler import RefreshController
from src.core.updater import Updater, UpdateInfo, get_current_version
from src.db.repository import Repository

from .brand_tab import BrandTab
from .competitors_tab import CompetitorsTab
from .dashboard_tab import DashboardTab
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
        self._setup_shortcuts()
        self._setup_tray_icon()
        self._connect_signals()
        self._load_initial_data()
        self._check_for_updates_on_startup()

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

        # Alert indicator
        self.alert_label = QLabel("🔔 0")
        self.alert_label.setStyleSheet("color: #6c757d; font-weight: bold;")
        self.alert_label.setToolTip("No new alerts")
        top_bar.addWidget(self.alert_label)
        self._alert_count = 0

        top_bar.addStretch()

        # Version label
        self.version_label = QLabel(f"v{get_current_version()}")
        self.version_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        top_bar.addWidget(self.version_label)

        # Refresh toggle
        self.refresh_btn = QPushButton("Start Refresh")
        self.refresh_btn.setCheckable(True)
        self.refresh_btn.clicked.connect(self._on_toggle_refresh)
        top_bar.addWidget(self.refresh_btn)

        # Check updates button
        self.update_btn = QPushButton("Check Updates")
        self.update_btn.clicked.connect(self._on_check_updates)
        top_bar.addWidget(self.update_btn)

        main_layout.addLayout(top_bar)

        # Tab widget
        self.tabs = QTabWidget()

        # Dashboard tab (first)
        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Dashboard")

        # Brand tabs
        self.brand_tabs: dict[str, BrandTab] = {}
        for brand in Brand:
            tab = BrandTab(brand)
            self.tabs.addTab(tab, brand.value)
            self.brand_tabs[brand.value] = tab

        # Mappings tab
        self.mappings_tab = MappingsTab()
        self.tabs.addTab(self.mappings_tab, "Mappings")

        # Competitors tab
        self.competitors_tab = CompetitorsTab()
        self.tabs.addTab(self.competitors_tab, "Competitors")

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

    def _setup_tray_icon(self) -> None:
        """Setup system tray icon."""
        self._tray_icon = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon(self)

        # Create a simple icon (would use a proper icon file in production)
        # For now, use the application icon if available
        app_icon = QApplication.instance().windowIcon()
        if not app_icon.isNull():
            self._tray_icon.setIcon(app_icon)
        else:
            # Fallback to a default icon
            self._tray_icon.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            ))

        # Create tray menu
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._show_from_tray)

        tray_menu.addSeparator()

        refresh_action = tray_menu.addAction("Toggle Refresh")
        refresh_action.triggered.connect(self.refresh_btn.click)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.setToolTip("Seller Opportunity Scanner")

        # Double-click to show
        self._tray_icon.activated.connect(self._on_tray_activated)

        self._tray_icon.show()

    def _show_from_tray(self) -> None:
        """Show window from tray."""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        # Tab navigation: Ctrl+1 through Ctrl+9
        for i in range(min(9, self.tabs.count())):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            shortcut.activated.connect(lambda idx=i: self.tabs.setCurrentIndex(idx))

        # Refresh data: F5 or Ctrl+R
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh_all)
        refresh_shortcut2 = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut2.activated.connect(self._refresh_all)

        # Toggle refresh: Ctrl+Shift+R
        toggle_refresh = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        toggle_refresh.activated.connect(self.refresh_btn.click)

        # Export current tab: Ctrl+E
        export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        export_shortcut.activated.connect(self._export_current_tab)

        # Search focus: Ctrl+F
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self._focus_search)

    def _refresh_all(self) -> None:
        """Refresh all data."""
        for brand in Brand:
            self._refresh_brand_tab(brand)
        self.mappings_tab.refresh_data()
        self.dashboard_tab.refresh_data()
        self.status_bar.showMessage("Data refreshed", 3000)

    def _export_current_tab(self) -> None:
        """Export data from current brand tab if applicable."""
        current = self.tabs.currentWidget()
        for brand_name, tab in self.brand_tabs.items():
            if current == tab:
                tab._on_export()
                return
        self.status_bar.showMessage("Export not available for this tab", 3000)

    def _focus_search(self) -> None:
        """Focus the search/filter input in current brand tab."""
        current = self.tabs.currentWidget()
        for brand_name, tab in self.brand_tabs.items():
            if current == tab and hasattr(tab, 'filter_input'):
                tab.filter_input.setFocus()
                tab.filter_input.selectAll()
                return

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
        self.dashboard_tab.refresh_data()

    def _refresh_brand_tab(self, brand: Brand) -> None:
        """Refresh data for a brand tab."""
        tab = self.brand_tabs.get(brand.value)
        if not tab:
            return

        # Get all active candidates with latest scores
        candidates = self._repo.get_candidates_by_brand(brand, active_only=True)

        results: list[ScoreResult] = []
        titles: dict[str, str] = {}
        profit_history: dict[int, list[float]] = {}  # candidate_id -> list of profits

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

                        # Get profit history for sparkline (last 20 records)
                        history = self._repo.get_score_history(candidate.id, limit=20)
                        if history:
                            # Extract profit values, oldest first
                            profits = [float(h.profit_net) for h in reversed(history)]
                            profit_history[candidate.id] = profits

        tab.update_results(results, titles, profit_history)

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
        self._refresh_controller.alert_triggered.connect(self._on_alert_triggered)

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

        # Refresh all brand tabs and dashboard
        for brand in Brand:
            self._refresh_brand_tab(brand)
        self.dashboard_tab.refresh_data()

    def _on_refresh_error(self, error: str) -> None:
        """Handle refresh error."""
        self.status_bar.showMessage(f"Error: {error}")
        self.diagnostics_tab.append_log(f"ERROR: {error}")

    def _on_refresh_log(self, message: str) -> None:
        """Handle refresh log message."""
        self.diagnostics_tab.append_log(message)

    def _on_alert_triggered(self, alert: Alert) -> None:
        """Handle a new alert from the refresh worker."""
        self._alert_count += 1
        self.alert_label.setText(f"🔔 {self._alert_count}")
        self.alert_label.setStyleSheet("color: #dc3545; font-weight: bold;")  # Red when alerts
        self.alert_label.setToolTip(f"Latest: {alert.message}")

        # Log the alert
        self.diagnostics_tab.append_log(f"ALERT: {alert.message}")

        # Show in status bar
        self.status_bar.showMessage(f"Alert: {alert.message}", 5000)

        # Show tray notification
        if self._tray_icon and self._settings.alerts.show_notification:
            self._tray_icon.showMessage(
                "Seller Opportunity Scanner",
                alert.message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

        # Optional: play system sound
        if self._settings.alerts.play_sound:
            try:
                QApplication.beep()
            except Exception:
                pass  # Ignore sound errors

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

    def _check_for_updates_on_startup(self) -> None:
        """Check for updates when app starts (silent, non-blocking)."""
        if not self._settings.check_updates_on_startup:
            return

        self._updater = Updater()
        self._updater.check_for_updates_async(
            on_update=self._on_update_available,
            on_error=lambda e: logger.debug(f"Update check failed: {e}"),
        )

    def _on_check_updates(self) -> None:
        """Handle manual update check."""
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Checking...")
        self.status_bar.showMessage("Checking for updates...")

        self._updater = Updater()
        self._updater.check_for_updates_async(
            on_update=self._on_update_available,
            on_no_update=self._on_no_update,
            on_error=self._on_update_error,
        )

    def _on_update_available(self, update_info: UpdateInfo) -> None:
        """Handle update available notification."""
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Check Updates")

        # Update version label to show update available
        self.version_label.setText(f"v{get_current_version()} → v{update_info.version}")
        self.version_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 11px;")

        # Show dialog
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"A new version is available!\n\n"
            f"Current: v{get_current_version()}\n"
            f"Latest: v{update_info.version}\n\n"
            f"Release notes:\n{update_info.release_notes[:500]}...\n\n"
            f"Would you like to open the download page?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes:
            Updater.open_download_page(update_info.download_url or Updater.get_github_releases_url())

    def _on_no_update(self) -> None:
        """Handle no update available."""
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Check Updates")
        self.status_bar.showMessage("You're running the latest version!", 5000)

    def _on_update_error(self, error: str) -> None:
        """Handle update check error."""
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Check Updates")
        self.status_bar.showMessage(f"Update check failed: {error}", 5000)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Stop refresh
        if self._refresh_controller:
            self._refresh_controller.stop()

        event.accept()
