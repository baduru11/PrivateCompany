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
        "GEMINI_API_KEY": "test-gemini-key",
        "TAVILY_API_KEY": "test-tavily-key",
        "EXA_API_KEY": "test-exa-key",
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "LLM_PROVIDER": "openai",
        "CACHE_DIR": "/tmp/test_cache",
    }
    with patch.dict(os.environ, env, clear=False):
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.gemini_api_key == "test-gemini-key"
        assert settings.tavily_api_key == "test-tavily-key"
        assert settings.exa_api_key == "test-exa-key"
        assert settings.openai_api_key == "test-openai-key"
        assert settings.anthropic_api_key == "test-anthropic-key"
        assert settings.llm_provider == "openai"
        assert settings.cache_dir == "/tmp/test_cache"


def test_settings_defaults():
    """Settings should have sensible defaults when env vars are not set."""
    # Ensure the relevant env vars are absent
    keys_to_remove = [
        "GEMINI_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER", "CACHE_DIR",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.gemini_api_key == ""
        assert settings.llm_provider == "gemini"
        assert settings.cache_dir == "cache"


def test_get_llm_raises_for_missing_gemini_key():
    """get_llm should raise ValueError when gemini key is missing."""
    keys_to_remove = [
        "GEMINI_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_llm, get_settings
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="GEMINI_API_KEY not set"):
            get_llm("gemini")


def test_get_llm_raises_for_missing_openai_key():
    """get_llm should raise ValueError when openai key is missing."""
    keys_to_remove = [
        "GEMINI_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_llm, get_settings
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
            get_llm("openai")


def test_get_llm_raises_for_missing_anthropic_key():
    """get_llm should raise ValueError when anthropic key is missing."""
    keys_to_remove = [
        "GEMINI_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_llm, get_settings
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not set"):
            get_llm("anthropic")


def test_get_llm_raises_for_unknown_provider():
    """get_llm should raise ValueError for an unsupported provider name."""
    from backend.config import get_llm, get_settings
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="Unknown LLM provider: not_a_provider"):
        get_llm("not_a_provider")


def test_get_llm_uses_default_provider():
    """get_llm with no argument should fall back to settings.llm_provider."""
    keys_to_remove = [
        "GEMINI_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER",
    ]
    cleaned_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
    with patch.dict(os.environ, cleaned_env, clear=True):
        from backend.config import get_llm, get_settings
        get_settings.cache_clear()
        # Default provider is gemini, and no key is set, so it should raise
        with pytest.raises(ValueError, match="GEMINI_API_KEY not set"):
            get_llm()
