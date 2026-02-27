# backend/cache.py
from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path


class CacheManager:
    def __init__(self, base_dir: str = "cache"):
        self.base_dir = Path(base_dir)
        self.api_dir = self.base_dir / "api"
        self.report_dir = self.base_dir / "reports"
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_key(self, key: str) -> str:
        return key.strip().lower()

    def _hash_key(self, *parts: str) -> str:
        combined = "|".join(self._normalize_key(p) for p in parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def get_api(self, provider: str, query: str) -> dict | None:
        path = self.api_dir / f"{provider}_{self._hash_key(provider, query)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def set_api(self, provider: str, query: str, data: dict) -> None:
        path = self.api_dir / f"{provider}_{self._hash_key(provider, query)}.json"
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def get_report(self, mode: str, query: str) -> dict | None:
        path = self.report_dir / f"{mode}_{self._hash_key(mode, query)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def set_report(self, mode: str, query: str, data: dict) -> None:
        meta = {
            **data,
            "_cached_at": datetime.now(timezone.utc).isoformat(),
            "_mode": mode,
            "_query": query,
        }
        path = self.report_dir / f"{mode}_{self._hash_key(mode, query)}.json"
        path.write_text(json.dumps(meta, default=str), encoding="utf-8")

    def list_reports(self) -> list[dict]:
        reports = []
        for path in self.report_dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            reports.append({
                "mode": data.get("_mode", "unknown"),
                "query": data.get("_query", "unknown"),
                "cached_at": data.get("_cached_at", ""),
                "filename": path.name,
            })
        return sorted(reports, key=lambda r: r["cached_at"], reverse=True)
