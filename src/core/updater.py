"""Auto-update functionality for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Current version
__version__ = "1.0.0"

# GitHub repository info (update these for your repo)
GITHUB_OWNER = "your-username"
GITHUB_REPO = "seller-opportunity-scanner"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: str
    release_date: datetime
    release_notes: str
    download_url: str
    is_newer: bool

    @property
    def version_tuple(self) -> tuple[int, ...]:
        """Parse version string to tuple for comparison."""
        try:
            return tuple(int(x) for x in self.version.lstrip("v").split("."))
        except ValueError:
            return (0, 0, 0)


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string to tuple."""
    try:
        return tuple(int(x) for x in version_str.lstrip("v").split("."))
    except ValueError:
        return (0, 0, 0)


def is_newer_version(current: str, latest: str) -> bool:
    """Check if latest version is newer than current."""
    return parse_version(latest) > parse_version(current)


class UpdateChecker(QObject):
    """Background worker to check for updates."""

    # Signals
    update_available = pyqtSignal(object)  # UpdateInfo
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)  # error message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_version = __version__

    def check_for_updates(self) -> None:
        """Check GitHub for latest release."""
        try:
            response = requests.get(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10,
            )

            if response.status_code == 404:
                # No releases yet
                self.no_update.emit()
                return

            response.raise_for_status()
            data = response.json()

            latest_version = data.get("tag_name", "").lstrip("v")
            release_date_str = data.get("published_at", "")
            release_notes = data.get("body", "")

            # Find download URL for macOS
            download_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if "mac" in name or "darwin" in name or name.endswith(".dmg") or name.endswith(".app.zip"):
                    download_url = asset.get("browser_download_url", "")
                    break

            # If no macOS-specific asset, use the zipball
            if not download_url:
                download_url = data.get("zipball_url", "")

            # Parse release date
            try:
                release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                release_date = datetime.now()

            is_newer = is_newer_version(self._current_version, latest_version)

            update_info = UpdateInfo(
                version=latest_version,
                release_date=release_date,
                release_notes=release_notes,
                download_url=download_url,
                is_newer=is_newer,
            )

            if is_newer:
                logger.info(f"Update available: {latest_version} (current: {self._current_version})")
                self.update_available.emit(update_info)
            else:
                logger.info(f"No update available. Current: {self._current_version}, Latest: {latest_version}")
                self.no_update.emit()

        except requests.RequestException as e:
            error_msg = f"Failed to check for updates: {e}"
            logger.warning(error_msg)
            self.check_failed.emit(error_msg)
        except Exception as e:
            error_msg = f"Update check error: {e}"
            logger.exception(error_msg)
            self.check_failed.emit(error_msg)


class UpdateCheckerThread(QThread):
    """Thread wrapper for update checking."""

    update_available = pyqtSignal(object)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    def run(self) -> None:
        """Run the update check in background."""
        checker = UpdateChecker()
        checker.update_available.connect(self.update_available)
        checker.no_update.connect(self.no_update)
        checker.check_failed.connect(self.check_failed)
        checker.check_for_updates()


class Updater:
    """Manages the update process."""

    def __init__(self) -> None:
        self.current_version = __version__
        self._checker_thread: UpdateCheckerThread | None = None

    def check_for_updates_async(
        self,
        on_update: callable | None = None,
        on_no_update: callable | None = None,
        on_error: callable | None = None,
    ) -> None:
        """Check for updates in background thread."""
        self._checker_thread = UpdateCheckerThread()

        if on_update:
            self._checker_thread.update_available.connect(on_update)
        if on_no_update:
            self._checker_thread.no_update.connect(on_no_update)
        if on_error:
            self._checker_thread.check_failed.connect(on_error)

        self._checker_thread.start()

    def check_for_updates_sync(self) -> UpdateInfo | None:
        """Check for updates synchronously. Returns UpdateInfo if available."""
        checker = UpdateChecker()
        result: list[UpdateInfo | None] = [None]

        def on_update(info: UpdateInfo) -> None:
            result[0] = info

        checker.update_available.connect(on_update)
        checker.check_for_updates()

        return result[0]

    @staticmethod
    def open_download_page(url: str) -> bool:
        """Open the download page in the default browser."""
        import webbrowser

        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            logger.error(f"Failed to open download page: {e}")
            return False

    @staticmethod
    def get_github_releases_url() -> str:
        """Get the GitHub releases page URL."""
        return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


def get_current_version() -> str:
    """Get the current application version."""
    return __version__
