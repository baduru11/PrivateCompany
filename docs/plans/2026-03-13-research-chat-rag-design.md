# Research Chat with RAG — Design Document

> **Date:** 2026-03-13
> **Status:** Approved
> **Summary:** Add a chat interface to the Deep Dive results page that lets users ask questions about raw research data using server-side RAG with ChromaDB, with web search fallback.

---

## Overview

Users can chat with their research data directly from the Deep Dive results page. The chat is powered by RAG over the **raw research data** (search results, crawled pages, extracted content from Tavily/Exa/Crawl4AI) — not just the final synthesized report. This gives users access to details that may have been filtered out during synthesis.

Users can scope queries to the current report or search across all past research. When RAG retrieval is weak, the system falls back to live web search, enriching the knowledge base over time.

---

## Architecture

### Data Ingestion

- After the **Searcher node** completes, a new async step chunks and embeds raw research content into ChromaDB
- Each deep dive gets a **collection** named by report ID (e.g., `research_abc123`)
- Raw data is chunked at ~500 tokens per chunk
- Each chunk stores metadata: `source_url`, `provider` (tavily/exa/crawl4ai), `company_name`, `query_used`, `timestamp`
- Embeddings generated locally via **sentence-transformers** (`all-MiniLM-L6-v2`) — no API cost
- A second collection `all_research` indexes the same chunks for cross-report queries
- Ingestion runs **async** — does not slow down the main pipeline
- Existing pipeline nodes (Profiler, Synthesis, Critic) are unaffected

### Chat Backend — `POST /api/chat`

**Request:**

```json
{
  "message": "What did sources say about their patent portfolio?",
  "report_id": "abc123",
  "scope": "current" | "all",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

**Server-side flow:**

1. **Retrieve** — Query the appropriate ChromaDB collection (`research_{report_id}` or `all_research`) for top 8-10 relevant chunks
2. **Evaluate retrieval quality** — If top results have low similarity scores (below 0.4 threshold) or fewer than 3 chunks returned, trigger a **live web search** via Tavily as fallback
3. **Enrich** — Web search results are added to the ChromaDB collection, so the knowledge base grows from chat interactions
4. **Build prompt** — System prompt instructs the LLM to answer based on the provided research context. Includes: retrieved chunks with source metadata, the final report summary (for grounding), conversation history
5. **Stream** — Pass to existing multi-LLM infrastructure (Gemini/GPT-4o/Claude) and stream response via SSE
6. **Citations** — LLM is instructed to reference source URLs from chunk metadata

**Key details:**

- Conversation history sent from frontend (stateless backend)
- If `scope: "all"`, filter by `company_name` metadata when relevant
- Reuses existing SSE streaming — no new streaming infrastructure
- Max 10 conversation turns in history
- Input capped at 1000 characters per message
- Timeout of 30s per chat response

### Chat UI

**Placement & Layout:**

- Slide-out panel from the right side of the Deep Dive results page
- Triggered by a floating "Ask about this research" button (bottom-right corner)
- Panel takes ~40% width on desktop, full-screen overlay on mobile
- Report stays visible and scrollable on the left

**Visual Design:**

- Glass-morphism panel consistent with existing dark theme and glass utilities
- Smooth slide-in animation (300ms ease-out) on open, fade + slide-out on close
- Messages appear with fade-up + scale entrance animation, staggered

**Message Bubbles:**

- User messages: right-aligned, subtle solid background
- Assistant messages: left-aligned, glass/translucent background with soft border
- Inline citations via existing `SourcePopover` components
- Markdown rendering via existing `MarkdownProse` component
- Streaming shows pulsing dot typing indicator that transitions into text
- "Searched the web" label on messages where fallback search was triggered

**Scope Toggle:**

- Pill toggle at top of chat panel: "This report" | "All research"
- Smooth background slide animation on toggle
- "All research" shows count of indexed reports

**Micro-interactions:**

- Send button spring animation on press
- Messages have soft glow on hover
- Auto-scroll to bottom with smooth scrolling
- Auto-resize textarea, Shift+Enter for newline, Enter to send

---

## Error Handling & Edge Cases

- **Report still generating:** Chat button disabled with tooltip "Available after research completes"
- **Single report in "All research":** Subtle hint "Only 1 report indexed"
- **No relevant chunks:** LLM responds honestly: "I didn't find anything about that in the research data" (then may trigger web search fallback)
- **SSE connection drop:** "Connection lost — tap to retry" inline on partial message
- **Re-run deep dive for same company:** Old collection is replaced, not duplicated
- **System prompt grounding:** "Answer based on the provided research context. If the answer isn't in the context, say so."

---

## Implementation — File Changes

### Backend (new files)

| File | Purpose |
|------|---------|
| `backend/rag.py` | ChromaDB client setup, chunking logic, embed + store, retrieval function, web search fallback |
| `backend/nodes/chat.py` | Chat endpoint logic: retrieve → evaluate → build prompt → stream |

### Backend (modified)

| File | Change |
|------|--------|
| `backend/main.py` | Register `POST /api/chat` SSE endpoint |
| `backend/nodes/searcher.py` | After search completes, call `rag.store_research()` async |
| `backend/requirements.txt` | Add `chromadb`, `sentence-transformers` |

### Frontend (new files)

| File | Purpose |
|------|---------|
| `frontend/src/components/chat/ChatPanel.jsx` | Slide-out panel container with animations |
| `frontend/src/components/chat/ChatMessage.jsx` | Message bubble with entrance animations |
| `frontend/src/components/chat/ChatInput.jsx` | Auto-resize textarea with send button |
| `frontend/src/components/chat/ScopeToggle.jsx` | "This report" / "All research" pill toggle |
| `frontend/src/hooks/useChatStream.js` | SSE hook for chat streaming |

### Frontend (modified)

| File | Change |
|------|--------|
| `frontend/src/pages/DeepDiveView.jsx` | Add floating chat button + render ChatPanel |
| `frontend/src/index.css` | Chat animations (fade-up, slide-in, pulse dots) |

### Dependencies

- **Backend:** `chromadb`, `sentence-transformers`
- **Frontend:** none (uses existing libs)

**Total: 7 new files, 4 modified files.**
