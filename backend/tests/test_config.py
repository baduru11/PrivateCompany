# backend/tests/test_config.py
import os
import pytest
from unittest.mock import patch


def setup_function():
    """Clear lru_cache before each test to avoid stale settings."""
    from backend.config import get_settings
    get_settings.cache_clear()


def teardown_function():
    """Clear lru_cache after each test."""
    from backend.config import get_settings
    get_settings.cache_clear()


def test_settings_loads_env_vars():
    """Settings should pick up values from environment variables."""
    env = {
        "TAVILY_API_KEY": "test-tavily-key",
        "EXA_API_KEY": "test-exa-key",
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "CACHE_DIR": "/tmp/test_cache",
    }
    with patch.dict(os.environ, env, clear=False):
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.tavily_api_key == "test-tavily-key"
        assert settings.exa_api_key == "test-exa-key"
        assert settings.openrouter_api_key == "test-openrouter-key"
        assert settings.llm_provider == "openrouter"
        assert settings.cache_dir == "/tmp/test_cache"


def test_settings_defaults():
    """Settings should have sensible defaults when env vars are not set."""
    keys_to_remove = [
        "TAVILY_API_KEY", "EXA_API_KEY", "OPENROUTER_API_KEY", "CACHE_DIR",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.openrouter_api_key == ""
        assert settings.llm_provider == "openrouter"
        assert settings.cache_dir == "cache"


def test_get_llm_raises_for_missing_openrouter_key():
    """get_llm should raise ValueError when openrouter key is missing."""
    keys_to_remove = [
        "TAVILY_API_KEY", "EXA_API_KEY", "OPENROUTER_API_KEY",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_llm, get_settings
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY not set"):
            get_llm()


def test_settings_loads_llm_model():
    """Settings should pick up LLM_MODEL from environment."""
    env = {
        "LLM_MODEL": "openai/gpt-4o",
        "OPENROUTER_API_KEY": "test-key",
    }
    with patch.dict(os.environ, env, clear=False):
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.llm_model == "openai/gpt-4o"


def test_settings_defaults_llm_model():
    """LLM_MODEL should default to deepseek."""
    keys_to_remove = ["LLM_MODEL"]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.llm_model == "deepseek/deepseek-v3.2"
