#!/usr/bin/env python
"""Integration test script - verifies all components work together."""

from __future__ import annotations

import sys


def main() -> int:
    """Run integration tests."""
    from decimal import Decimal

    from PyQt6.QtWidgets import QApplication

    from src.core.alerts import AlertManager
    from src.core.competitors import CompetitorOffer, CompetitorSnapshot, CompetitorTracker
    from src.core.config import AlertConfig, Settings
    from src.core.scoring import ScoringEngine
    from src.core.scheduler import RefreshController, RefreshWorker
    from src.core.updater import Updater
    from src.db.session import close_database, init_database
    from src.gui.brand_tab import BrandTab
    from src.gui.competitors_tab import CompetitorsTab
    from src.gui.dashboard_tab import DashboardTab
    from src.gui.main_window import MainWindow
    from src.gui.settings_tab import SettingsTab
    from src.gui.themes import get_theme_stylesheet

    # Test database init with migrations
    print("Testing database initialization...")
    init_database(use_migrations=True)
    print("✓ Database initialized")

    # Test settings
    print("Testing settings...")
    settings = Settings()
    print("✓ Settings loaded")

    print("✓ Core modules imported")

    # Test GUI creation (headless)
    print("Testing GUI creation...")
    app = QApplication(sys.argv)
    window = MainWindow()
    print(f"✓ MainWindow created with {window.tabs.count()} tabs")

    # Check all tabs exist
    tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    print(f"  Tabs: {tab_names}")

    # Check expected tabs are present
    expected = ["Dashboard", "Competitors", "Settings", "Diagnostics"]
    all_present = True
    for tab in expected:
        if tab in tab_names:
            print(f"  ✓ {tab} tab present")
        else:
            print(f"  ✗ {tab} tab MISSING")
            all_present = False

    # Test updater
    print("Testing updater...")
    updater = Updater()
    print(f"✓ Updater ready (current version: {updater.current_version})")

    # Test competitor tracker
    print("Testing competitor tracker...")
    tracker = CompetitorTracker()
    offer = CompetitorOffer(seller_id="TEST", price=Decimal("10.00"))
    snapshot = CompetitorSnapshot(asin="B001TEST", offers=[offer])
    tracker.add_snapshot(snapshot)
    print(f"✓ Competitor tracker working ({len(tracker.get_all_asins())} ASINs)")

    # Test alerts
    print("Testing alert manager...")
    alert_config = AlertConfig()
    alert_mgr = AlertManager(alert_config)
    print("✓ Alert manager ready")

    # Test theme
    print("Testing themes...")
    light = get_theme_stylesheet(dark_mode=False)
    dark = get_theme_stylesheet(dark_mode=True)
    print(f"✓ Themes working (light: {len(light)} chars, dark: {len(dark)} chars)")

    # Cleanup
    close_database()
    print()

    if all_present:
        print("✅ All integration tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
