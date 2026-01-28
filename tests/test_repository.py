
class TestTokenUsageStats:
    """Tests for token usage statistics."""

    def test_get_token_usage_stats_empty(self):
        """Test token stats with no data."""
        from src.db.repository import Repository
        repo = Repository()
        stats = repo.get_token_usage_stats(24)
        
        assert "total_tokens" in stats
        assert "total_calls" in stats
        assert "success_count" in stats
        assert stats["total_tokens"] == 0
