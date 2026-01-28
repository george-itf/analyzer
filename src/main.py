"""Main entry point for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.config import get_config_dir, get_settings
from src.db.session import init_database


def setup_exception_handler() -> None:
    """Set up global exception handler for unhandled exceptions."""
    logger = logging.getLogger(__name__)

    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow Ctrl+C to exit normally
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Log the exception
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        # Show error dialog if QApplication exists
        app = QApplication.instance()
        if app:
            QMessageBox.critical(
                None,
                "Unexpected Error",
                f"An unexpected error occurred:\n\n{exc_value}\n\nSee log file for details.",
            )

    sys.excepthook = handle_exception


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
    setup_exception_handler()
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

    # Set application-wide stylesheet based on theme preference
    from src.gui.themes import get_theme_stylesheet
    app.setStyleSheet(get_theme_stylesheet(settings.dark_mode))

    # Create and show main window
    from src.gui.main_window import MainWindow

    window = MainWindow(settings)
    window.show()

    logger.info("Application started")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
