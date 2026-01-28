"""Tests for Keepa API client."""

from __future__ import annotations

import pytest

from src.core.models import TokenStatus
from src.api.keepa import KeepaClient
from src.core.config import Settings


class TestKeepaTokenLogic:
    """Tests for Keepa token management."""

    def test_can_make_request_before_any_calls(self):
        """Test that can_make_request returns True before any API calls.
        
        This is important because we don't know the actual token count
        until we make a request - we should try and let the API tell us.
        """
        settings = Settings()
        settings.api.mock_mode = True
        client = KeepaClient(settings)
        
        # Before any requests, last_updated is None
        assert client.token_status.last_updated is None
        
        # Should allow request even though tokens_left is 0
        assert client.can_make_request(20) is True

    def test_can_make_request_after_status_updated(self):
        """Test can_make_request after token status is manually set."""
        settings = Settings()
        settings.api.mock_mode = True
        client = KeepaClient(settings)
        
        # Simulate token status being updated from an API response
        from datetime import datetime
        client._token_status = TokenStatus(
            tokens_left=100,
            refill_rate=20,
            refill_in_seconds=60,
            last_updated=datetime.now(),
        )
        
        # Should allow request when we have enough tokens
        assert client.can_make_request(50) is True
        
        # Should deny when we don't have enough
        assert client.can_make_request(200) is False

    def test_wait_for_tokens_initial_state(self):
        """Test wait_for_tokens returns 0 when status unknown."""
        settings = Settings()
        settings.api.mock_mode = True
        client = KeepaClient(settings)
        
        # Before any requests, should not wait
        wait_time = client.wait_for_tokens(20)
        assert wait_time == 0.0
