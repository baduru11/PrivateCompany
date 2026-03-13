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
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
        self.exa_api_key: str = os.getenv("EXA_API_KEY", "")
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.llm_provider: str = "openrouter"
        self.llm_model: str = os.getenv("LLM_MODEL", "deepseek/deepseek-v3.2")
        self.cache_dir: str = os.getenv("CACHE_DIR", "cache")
        self.langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_llm():
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
    )
