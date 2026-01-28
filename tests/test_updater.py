"""Tests for the auto-update functionality."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.core.updater import (
    UpdateInfo,
    UpdateChecker,
    Updater,
    get_current_version,
    is_newer_version,
    parse_version,
)


class TestVersionParsing:
    """Tests for version parsing utilities."""

    def test_parse_version_simple(self):
        """Test parsing simple version string."""
        assert parse_version("1.0.0") == (1, 0, 0)

    def test_parse_version_with_v_prefix(self):
        """Test parsing version with 'v' prefix."""
        assert parse_version("v1.2.3") == (1, 2, 3)

    def test_parse_version_two_parts(self):
        """Test parsing two-part version."""
        assert parse_version("2.1") == (2, 1)

    def test_parse_version_invalid(self):
        """Test parsing invalid version returns (0, 0, 0)."""
        assert parse_version("invalid") == (0, 0, 0)

    def test_is_newer_version_true(self):
        """Test detecting newer version."""
        assert is_newer_version("1.0.0", "1.1.0") is True
        assert is_newer_version("1.0.0", "2.0.0") is True
        assert is_newer_version("1.0.0", "1.0.1") is True

    def test_is_newer_version_false(self):
        """Test detecting same or older version."""
        assert is_newer_version("1.0.0", "1.0.0") is False
        assert is_newer_version("2.0.0", "1.0.0") is False
        assert is_newer_version("1.1.0", "1.0.0") is False

    def test_is_newer_version_with_v_prefix(self):
        """Test version comparison with 'v' prefix."""
        assert is_newer_version("v1.0.0", "v1.1.0") is True
        assert is_newer_version("1.0.0", "v1.1.0") is True


class TestUpdateInfo:
    """Tests for UpdateInfo dataclass."""

    def test_version_tuple(self):
        """Test version_tuple property."""
        info = UpdateInfo(
            version="1.2.3",
            release_date=datetime.now(),
            release_notes="Test",
            download_url="http://example.com",
            is_newer=True,
        )
        assert info.version_tuple == (1, 2, 3)

    def test_version_tuple_with_prefix(self):
        """Test version_tuple with 'v' prefix."""
        info = UpdateInfo(
            version="v2.0.0",
            release_date=datetime.now(),
            release_notes="Test",
            download_url="http://example.com",
            is_newer=True,
        )
        assert info.version_tuple == (2, 0, 0)


class TestUpdateChecker:
    """Tests for UpdateChecker."""

    def test_check_no_releases(self, qtbot):
        """Test handling when no releases exist."""
        checker = UpdateChecker()
        
        with patch('src.core.updater.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            no_update_received = []
            checker.no_update.connect(lambda: no_update_received.append(True))
            
            checker.check_for_updates()
            
            assert len(no_update_received) == 1

    def test_check_update_available(self, qtbot):
        """Test detecting available update."""
        checker = UpdateChecker()
        checker._current_version = "1.0.0"
        
        with patch('src.core.updater.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "tag_name": "v2.0.0",
                "published_at": "2024-01-01T00:00:00Z",
                "body": "New features",
                "assets": [],
                "zipball_url": "http://example.com/zip",
            }
            mock_get.return_value = mock_response
            
            update_received = []
            checker.update_available.connect(lambda info: update_received.append(info))
            
            checker.check_for_updates()
            
            assert len(update_received) == 1
            assert update_received[0].version == "2.0.0"
            assert update_received[0].is_newer is True

    def test_check_no_update_same_version(self, qtbot):
        """Test when current version is latest."""
        checker = UpdateChecker()
        checker._current_version = "1.0.0"
        
        with patch('src.core.updater.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "tag_name": "v1.0.0",
                "published_at": "2024-01-01T00:00:00Z",
                "body": "Current version",
                "assets": [],
            }
            mock_get.return_value = mock_response
            
            no_update_received = []
            checker.no_update.connect(lambda: no_update_received.append(True))
            
            checker.check_for_updates()
            
            assert len(no_update_received) == 1

    def test_check_network_error(self, qtbot):
        """Test handling network errors."""
        import requests
        
        checker = UpdateChecker()
        
        with patch('src.core.updater.requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")
            
            error_received = []
            checker.check_failed.connect(lambda msg: error_received.append(msg))
            
            checker.check_for_updates()
            
            assert len(error_received) == 1
            assert "Network error" in error_received[0]


class TestUpdater:
    """Tests for Updater class."""

    def test_current_version(self):
        """Test getting current version."""
        updater = Updater()
        assert updater.current_version == get_current_version()

    def test_get_current_version_function(self):
        """Test get_current_version function."""
        version = get_current_version()
        assert isinstance(version, str)
        assert "." in version  # Should be semver format

    def test_github_releases_url(self):
        """Test getting GitHub releases URL."""
        url = Updater.get_github_releases_url()
        assert "github.com" in url
        assert "releases" in url
