# backend/config.py
from __future__ import annotations
import json
import logging
import os
import re
from pathlib import Path
from functools import lru_cache
from typing import TypeVar

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Load .env from backend/ directory — do this BEFORE anything else
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, override=True)


class Settings:
    """Simple settings class that reads from environment variables."""

    def __init__(self):
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
        self.exa_api_key: str = os.getenv("EXA_API_KEY", "")
        self.serper_api_key: str = os.getenv("SERPER_API_KEY", "")
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.llm_provider: str = "openrouter"
        self.llm_model: str = os.getenv("LLM_MODEL", "deepseek/deepseek-v3.2")
        self.chat_model: str = os.getenv("CHAT_MODEL", "deepseek/deepseek-chat")
        self.extraction_model: str = os.getenv("EXTRACTION_MODEL", "google/gemini-3-flash-preview")
        self.diffbot_api_key: str = os.getenv("DIFFBOT_API_KEY", "")
        self.cache_dir: str = os.getenv("CACHE_DIR", "cache")
        self.langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


from langchain_openai import ChatOpenAI


def get_llm(model: str | None = None, timeout: float = 120):
    """Create a ChatOpenAI instance for OpenRouter.

    Args:
        model: Override model name. Defaults to settings.llm_model (prose/reasoning).
               Use settings.extraction_model for structured JSON extraction tasks.
        timeout: Request timeout in seconds. Default 120s for pipeline,
                 use 15s for quick validation calls.

    Returns a new instance each call — construction is cheap (~1ms) after
    the module-level import, and separate instances are thread-safe for
    parallel pipeline nodes.
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    model = model or settings.llm_model
    # NOTE: ChatOpenAI renames max_tokens → max_completion_tokens in the
    # payload, which OpenRouter doesn't recognise.  Passing it via extra_body
    # ensures the raw "max_tokens" key reaches the provider.
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        extra_body={"max_tokens": 16384},
        request_timeout=timeout,
    )


def _strip_fences(text: str) -> str:
    """Remove markdown code fences and extract JSON from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text
    # If text doesn't start with { or [, try to extract embedded JSON
    if text and text[0] not in ('{', '['):
        # Look for a JSON object or array within the text
        start = text.find('{')
        if start == -1:
            start = text.find('[')
        if start != -1:
            # Find the matching closing bracket from the end
            for end in range(len(text) - 1, start, -1):
                if text[end] in ('}', ']'):
                    return text[start:end + 1]
    return text


def _repair_truncated_json(text: str) -> str:
    """Best-effort repair of JSON truncated by token limit.

    Strips any trailing incomplete string/value, then closes open
    brackets and braces so the JSON can be parsed.
    """
    # Remove trailing incomplete string (unmatched quote)
    # Walk the text to find if we're inside a string
    in_string = False
    escape = False
    last_quote = -1
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            if in_string:
                last_quote = i

    if in_string and last_quote >= 0:
        # Truncated mid-string — close the string
        text = text + '"'

    # Remove trailing comma or colon (invalid before closing)
    text = re.sub(r'[,:\s]+$', '', text)

    # Count open/close brackets and braces
    opens = []
    in_str = False
    esc = False
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == '\\' and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ('{', '['):
            opens.append(ch)
        elif ch == '}' and opens and opens[-1] == '{':
            opens.pop()
        elif ch == ']' and opens and opens[-1] == '[':
            opens.pop()

    # Close remaining open brackets/braces in reverse order
    for bracket in reversed(opens):
        text += ']' if bracket == '[' else '}'

    return text


def invoke_structured(llm, schema: type[T], messages: list) -> T:
    """Call LLM with structured output, with fence-stripping fallback.

    Tries with_structured_output first (json_schema mode). If parsing fails
    due to markdown fences in the response, falls back to raw invoke +
    manual JSON parsing.
    """
    try:
        structured_llm = llm.with_structured_output(schema)
        return structured_llm.invoke(messages)
    except Exception as first_err:
        # Check if this is a recoverable parsing/format error worth retrying
        # with manual JSON parsing. Non-recoverable errors (auth, rate limit,
        # model not found, content blocked) should propagate immediately.
        # Pydantic ValidationErrors are always recoverable (LLM returned wrong format).
        from pydantic import ValidationError as _PydanticVE
        if isinstance(first_err, _PydanticVE):
            is_recoverable = True
        else:
            err_str = str(first_err).lower()
            non_recoverable = (
                "auth" in err_str
                or "api key" in err_str
                or "rate limit" in err_str
                or "429" in err_str
                or "model not found" in err_str
                or "content filter" in err_str
                or "content_policy" in err_str
                or "safety" in err_str
                or "timeout" in err_str
                or "timed out" in err_str
            )
            is_recoverable = not non_recoverable
        if not is_recoverable:
            raise

        logger.warning("Structured output failed, retrying with manual parsing: %s", first_err)

        # Fallback: raw invoke with explicit JSON instruction + strip fences + parse
        json_schema = schema.model_json_schema()
        fallback_messages = list(messages) + [
            HumanMessage(content=(
                "IMPORTANT: Respond ONLY with valid JSON matching this schema, "
                "no markdown, no explanations:\n"
                + json.dumps(json_schema, indent=2)
            ))
        ]
        response = llm.invoke(fallback_messages)
        text = _strip_fences(response.content)
        try:
            return schema.model_validate_json(text)
        except Exception:
            # Response may be truncated by token limit — try repair
            logger.warning("JSON parse failed, attempting truncated JSON repair")
            repaired = _repair_truncated_json(text)
            return schema.model_validate_json(repaired)
