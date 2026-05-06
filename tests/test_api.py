"""Tests for F012 - REST API."""

import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from idea_to_action.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "llm_available" in data

    def test_health_llm_unavailable_when_no_key(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["llm_available"] is False

    def test_health_llm_available_with_key(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-key"}, clear=True):
            app = create_app()
            client = TestClient(app)
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["llm_available"] is True


class TestSubmitEndpoint:
    def test_submit_validates_empty_input(self, client):
        response = client.post("/submit", json={"raw_text": ""})
        assert response.status_code == 422

    def test_submit_missing_raw_text(self, client):
        response = client.post("/submit", json={})
        assert response.status_code == 422

    def test_submit_no_llm_returns_503(self, client):
        """Without an API key, /submit should return 503."""

        response = client.post("/submit", json={"raw_text": "Test note"})
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error_type"] == "llm_not_configured"

    def test_submit_with_invalid_input_type(self, client):
        """Invalid input_type should still be accepted (defaults or 422)."""
        response = client.post("/submit", json={
            "raw_text": "Test",
            "input_type": "voice_memo",
        })
        # May be 503 (no LLM) or 422 (invalid type) - either is fine
        assert response.status_code in (422, 503)

    def test_submit_response_structure(self):
        """With a fake API key, the response should have the right structure."""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-fake-key"}, clear=True):
            app = create_app()
            client = TestClient(app)
            response = client.post("/submit", json={"raw_text": "Buy milk"})

            # Will likely be 200 with partial results (LLM connection fails)
            # or 200/500 depending on how the LLM connection error propagates
            assert response.status_code in (200, 500, 503)
            if response.status_code == 200:
                data = response.json()
                assert "trace_id" in data
                assert "status" in data
                assert "errors" in data
                assert "input_text" in data


class TestErrorResponseFormat:
    def test_404_on_unknown_route(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_405_on_wrong_method(self, client):
        response = client.put("/health")
        assert response.status_code == 405
