"""Tests for web dashboard."""

from __future__ import annotations

import pytest

from src.web.server import WebServer, create_app


class TestWebServer:
    """Tests for WebServer class."""

    def test_server_creation(self):
        """Test WebServer can be created."""
        server = WebServer(host="127.0.0.1", port=5051)
        assert server.host == "127.0.0.1"
        assert server.port == 5051
        assert server.is_running is False

    def test_url_generation(self):
        """Test URL is generated correctly."""
        server = WebServer(port=5050)
        url = server.url
        assert ":5050" in url
        assert url.startswith("http://")


class TestFlaskApp:
    """Tests for Flask application routes."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_index_route(self, client):
        """Test index route returns HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Seller Opportunity Scanner" in response.data

    def test_api_summary(self, client):
        """Test API summary endpoint."""
        response = client.get("/api/summary")
        assert response.status_code == 200

        data = response.get_json()
        assert "total_items" in data
        assert "opportunities" in data
        assert "brands" in data

    def test_api_top(self, client):
        """Test API top opportunities endpoint."""
        response = client.get("/api/top")
        assert response.status_code == 200

        data = response.get_json()
        assert "items" in data
        assert "count" in data

    def test_api_score_distribution(self, client):
        """Test API score distribution endpoint."""
        response = client.get("/api/score-distribution")
        assert response.status_code == 200

        data = response.get_json()
        assert "buckets" in data
        assert len(data["buckets"]) == 5

    def test_api_brand_scores_valid(self, client):
        """Test API brand scores endpoint with valid brand."""
        response = client.get("/api/scores/Makita")
        assert response.status_code == 200

        data = response.get_json()
        assert data["brand"] == "Makita"
        assert "items" in data

    def test_api_brand_scores_invalid(self, client):
        """Test API brand scores endpoint with invalid brand."""
        response = client.get("/api/scores/InvalidBrand")
        assert response.status_code == 404
