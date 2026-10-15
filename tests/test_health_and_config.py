import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings


def test_health_endpoint():
    """Verify that /health returns ok: true per contract."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_config_model_defaults():
    """Verify default verified models are populated."""
    assert "llama-3.3" in settings.groq_model
    assert "nemotron" in settings.nvidia_model
