# backend/config.py
from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

# Load .env from backend/ directory — do this BEFORE anything else
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, override=True)


class Settings:
    """Simple settings class that reads from environment variables."""

    def __init__(self):
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
        self.exa_api_key: str = os.getenv("EXA_API_KEY", "")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
        self.cache_dir: str = os.getenv("CACHE_DIR", "cache")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_llm(provider: str | None = None):
    settings = get_settings()
    provider = provider or settings.llm_provider

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
        )
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=0,
        )
    elif provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="deepseek/deepseek-v3.2",
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
