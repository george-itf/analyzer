"""Main entry point for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.core.config import get_config_dir, get_settings
from src.db.session import init_database


def setup_logging() -> None:
    """Configure application logging."""
    log_dir = get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "scanner.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    """Application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Seller Opportunity Scanner")

    # Load settings
    settings = get_settings()
    logger.info(f"Config dir: {get_config_dir()}")
    logger.info(f"Mock mode: {settings.api.mock_mode}")

    # Initialize database
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.exception("Failed to initialize database")
        print(f"Error: Failed to initialize database: {e}", file=sys.stderr)
        return 1

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Seller Opportunity Scanner")
    app.setOrganizationName("SellerTools")

    # Set application-wide stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QTabWidget::pane {
            border: 1px solid #ccc;
            background-color: white;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            border: 1px solid #ccc;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom-color: white;
        }
        QTabBar::tab:hover {
            background-color: #d0d0d0;
        }
        QTableView {
            gridline-color: #e0e0e0;
            selection-background-color: #cce5ff;
            selection-color: #000000;
        }
        QTableView::item {
            padding: 4px;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            padding: 6px;
            border: 1px solid #ddd;
            font-weight: bold;
        }
        QPushButton {
            background-color: #0d6efd;
            color: white;
            border: none;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0b5ed7;
        }
        QPushButton:pressed {
            background-color: #0a58ca;
        }
        QPushButton:disabled {
            background-color: #6c757d;
        }
        QPushButton:checked {
            background-color: #dc3545;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            padding: 4px 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
    """)

    # Create and show main window
    from src.gui.main_window import MainWindow

    window = MainWindow(settings)
    window.show()

    logger.info("Application started")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
