# Research Chat with RAG — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a chat interface to the Deep Dive results page powered by server-side RAG over raw research data, with web search fallback when retrieval is weak.

**Architecture:** After the Searcher node completes, raw signals are chunked and embedded into ChromaDB collections (per-report + unified). A new `/api/chat` SSE endpoint retrieves relevant chunks, optionally falls back to live Tavily search, then streams an LLM response. The frontend renders a slide-out glass-morphism chat panel.

**Tech Stack:** ChromaDB (vector store), sentence-transformers (embeddings), FastAPI SSE (streaming), React + Tailwind (UI)

**Design Doc:** `docs/plans/2026-03-13-research-chat-rag-design.md`

---

## Task 1: Add Backend Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add chromadb and sentence-transformers**

Add to `backend/requirements.txt`:

```
chromadb>=0.5.0
sentence-transformers>=3.0.0
```

**Step 2: Install dependencies**

Run: `cd backend && pip install -r requirements.txt`

**Step 3: Verify imports**

Run: `python -c "import chromadb; from sentence_transformers import SentenceTransformer; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(deps): add chromadb and sentence-transformers for RAG"
```

---

## Task 2: Create RAG Module — ChromaDB Setup, Chunking, Storage, Retrieval

**Files:**
- Create: `backend/rag.py`

**Step 1: Create `backend/rag.py`**

```python
"""RAG module — ChromaDB vector store for raw research data."""

import hashlib
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.models import RawCompanySignal

logger = logging.getLogger(__name__)

CHROMA_DIR = Path("cache/chromadb")
EMBED_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500  # approximate token limit per chunk
RELEVANCE_THRESHOLD = 0.4
MIN_RESULTS = 3
TOP_K = 10

_client: Optional[chromadb.PersistentClient] = None
_embed_fn: Optional[SentenceTransformerEmbeddingFunction] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _get_embed_fn() -> SentenceTransformerEmbeddingFunction:
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return _embed_fn


def _report_collection_name(report_id: str) -> str:
    """Sanitize report_id into a valid ChromaDB collection name."""
    safe = report_id[:50].replace("-", "_")
    return f"r_{safe}"


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks of approximately chunk_size tokens (≈4 chars/token)."""
    char_limit = chunk_size * 4
    if len(text) <= char_limit:
        return [text]

    chunks = []
    sentences = text.replace("\n", " ").split(". ")
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 2 > char_limit and current:
            chunks.append(current.strip())
            current = ""
        current += sentence + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


def make_report_id(query: str) -> str:
    """Generate a report ID from query — matches cache.py hashing pattern."""
    normalized = query.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def store_research(
    report_id: str,
    company_name: str,
    signals: list[RawCompanySignal],
) -> int:
    """Chunk and embed raw signals into ChromaDB. Returns chunk count."""
    client = _get_client()
    embed_fn = _get_embed_fn()

    # Per-report collection (replace if exists)
    col_name = _report_collection_name(report_id)
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=col_name, embedding_function=embed_fn
    )

    # Unified collection for cross-report queries
    unified = client.get_or_create_collection(
        name="all_research", embedding_function=embed_fn
    )
    # Remove old entries for this report from unified
    try:
        existing = unified.get(where={"report_id": report_id})
        if existing["ids"]:
            unified.delete(ids=existing["ids"])
    except Exception:
        pass

    documents = []
    metadatas = []
    ids = []

    for i, signal in enumerate(signals):
        chunks = _chunk_text(signal.snippet)
        for j, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            doc_id = f"{report_id}_{i}_{j}"
            meta = {
                "report_id": report_id,
                "company_name": company_name,
                "source_url": signal.url,
                "provider": signal.source,
            }
            documents.append(chunk)
            metadatas.append(meta)
            ids.append(doc_id)

    if not documents:
        return 0

    # Batch add (ChromaDB handles batching internally)
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    unified.add(documents=documents, metadatas=metadatas, ids=ids)

    logger.info(f"Stored {len(documents)} chunks for report {report_id}")
    return len(documents)


def store_web_results(
    report_id: str,
    company_name: str,
    results: list[dict],
) -> int:
    """Store web search fallback results into both collections."""
    client = _get_client()
    embed_fn = _get_embed_fn()

    col_name = _report_collection_name(report_id)
    collection = client.get_or_create_collection(
        name=col_name, embedding_function=embed_fn
    )
    unified = client.get_or_create_collection(
        name="all_research", embedding_function=embed_fn
    )

    documents = []
    metadatas = []
    ids = []

    for i, result in enumerate(results):
        text = result.get("content") or result.get("snippet", "")
        chunks = _chunk_text(text)
        for j, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            doc_id = f"{report_id}_web_{i}_{j}"
            meta = {
                "report_id": report_id,
                "company_name": company_name,
                "source_url": result.get("url", ""),
                "provider": "tavily_chat",
            }
            documents.append(chunk)
            metadatas.append(meta)
            ids.append(doc_id)

    if not documents:
        return 0

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    unified.add(documents=documents, metadatas=metadatas, ids=ids)
    return len(documents)


def retrieve(
    query: str,
    report_id: Optional[str] = None,
    scope: str = "current",
    top_k: int = TOP_K,
) -> dict:
    """
    Retrieve relevant chunks from ChromaDB.

    Returns:
        {
            "chunks": [{"text": str, "source_url": str, "provider": str, "company_name": str, "distance": float}],
            "is_weak": bool  # True if results are below quality threshold
        }
    """
    client = _get_client()
    embed_fn = _get_embed_fn()

    if scope == "current" and report_id:
        col_name = _report_collection_name(report_id)
        try:
            collection = client.get_collection(
                name=col_name, embedding_function=embed_fn
            )
        except Exception:
            return {"chunks": [], "is_weak": True}
    else:
        try:
            collection = client.get_collection(
                name="all_research", embedding_function=embed_fn
            )
        except Exception:
            return {"chunks": [], "is_weak": True}

    results = collection.query(query_texts=[query], n_results=top_k)

    chunks = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(
                {
                    "text": doc,
                    "source_url": meta.get("source_url", ""),
                    "provider": meta.get("provider", ""),
                    "company_name": meta.get("company_name", ""),
                    "distance": dist,
                }
            )

    # Check retrieval quality — ChromaDB distances are L2 (lower = better)
    is_weak = len(chunks) < MIN_RESULTS or (
        chunks and chunks[0]["distance"] > (1 - RELEVANCE_THRESHOLD)
    )

    return {"chunks": chunks, "is_weak": is_weak}


def get_indexed_report_count() -> int:
    """Return count of indexed report collections."""
    client = _get_client()
    collections = client.list_collections()
    return sum(1 for c in collections if c.name.startswith("r_"))
```

**Step 2: Verify module imports**

Run: `cd backend && python -c "from backend.rag import store_research, retrieve, make_report_id; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/rag.py
git commit -m "feat(rag): add ChromaDB vector store module with chunking and retrieval"
```

---

## Task 3: Hook RAG Ingestion into Searcher Node

**Files:**
- Modify: `backend/nodes/searcher.py`
- Modify: `backend/graph.py` (add `report_id` to state)

**Step 1: Add `report_id` to AgentState**

In `backend/graph.py`, add `report_id` field to `AgentState`:

```python
# Add to AgentState TypedDict
report_id: str  # SHA256 hash of query, used for RAG collection scoping
```

**Step 2: Modify searcher to store research in ChromaDB**

In `backend/nodes/searcher.py`, add RAG ingestion after search completes. Add at top:

```python
import threading
from backend.rag import store_research, make_report_id
```

At the end of the `search()` function, before the return statement, add:

```python
    # Async RAG ingestion — non-blocking side effect
    report_id = make_report_id(state["query"])
    company_name = state["query"].strip()

    def _ingest():
        try:
            store_research(report_id, company_name, signals)
        except Exception as e:
            logger.warning(f"RAG ingestion failed: {e}")

    threading.Thread(target=_ingest, daemon=True).start()
```

And update the return to include `report_id`:

```python
    return {"raw_signals": signals, "report_id": report_id}
```

**Step 3: Verify pipeline still works**

Run the backend dev server and test a deep dive query to confirm the pipeline completes without errors and `cache/chromadb/` is created.

**Step 4: Commit**

```bash
git add backend/nodes/searcher.py backend/graph.py
git commit -m "feat(rag): hook ChromaDB ingestion into searcher node"
```

---

## Task 4: Create Chat Endpoint

**Files:**
- Create: `backend/nodes/chat.py`
- Modify: `backend/main.py`

**Step 1: Create `backend/nodes/chat.py`**

```python
"""Chat endpoint logic — RAG retrieval + LLM streaming with web search fallback."""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field
from tavily import TavilyClient

from backend.config import get_settings
from backend.rag import retrieve, store_web_results

logger = logging.getLogger(__name__)

settings = get_settings()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    report_id: str
    scope: str = "current"  # "current" or "all"
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)
    company_name: str = ""


def _web_search_fallback(query: str) -> list[dict]:
    """Fallback web search via Tavily when RAG retrieval is weak."""
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query, max_results=5, include_raw_content=False)
        return [
            {"url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in response.get("results", [])
        ]
    except Exception as e:
        logger.warning(f"Web search fallback failed: {e}")
        return []


def _build_system_prompt(chunks: list[dict], used_web_search: bool) -> str:
    """Build system prompt with retrieved context."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source_url", "unknown")
        provider = chunk.get("provider", "unknown")
        context_parts.append(
            f"[Source {i}] ({provider}) {source}\n{chunk['text']}"
        )

    context_block = "\n\n---\n\n".join(context_parts)

    return f"""You are a research assistant helping users understand company intelligence data.
You answer questions based ONLY on the provided research context below.
If the answer is not in the context, say so honestly — do not make up information.
When referencing information, cite the source number in brackets like [1], [2], etc.
Keep answers concise and well-structured. Use markdown formatting.

## Research Context

{context_block}

## Rules
- Only answer from the context above
- Cite sources with [N] notation
- If unsure, say "I didn't find clear information about that in the research data"
- Be concise and direct"""


async def generate_chat_response(req: ChatRequest):
    """
    Generator that yields SSE events for the chat response.

    Yields dicts with:
        - {"type": "retrieval", "chunk_count": N, "web_search": bool}
        - {"type": "token", "content": "..."}
        - {"type": "sources", "sources": [...]}
        - {"type": "done"}
        - {"type": "error", "message": "..."}
    """
    try:
        # Step 1: Retrieve from ChromaDB
        rag_result = retrieve(
            query=req.message,
            report_id=req.report_id,
            scope=req.scope,
        )
        chunks = rag_result["chunks"]
        used_web_search = False

        # Step 2: Web search fallback if retrieval is weak
        if rag_result["is_weak"]:
            web_results = _web_search_fallback(
                f"{req.company_name} {req.message}" if req.company_name else req.message
            )
            if web_results:
                used_web_search = True
                store_web_results(req.report_id, req.company_name, web_results)
                # Re-retrieve with enriched data
                rag_result = retrieve(
                    query=req.message,
                    report_id=req.report_id,
                    scope=req.scope,
                )
                chunks = rag_result["chunks"]

        yield {"type": "retrieval", "chunk_count": len(chunks), "web_search": used_web_search}

        if not chunks:
            yield {"type": "token", "content": "I don't have any research data to answer this question. Try running a deep dive first."}
            yield {"type": "done"}
            return

        # Step 3: Build prompt and stream LLM response
        system_prompt = _build_system_prompt(chunks, used_web_search)

        messages = [{"role": "system", "content": system_prompt}]
        for msg in req.history[-10:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": req.message})

        # Use OpenAI-compatible client (same as existing pipeline)
        import openai

        client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=getattr(settings, "openai_base_url", None),
        )

        model = getattr(settings, "chat_model", None) or getattr(settings, "default_model", "gpt-4o-mini")

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.3,
            max_tokens=1500,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield {"type": "token", "content": delta.content}

        # Step 4: Return source URLs used
        source_urls = list(dict.fromkeys(c["source_url"] for c in chunks if c["source_url"]))
        yield {"type": "sources", "sources": source_urls[:10]}
        yield {"type": "done"}

    except Exception as e:
        logger.exception("Chat generation failed")
        yield {"type": "error", "message": str(e)}
```

**Step 2: Register `/api/chat` endpoint in `backend/main.py`**

Add import at top of `main.py`:

```python
from backend.nodes.chat import ChatRequest, generate_chat_response
from backend.rag import get_indexed_report_count
```

Add the endpoint (after existing endpoints):

```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat with research data via RAG + LLM streaming."""

    async def event_generator():
        async for event in generate_chat_response(req):
            yield ServerSentEvent(
                event=event["type"],
                data=json.dumps(event),
            )

    return EventSourceResponse(event_generator())


@app.get("/api/chat/status")
async def chat_status():
    """Return count of indexed reports for the scope toggle UI."""
    return {"indexed_reports": get_indexed_report_count()}
```

Also add `report_id` to the complete event data in the existing `/api/query` endpoint. In the section that builds the final payload on `event="complete"`, add:

```python
# Inside the event_generator for /api/query, where final_payload is built:
# Add report_id from state
"report_id": state_snapshot.get("report_id", ""),
```

**Step 3: Verify endpoint starts**

Run: `cd backend && uvicorn backend.main:app --reload`

Confirm no import errors.

**Step 4: Commit**

```bash
git add backend/nodes/chat.py backend/main.py
git commit -m "feat(chat): add /api/chat SSE endpoint with RAG retrieval and web search fallback"
```

---

## Task 5: Create `useChatStream` Hook

**Files:**
- Create: `frontend/src/hooks/useChatStream.js`

**Step 1: Create the hook**

Follow the same SSE reading pattern as `useAgentQuery.js`:

```javascript
import { useState, useRef, useCallback } from "react";
import { getApiUrl } from "../lib/api";

export function useChatStream(reportId) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const cancelledRef = useRef(false);
  const abortRef = useRef(null);

  const sendMessage = useCallback(
    async (message, { scope = "current", companyName = "" } = {}) => {
      if (!message.trim() || isStreaming) return;

      const userMsg = { role: "user", content: message };
      const assistantMsg = {
        role: "assistant",
        content: "",
        sources: [],
        webSearch: false,
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);
      setError(null);
      cancelledRef.current = false;

      const history = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }))
        .slice(-10);

      try {
        const controller = new AbortController();
        abortRef.current = controller;

        const resp = await fetch(getApiUrl("/api/chat"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            report_id: reportId,
            scope,
            history,
            company_name: companyName,
          }),
          signal: controller.signal,
        });

        if (!resp.ok) throw new Error(`Chat request failed: ${resp.status}`);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent = "";

        while (!cancelledRef.current) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              const data = JSON.parse(line.slice(5).trim());

              if (currentEvent === "token" || data.type === "token") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = { ...updated[updated.length - 1] };
                  last.content += data.content;
                  updated[updated.length - 1] = last;
                  return updated;
                });
              } else if (
                currentEvent === "retrieval" ||
                data.type === "retrieval"
              ) {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = { ...updated[updated.length - 1] };
                  last.webSearch = data.web_search;
                  updated[updated.length - 1] = last;
                  return updated;
                });
              } else if (
                currentEvent === "sources" ||
                data.type === "sources"
              ) {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = { ...updated[updated.length - 1] };
                  last.sources = data.sources || [];
                  updated[updated.length - 1] = last;
                  return updated;
                });
              } else if (currentEvent === "error" || data.type === "error") {
                setError(data.message);
              }
            }
          }
        }
      } catch (e) {
        if (e.name !== "AbortError") {
          setError(e.message);
        }
      } finally {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0) {
            const last = { ...updated[updated.length - 1] };
            last.isStreaming = false;
            updated[updated.length - 1] = last;
          }
          return updated;
        });
      }
    },
    [reportId, isStreaming, messages],
  );

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    abortRef.current?.abort();
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, isStreaming, error, sendMessage, cancel, clearMessages };
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useChatStream.js
git commit -m "feat(chat): add useChatStream SSE hook"
```

---

## Task 6: Create Chat UI Components

**Files:**
- Create: `frontend/src/components/chat/ChatMessage.jsx`
- Create: `frontend/src/components/chat/ChatInput.jsx`
- Create: `frontend/src/components/chat/ScopeToggle.jsx`
- Create: `frontend/src/components/chat/ChatPanel.jsx`

**Step 1: Create `ChatMessage.jsx`**

```jsx
import { cn } from "../../lib/utils";
import { MarkdownProse } from "../shared/MarkdownProse";
import { Globe, ExternalLink } from "lucide-react";

export function ChatMessage({ message, index }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex w-full animate-init animate-chat-fade-up",
        isUser ? "justify-end" : "justify-start",
      )}
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-primary/20 text-foreground"
            : "glass border border-white/[0.06]",
        )}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <>
            {message.isStreaming && !message.content && <TypingIndicator />}
            {message.content && (
              <MarkdownProse content={message.content} citations={[]} />
            )}
            {message.webSearch && (
              <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                <Globe className="h-3 w-3" />
                <span>Searched the web</span>
              </div>
            )}
            {message.sources?.length > 0 && !message.isStreaming && (
              <div className="mt-3 border-t border-white/[0.06] pt-2">
                <p className="mb-1 text-xs text-muted-foreground">Sources</p>
                <div className="flex flex-wrap gap-1.5">
                  {message.sources.map((url, i) => (
                    <a
                      key={i}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-2 py-0.5 text-xs text-blue-400 transition-colors hover:bg-white/[0.08]"
                    >
                      <ExternalLink className="h-2.5 w-2.5" />
                      {new URL(url).hostname.replace("www.", "")}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-chat-dot"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
```

**Step 2: Create `ChatInput.jsx`**

```jsx
import { useState, useRef, useEffect } from "react";
import { SendHorizonal } from "lucide-react";
import { cn } from "../../lib/utils";

export function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }
  }, [value]);

  const handleSubmit = () => {
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex items-end gap-2 rounded-xl border border-white/[0.08] bg-white/[0.03] p-2 transition-colors focus-within:border-primary/30">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about this research..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-all",
          value.trim() && !disabled
            ? "bg-primary text-white active:scale-90"
            : "text-muted-foreground opacity-40",
        )}
      >
        <SendHorizonal className="h-4 w-4" />
      </button>
    </div>
  );
}
```

**Step 3: Create `ScopeToggle.jsx`**

```jsx
import { useState, useEffect } from "react";
import { cn } from "../../lib/utils";
import { getApiUrl } from "../../lib/api";

export function ScopeToggle({ scope, onScopeChange }) {
  const [reportCount, setReportCount] = useState(0);

  useEffect(() => {
    fetch(getApiUrl("/api/chat/status"))
      .then((r) => r.json())
      .then((d) => setReportCount(d.indexed_reports || 0))
      .catch(() => {});
  }, []);

  return (
    <div className="relative flex rounded-lg bg-white/[0.04] p-0.5">
      <div
        className={cn(
          "absolute inset-y-0.5 rounded-md bg-primary/20 transition-all duration-300 ease-out",
          scope === "current"
            ? "left-0.5 w-[calc(50%-2px)]"
            : "left-[50%] w-[calc(50%-2px)]",
        )}
      />
      <button
        onClick={() => onScopeChange("current")}
        className={cn(
          "relative z-10 flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
          scope === "current" ? "text-foreground" : "text-muted-foreground",
        )}
      >
        This report
      </button>
      <button
        onClick={() => onScopeChange("all")}
        className={cn(
          "relative z-10 flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
          scope === "all" ? "text-foreground" : "text-muted-foreground",
        )}
      >
        All research
        {reportCount > 1 && (
          <span className="ml-1 text-[10px] text-muted-foreground">
            ({reportCount})
          </span>
        )}
      </button>
    </div>
  );
}
```

**Step 4: Create `ChatPanel.jsx`**

```jsx
import { useState, useRef, useEffect } from "react";
import { X, MessageSquare, Trash2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { useChatStream } from "../../hooks/useChatStream";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { ScopeToggle } from "./ScopeToggle";

export function ChatPanel({ reportId, companyName, isOpen, onClose }) {
  const [scope, setScope] = useState("current");
  const scrollRef = useRef(null);
  const { messages, isStreaming, error, sendMessage, clearMessages } =
    useChatStream(reportId);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const handleSend = (message) => {
    sendMessage(message, { scope, companyName });
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-300 lg:hidden",
          isOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className={cn(
          "fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-white/[0.06] transition-transform duration-300 ease-out lg:w-[420px]",
          "glass-strong",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-medium text-foreground">
              Research Chat
            </h3>
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={clearMessages}
                className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                title="Clear chat"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Scope Toggle */}
        <div className="px-4 py-2">
          <ScopeToggle scope={scope} onScopeChange={setScope} />
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-3"
        >
          {messages.length === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <div className="rounded-full bg-primary/10 p-3">
                <MessageSquare className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">
                  Ask about this research
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Chat with the raw data collected during the deep dive
                </p>
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} index={i} />
          ))}
          {error && (
            <div className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-white/[0.06] px-4 py-3">
          <ChatInput onSend={handleSend} disabled={isStreaming} />
        </div>
      </div>
    </>
  );
}

export function ChatTrigger({ onClick }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full px-4 py-3",
        "bg-primary text-white shadow-lg shadow-primary/20",
        "transition-all duration-200 hover:scale-105 hover:shadow-xl hover:shadow-primary/30",
        "active:scale-95",
        "animate-init animate-chat-fade-up",
      )}
      style={{ animationDelay: "0.5s" }}
    >
      <MessageSquare className="h-4 w-4" />
      <span className="text-sm font-medium">Ask about this research</span>
    </button>
  );
}
```

**Step 5: Commit**

```bash
git add frontend/src/components/chat/
git commit -m "feat(chat): add ChatPanel, ChatMessage, ChatInput, and ScopeToggle components"
```

---

## Task 7: Add Chat Animations to CSS

**Files:**
- Modify: `frontend/src/index.css`

**Step 1: Add chat-specific keyframes and utilities**

Add after the existing `@keyframes` block in `index.css`:

```css
/* Chat animations */
@keyframes chat-fade-up {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes chat-dot {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  30% {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-chat-fade-up {
  animation: chat-fade-up 0.35s ease-out forwards;
}

.animate-chat-dot {
  animation: chat-dot 1.2s ease-in-out infinite;
}
```

**Step 2: Commit**

```bash
git add frontend/src/index.css
git commit -m "style(css): add chat fade-up and typing dot animations"
```

---

## Task 8: Integrate ChatPanel into DeepDiveView

**Files:**
- Modify: `frontend/src/components/deep-dive/DeepDiveView.jsx`

**Step 1: Add chat state and render ChatPanel**

Add imports at top of `DeepDiveView.jsx`:

```javascript
import { ChatPanel, ChatTrigger } from "../chat/ChatPanel";
import { useState } from "react";
```

Add state inside the component:

```javascript
const [chatOpen, setChatOpen] = useState(false);
```

Extract `reportId` and `companyName` from data:

```javascript
const reportId = data?.report_id || "";
const companyName = report?.company_name || data?.query || "";
```

Add at the end of the component's return, just before the closing fragment/div:

```jsx
{reportId && (
  <>
    {!chatOpen && <ChatTrigger onClick={() => setChatOpen(true)} />}
    <ChatPanel
      reportId={reportId}
      companyName={companyName}
      isOpen={chatOpen}
      onClose={() => setChatOpen(false)}
    />
  </>
)}
```

**Step 2: Pass `report_id` through from App.jsx**

In `App.jsx`, ensure the `report_id` from the SSE complete event is included in the result data passed to `DeepDiveView`. Check if `useAgentQuery` already passes through all fields from the complete event — if so, no change needed. If not, the `report_id` field should be preserved in the result state.

**Step 3: Verify end-to-end**

1. Start backend: `cd backend && uvicorn backend.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Run a deep dive query
4. Verify the "Ask about this research" button appears on the results page
5. Click it — chat panel should slide in from the right
6. Send a message — should stream a response with citations
7. Toggle "All research" — should work if multiple reports exist
8. Close the panel — should slide out smoothly

**Step 4: Commit**

```bash
git add frontend/src/components/deep-dive/DeepDiveView.jsx
git commit -m "feat(chat): integrate ChatPanel into DeepDiveView"
```

---

## Task 9: Backend Config — Add Chat Model Setting

**Files:**
- Modify: `backend/config.py` (or wherever `get_settings()` is defined)

**Step 1: Add chat-specific settings**

Add to the settings class:

```python
chat_model: str = "gpt-4o-mini"  # Cheaper model for chat responses
openai_api_key: str = ""  # Should already exist
```

`gpt-4o-mini` is recommended for chat to keep costs low — the heavy lifting is done by the embedding model and retrieval, not the generation.

**Step 2: Commit**

```bash
git add backend/config.py
git commit -m "chore(config): add chat_model setting for RAG chat responses"
```

---

## Summary

| Task | Description | New Files | Modified Files |
|------|-------------|-----------|----------------|
| 1 | Add dependencies | — | `requirements.txt` |
| 2 | RAG module | `backend/rag.py` | — |
| 3 | Searcher integration | — | `searcher.py`, `graph.py` |
| 4 | Chat endpoint | `backend/nodes/chat.py` | `main.py` |
| 5 | useChatStream hook | `frontend/src/hooks/useChatStream.js` | — |
| 6 | Chat UI components | 4 files in `components/chat/` | — |
| 7 | CSS animations | — | `index.css` |
| 8 | DeepDiveView integration | — | `DeepDiveView.jsx` |
| 9 | Config settings | — | `config.py` |

**Total: 7 new files, 6 modified files, 9 tasks.**
