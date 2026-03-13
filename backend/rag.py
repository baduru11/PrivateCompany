# backend/rag.py
"""
RAG (Retrieval-Augmented Generation) module for CompanyIntel.

Provides chunking, embedding, and retrieval over research signals
using ChromaDB with SentenceTransformer embeddings.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from backend.models import RawCompanySignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_chroma_client = None
_embed_fn = None

CHROMA_DIR = str(Path("cache") / "chromadb")
UNIFIED_COLLECTION = "all_research"
DISTANCE_THRESHOLD = 0.7  # cosine distance above which results are "weak" (0-2 range)
MIN_GOOD_RESULTS = 3


def _get_client():
    """Lazy-init ChromaDB PersistentClient at cache/chromadb/."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        logger.info("ChromaDB PersistentClient initialized at %s", CHROMA_DIR)
    return _chroma_client


def _get_embed_fn():
    """Lazy-init SentenceTransformerEmbeddingFunction with all-MiniLM-L6-v2."""
    global _embed_fn
    if _embed_fn is None:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        _embed_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
        )
        logger.info("SentenceTransformer embedding function loaded (all-MiniLM-L6-v2)")
    return _embed_fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report_collection_name(report_id: str) -> str:
    """Sanitize report_id into a valid ChromaDB collection name.

    ChromaDB collection names must:
      - be 3-63 characters
      - start and end with alphanumeric
      - contain only alphanumeric, underscores, or hyphens
      - not contain two consecutive periods
    """
    # Prefix with r_ so we can identify report collections
    name = f"r_{report_id}"
    # Replace any character that isn't alphanumeric, underscore, or hyphen
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    # Collapse consecutive underscores
    name = re.sub(r"_{2,}", "_", name)
    # Ensure starts/ends with alphanumeric
    name = name.strip("_-")
    if not name or not name[0].isalnum():
        name = "r" + name
    if not name[-1].isalnum():
        name = name + "0"
    # Enforce length bounds
    name = name[:63]
    if len(name) < 3:
        name = name.ljust(3, "0")
    return name


def _chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split text into ~500-token chunks by sentence boundaries.

    Uses a rough heuristic of 1 token ~ 4 characters. Splits on sentence
    endings (.!?) and groups sentences until the chunk reaches the target
    size. Handles edge cases like empty text and very long sentences.
    """
    if not text or not text.strip():
        return []

    # Approximate char limit from token target (1 token ~ 4 chars)
    char_limit = chunk_size * 4

    # Split into sentences (keep the delimiter attached)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sent_len = len(sentence)

        # If a single sentence exceeds the limit, split it by words
        if sent_len > char_limit:
            # Flush current buffer first
            if current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0

            words = sentence.split()
            word_buf: list[str] = []
            word_buf_len = 0
            for word in words:
                if word_buf_len + len(word) + 1 > char_limit and word_buf:
                    chunks.append(" ".join(word_buf))
                    word_buf = []
                    word_buf_len = 0
                word_buf.append(word)
                word_buf_len += len(word) + 1
            if word_buf:
                chunks.append(" ".join(word_buf))
            continue

        if current_len + sent_len + 1 > char_limit and current:
            chunks.append(" ".join(current))
            current = []
            current_len = 0

        current.append(sentence)
        current_len += sent_len + 1

    if current:
        chunks.append(" ".join(current))

    return chunks


def make_report_id(query: str) -> str:
    """SHA256 hash (first 16 chars) of normalized query."""
    normalized = query.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _get_or_create_collection(name: str):
    """Get or create a ChromaDB collection with the embedding function."""
    client = _get_client()
    return client.get_or_create_collection(
        name=name,
        embedding_function=_get_embed_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def _upsert_chunks(
    collection,
    chunks: list[str],
    metadatas: list[dict[str, Any]],
    id_prefix: str,
) -> None:
    """Upsert chunks into a ChromaDB collection in batches."""
    if not chunks:
        return

    ids = [f"{id_prefix}_{i}" for i in range(len(chunks))]

    # ChromaDB has a batch limit; upsert in batches of 500
    batch_size = 500
    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        collection.upsert(
            ids=ids[start:end],
            documents=chunks[start:end],
            metadatas=metadatas[start:end],
        )


def store_research(
    report_id: str,
    company_name: str,
    signals: list[RawCompanySignal],
) -> int:
    """Chunk and embed raw signals into per-report and unified collections.

    Replaces old data in the per-report collection if re-running.
    Returns the total number of chunks stored.
    """
    col_name = _report_collection_name(report_id)

    # Delete existing per-report collection to replace old data
    client = _get_client()
    try:
        client.delete_collection(col_name)
        logger.info("Deleted existing collection %s for re-indexing", col_name)
    except Exception:
        pass  # Collection didn't exist yet

    report_col = _get_or_create_collection(col_name)
    unified_col = _get_or_create_collection(UNIFIED_COLLECTION)

    # Remove old entries from unified collection for this report
    try:
        existing = unified_col.get(where={"report_id": report_id})
        if existing and existing["ids"]:
            unified_col.delete(ids=existing["ids"])
    except Exception:
        pass

    total_chunks = 0

    for idx, signal in enumerate(signals):
        text = signal.snippet.strip()
        if not text:
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        meta_base = {
            "report_id": report_id,
            "company_name": company_name,
            "signal_company": signal.company_name,
            "source": signal.source,
            "url": signal.url,
        }
        metadatas = [dict(meta_base) for _ in chunks]

        # Per-report collection
        _upsert_chunks(
            report_col,
            chunks,
            metadatas,
            id_prefix=f"{report_id}_sig{idx}",
        )

        # Unified collection (prefix with report_id so IDs don't collide)
        _upsert_chunks(
            unified_col,
            chunks,
            metadatas,
            id_prefix=f"{report_id}_sig{idx}",
        )

        total_chunks += len(chunks)

    logger.info(
        "Stored %d chunks for report_id=%s (%d signals)",
        total_chunks,
        report_id,
        len(signals),
    )
    return total_chunks


def store_web_results(
    report_id: str,
    company_name: str,
    results: list[dict],
) -> int:
    """Store web search fallback results into per-report and unified collections.

    Each result dict is expected to have at least 'content' or 'snippet',
    plus optionally 'url' and 'title'.
    Returns the total number of chunks stored.
    """
    col_name = _report_collection_name(report_id)
    report_col = _get_or_create_collection(col_name)
    unified_col = _get_or_create_collection(UNIFIED_COLLECTION)

    total_chunks = 0

    for idx, result in enumerate(results):
        text = result.get("content") or result.get("snippet") or ""
        text = text.strip()
        if not text:
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        meta_base = {
            "report_id": report_id,
            "company_name": company_name,
            "source": "web_search",
            "url": result.get("url", ""),
            "title": result.get("title", ""),
        }
        metadatas = [dict(meta_base) for _ in chunks]

        _upsert_chunks(
            report_col,
            chunks,
            metadatas,
            id_prefix=f"{report_id}_web{idx}",
        )

        _upsert_chunks(
            unified_col,
            chunks,
            metadatas,
            id_prefix=f"{report_id}_web{idx}",
        )

        total_chunks += len(chunks)

    logger.info(
        "Stored %d web result chunks for report_id=%s (%d results)",
        total_chunks,
        report_id,
        len(results),
    )
    return total_chunks


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    report_id: str | None = None,
    scope: str = "current",
    top_k: int = 10,
) -> dict[str, Any]:
    """Query ChromaDB and return relevant chunks.

    Args:
        query: The search query text.
        report_id: The report to scope to (required if scope="report").
        scope: "current" to search per-report collection, "all" to search
               the unified all_research collection.
        top_k: Maximum number of results to return.

    Returns:
        {"chunks": [...], "is_weak": bool}
        Each chunk has "text", "source_url", "provider", "company_name", "distance".
        is_weak is True if fewer than MIN_GOOD_RESULTS results or
        top result distance exceeds DISTANCE_THRESHOLD.
    """
    try:
        if scope == "current" and report_id:
            col_name = _report_collection_name(report_id)
        else:
            col_name = UNIFIED_COLLECTION

        collection = _get_or_create_collection(col_name)
        count = collection.count()

        if count == 0:
            logger.warning("Collection %s is empty", col_name)
            return {"chunks": [], "is_weak": True}

        # Don't request more than what's available
        actual_k = min(top_k, count)

        results = collection.query(
            query_texts=[query],
            n_results=actual_k,
        )
    except Exception as exc:
        logger.error("ChromaDB query failed: %s", exc)
        return {"chunks": [], "is_weak": True}

    # Unpack ChromaDB results (they come as lists of lists)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        chunks.append({
            "text": doc,
            "source_url": meta.get("url", ""),
            "provider": meta.get("source", ""),
            "company_name": meta.get("company_name", ""),
            "distance": dist,
        })

    # Determine if the results are weak
    is_weak = False
    if len(chunks) < MIN_GOOD_RESULTS:
        is_weak = True
    elif chunks and chunks[0]["distance"] > DISTANCE_THRESHOLD:
        is_weak = True

    logger.info(
        "Retrieved %d chunks (scope=%s, is_weak=%s) for query: %.80s",
        len(chunks),
        scope,
        is_weak,
        query,
    )
    return {"chunks": chunks, "is_weak": is_weak}


# ---------------------------------------------------------------------------
# Admin / Metrics
# ---------------------------------------------------------------------------

def get_indexed_report_count() -> int:
    """Count collections starting with 'r_' (per-report collections)."""
    try:
        client = _get_client()
        collections = client.list_collections()
        # list_collections returns collection names (str) in newer chromadb
        # or Collection objects in older versions
        count = 0
        for col in collections:
            name = col if isinstance(col, str) else col.name
            if name.startswith("r_"):
                count += 1
        return count
    except Exception as exc:
        logger.error("Failed to count indexed reports: %s", exc)
        return 0
