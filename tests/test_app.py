import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint returns the index.html page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_upload_endpoint():
    """Test the upload endpoint with a test file."""
    test_file = {"files": ("test.srt", b"1\n00:00:01,000 --> 00:00:04,000\nHello world\n")}
    response = client.post("/upload_files/", files=test_file)
    assert response.status_code in [200, 422]  # 200 if successful, 422 if validation fails

def test_config_endpoint():
    """Test the config endpoint."""
    response = client.get("/config/")
    assert response.status_code == 200
    assert "gemini_api_key" in response.json()

def test_models_endpoint():
    """Test the models endpoint."""
    response = client.get("/models/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)  # Should return a list of models
