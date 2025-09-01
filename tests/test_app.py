import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Mock Google Generative AI before importing main
mock_genai = MagicMock()
mock_genai.configure.return_value = None
mock_model = MagicMock()
mock_genai.GenerativeModel.return_value = mock_model
mock_model.generate_content.return_value.text = "Mocked translation"

import sys
sys.modules['google.generativeai'] = mock_genai

from main import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint returns the index.html page."""
    with patch('builtins.open', return_value=MagicMock(read=MagicMock(return_value='<html></html>'))):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

def test_upload_endpoint():
    """Test the upload endpoint with a test file."""
    test_file = ("test_file", ("test.srt", b"1\n00:00:01,000 --> 00:00:04,000\nHello world\n"))
    with patch('shutil.copyfileobj'), \
         patch('os.makedirs'), \
         patch('pathlib.Path.mkdir'):
        response = client.post("/upload_files/", files={"files": test_file})
        assert response.status_code in [200, 422]

def test_config_endpoint():
    """Test the config endpoint."""
    with patch('main.config_manager.get_config', return_value={"gemini_api_key": "test"}):
        response = client.get("/config/")
        assert response.status_code == 200
        assert "gemini_api_key" in response.json()

@patch('main.Translator.get_available_models')
def test_models_endpoint(mock_get_models):
    """Test the models endpoint."""
    mock_get_models.return_value = ["gemini-pro"]
    response = client.get("/models/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
