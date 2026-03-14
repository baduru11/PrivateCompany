# backend/nodes/chat.py
"""Chat endpoint logic: RAG retrieval + LLM streaming via OpenRouter."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tavily import TavilyClient

from backend.config import get_settings
from backend.rag import retrieve, store_web_results

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    report_id: str
    scope: str = "current"  # "current" or "all"
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)
    company_name: str = ""


# ---------------------------------------------------------------------------
# Web-search fallback
# ---------------------------------------------------------------------------

def _web_search_fallback(query: str) -> list[dict]:
    """Search the web via Tavily as a fallback when RAG results are weak."""
    try:
        settings = get_settings()
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query=query, max_results=5)
        results = []
        for r in response.get("results", []):
            results.append({
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            })
        return results
    except Exception as exc:
        logger.warning("Web search fallback failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(chunks: list[dict], used_web_search: bool) -> str:
    """Build a system prompt with numbered source context for the LLM."""
    source_block = ""
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source_url", "unknown")
        provider = chunk.get("provider", "")
        text = chunk.get("text", "")
        source_block += f"[{i}] ({provider}) {source}\n{text}\n\n"

    web_note = ""
    if used_web_search:
        web_note = (
            "\nNote: Some sources were obtained via live web search because "
            "the indexed data was insufficient.\n"
        )

    return (
        "You are a helpful research assistant for private company intelligence. "
        "Answer the user's question using ONLY the context provided below. "
        "Cite sources using [N] notation (e.g. [1], [2]). "
        "Be concise and factual. If the context does not contain enough "
        "information to answer, say so clearly.\n\n"
        f"--- CONTEXT ---\n{source_block}"
        f"{web_note}"
        "--- END CONTEXT ---"
    )


# ---------------------------------------------------------------------------
# Streaming chat generator
# ---------------------------------------------------------------------------

async def generate_chat_response(req: ChatRequest) -> AsyncGenerator[dict, None]:
    """Async generator that yields chat events (retrieval, tokens, sources, done)."""
    try:
        settings = get_settings()
        used_web_search = False

        # 1. Retrieve from ChromaDB (blocking — run in thread)
        rag_result = await asyncio.to_thread(
            retrieve,
            query=req.message,
            report_id=req.report_id,
            scope=req.scope,
        )

        # 2. If weak results, try web search fallback
        if rag_result["is_weak"]:
            fallback_query = f"{req.company_name} {req.message}" if req.company_name else req.message
            web_results = await asyncio.to_thread(_web_search_fallback, fallback_query)
            if web_results:
                used_web_search = True
                await asyncio.to_thread(store_web_results, req.report_id, req.company_name, web_results)
                # Re-retrieve after storing web results
                rag_result = await asyncio.to_thread(
                    retrieve,
                    query=req.message,
                    report_id=req.report_id,
                    scope=req.scope,
                )

        chunks = rag_result["chunks"]

        # 3. Yield retrieval metadata
        yield {
            "type": "retrieval",
            "chunk_count": len(chunks),
            "web_search": used_web_search,
        }

        # 4. If no chunks, yield a "no data" message and stop
        if not chunks:
            yield {
                "type": "token",
                "content": "I don't have enough data to answer this question. "
                           "Try running a research query first to index some data.",
            }
            yield {"type": "done"}
            return

        # 5. Build system prompt and messages
        system_prompt = _build_system_prompt(chunks, used_web_search)
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for msg in req.history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": req.message})

        # 6. Stream via OpenRouter
        client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=30.0,
        )
        model = settings.chat_model if hasattr(settings, "chat_model") else "deepseek/deepseek-chat"

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.3,
            max_tokens=1500,
        )

        try:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {
                        "type": "token",
                        "content": chunk.choices[0].delta.content,
                    }
        except Exception as stream_exc:
            logger.warning("Stream interrupted: %s", stream_exc)
            yield {"type": "error", "message": "Stream interrupted. Partial response may be incomplete."}

        # 7. Yield sources (unique source URLs)
        seen_urls: set[str] = set()
        unique_sources: list[str] = []
        for c in chunks:
            url = c.get("source_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(url)

        yield {"type": "sources", "sources": unique_sources}

        # 8. Done — always sent so frontend never hangs
        yield {"type": "done"}

    except Exception:
        logger.exception("Error in chat generation")
        yield {"type": "error", "message": "An error occurred while generating the response. Please try again."}
        yield {"type": "done"}
