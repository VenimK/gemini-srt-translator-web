import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_health():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_upload_endpoint():
    """Test the upload endpoint with a test file."""
    test_file = {"file": ("test.srt", b"1\n00:00:01,000 --> 00:00:04,000\nHello world\n")}
    response = client.post("/upload", files=test_file)
    assert response.status_code in [200, 422]  # 200 if auth is set, 422 if not

def test_config_endpoint():
    """Test the config endpoint."""
    response = client.get("/config/")
    assert response.status_code == 200
    assert "gemini_api_key" in response.json()
