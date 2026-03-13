# backend/tests/test_sse.py
"""Tests for SSE streaming endpoints using fixture/cached queries."""
import json
import pytest

try:
    from fastapi.testclient import TestClient
    from backend.main import app
    HAS_TEST_CLIENT = True
except ImportError:
    HAS_TEST_CLIENT = False

pytestmark = pytest.mark.skipif(not HAS_TEST_CLIENT, reason="starlette/httpx not installed")


@pytest.fixture
def client():
    return TestClient(app)


class TestSSEFixtureQueries:
    """Test SSE behavior for fixture (offline demo) queries which return cached JSON."""

    def test_fixture_query_returns_json_not_sse(self, client):
        """Fixture queries should return immediate JSON, not SSE stream."""
        resp = client.post("/api/query", json={"query": "Nvidia", "mode": "deep_dive"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True
        assert "data" in data

    def test_fixture_explore_returns_json(self, client):
        """Explore fixture queries should return immediate JSON."""
        resp = client.post("/api/query", json={"query": "AI inference chips", "mode": "explore"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True


class TestSSEValidation:
    """Test validation behavior on /api/query endpoint."""

    def test_empty_query_rejected(self, client):
        """Empty query should be rejected with 422."""
        resp = client.post("/api/query", json={"query": "", "mode": "explore"})
        assert resp.status_code == 422

    def test_short_query_rejected(self, client):
        """Very short query should be rejected by Tier 2 validation."""
        resp = client.post("/api/query", json={"query": "ab", "mode": "explore"})
        assert resp.status_code == 422

    def test_invalid_mode_rejected(self, client):
        """Invalid mode should be rejected."""
        resp = client.post("/api/query", json={"query": "test query", "mode": "invalid"})
        assert resp.status_code == 422


class TestHistoryEndpoint:
    """Test history and report CRUD endpoints."""

    def test_history_returns_list(self, client):
        """GET /api/history should return a list."""
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_missing_report_returns_404(self, client):
        """GET /api/report/{filename} for non-existent file returns 404."""
        resp = client.get("/api/report/nonexistent.json")
        assert resp.status_code == 404

    def test_delete_missing_report_returns_404(self, client):
        """DELETE /api/report/{filename} for non-existent file returns 404."""
        resp = client.delete("/api/report/nonexistent.json")
        assert resp.status_code == 404
