"""TraceService – read and parse traces from logs/traces.jsonl.

Provides a typed, filterable interface over the raw JSONL trace log.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.settings import resolve_path

logger = logging.getLogger(__name__)

# Default path to the traces file (absolute, CWD-independent)
DEFAULT_TRACES_PATH = resolve_path("logs/traces.jsonl")


class TraceService:
    """Read-only service for querying recorded traces.

    Args:
        traces_path: Path to the JSONL file.  Defaults to
            ``logs/traces.jsonl``.
    """

    def __init__(self, traces_path: Optional[str | Path] = None) -> None:
        self.traces_path = Path(traces_path) if traces_path else DEFAULT_TRACES_PATH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_traces(
        self,
        trace_type: Optional[str] = None,
        limit: Optional[int] = 100,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return traces in reverse-chronological order.

        Args:
            trace_type: Filter by ``trace_type`` field (e.g.
                ``"ingestion"`` or ``"query"``).  ``None`` = all.
            limit: Maximum number of traces to return.  ``None`` = no cap
                (useful when searching the full history).
            keyword: Case-insensitive substring filter on query text,
                collection, chunk content, trace_id, etc.

        Returns:
            List of trace dicts (newest first).
        """
        traces = self._load_all()

        if trace_type:
            traces = [t for t in traces if t.get("trace_type") == trace_type]

        if keyword and keyword.strip():
            traces = [t for t in traces if self.matches_keyword(t, keyword)]

        # Newest first
        traces.sort(key=lambda t: t.get("started_at", ""), reverse=True)

        if limit is None:
            return traces
        return traces[:limit]

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single trace by its ``trace_id``.

        Returns:
            Trace dict, or ``None`` if not found.
        """
        for t in self._load_all():
            if t.get("trace_id") == trace_id:
                return t
        return None

    def get_stage_timings(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract stage timings from a trace.

        Returns:
            List of dicts with keys: stage_name, elapsed_ms, data.
            Ordered by appearance.
        """
        stages = trace.get("stages", [])
        timings: List[Dict[str, Any]] = []
        for s in stages:
            # The raw stage dict has: stage, timestamp, data (dict), elapsed_ms
            # Extract the inner 'data' dict directly rather than flattening
            stage_data = s.get("data", {})
            if not isinstance(stage_data, dict):
                stage_data = {}
            timings.append(
                {
                    "stage_name": s.get("stage"),
                    "elapsed_ms": s.get("elapsed_ms", 0),
                    "data": stage_data,
                }
            )
        return timings

    @staticmethod
    def matches_keyword(trace: Dict[str, Any], keyword: str) -> bool:
        """Return whether *trace* matches a case-insensitive keyword.

        Searches user-facing fields only (query text, collection, chunk
        content, trace_id, etc.) — not raw stage names or JSON keys.
        """
        kw = keyword.strip().lower()
        if not kw:
            return True

        for text in TraceService._iter_searchable_texts(trace):
            if text and kw in str(text).lower():
                return True
        return False

    @staticmethod
    def _iter_searchable_texts(trace: Dict[str, Any]):
        """Yield human-meaningful strings from a trace for keyword search."""
        yield trace.get("trace_id", "")
        yield trace.get("started_at", "")

        meta = trace.get("metadata") or {}
        if not isinstance(meta, dict):
            return

        yield meta.get("query", "")
        yield meta.get("collection", "")
        yield meta.get("source", "")

        for result in meta.get("final_results") or []:
            if not isinstance(result, dict):
                continue
            yield result.get("text", "")
            yield result.get("title", "")
            yield result.get("source", "")
            yield result.get("chunk_id", "")

        for stage in trace.get("stages") or []:
            if not isinstance(stage, dict):
                continue
            data = stage.get("data") or {}
            if not isinstance(data, dict):
                continue
            yield data.get("original_query", "")
            for item in data.get("keywords") or []:
                yield item
            for chunk in data.get("chunks") or []:
                if not isinstance(chunk, dict):
                    continue
                yield chunk.get("text", "")
                yield chunk.get("title", "")
                yield chunk.get("source", "")
                yield chunk.get("chunk_id", "")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> List[Dict[str, Any]]:
        """Parse every line in the JSONL file.

        Silently skips malformed lines.
        """
        if not self.traces_path.exists():
            return []

        traces: List[Dict[str, Any]] = []
        with self.traces_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed trace line: %s", line[:80])
        return traces
