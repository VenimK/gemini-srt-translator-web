"""Test configuration and fixtures."""
import pytest
from unittest.mock import MagicMock, patch

# Mock Google Generative AI before any tests run
mock_genai = MagicMock()
mock_model = MagicMock()
mock_genai.GenerativeModel.return_value = mock_model
mock_model.generate_content.return_value.text = "Mocked translation"

# Apply the mock to the google.generativeai module
import sys
sys.modules['google.generativeai'] = mock_genai

@pytest.fixture
def mock_file_operations():
    """Mock file operations for tests."""
    with patch('shutil.copyfileobj'), \
         patch('os.makedirs'), \
         patch('pathlib.Path.mkdir'), \
         patch('builtins.open', MagicMock()):
        yield

@pytest.fixture
def mock_config():
    """Mock configuration for tests."""
    with patch('main.config_manager.config_manager.get_config', return_value={
        "gemini_api_key": "test_key",
        "model": "gemini-pro",
        "language": "English",
        "language_code": "en"
    }):
        yield

@pytest.fixture
def mock_models():
    """Mock model listing for tests."""
    with patch('main.Translator.get_models', return_value=["gemini-pro"]):
        yield
