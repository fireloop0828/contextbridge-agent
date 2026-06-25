"""Office / structured document loader via MarkItDown (e.g. DOCX)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict

try:
    from markitdown import MarkItDown

    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader

_SUPPORTED_SUFFIXES = {".docx"}


class MarkItDownLoader(BaseLoader):
    """Load DOCX and similar formats using MarkItDown."""

    def __init__(self) -> None:
        if not MARKITDOWN_AVAILABLE:
            raise ImportError(
                "MarkItDown is required for MarkItDownLoader. "
                "Install with: pip install markitdown"
            )
        self._markitdown = MarkItDown()

    def load(self, file_path: str | Path) -> Document:
        path = self._validate_file(file_path)
        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported file type for MarkItDownLoader: {suffix}. "
                f"Supported: {sorted(_SUPPORTED_SUFFIXES)}"
            )

        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"

        try:
            result = self._markitdown.convert(str(path))
            text_content = (
                result.text_content if hasattr(result, "text_content") else str(result)
            )
        except Exception as exc:
            raise RuntimeError(f"Document parsing failed: {exc}") from exc

        if not (text_content or "").strip():
            raise ValueError(f"Document contains no extractable text: {path}")

        metadata: Dict[str, Any] = {
            "source_path": str(path),
            "doc_type": suffix.lstrip("."),
            "doc_hash": doc_hash,
            "title": path.stem,
        }

        return Document(id=doc_id, text=text_content, metadata=metadata)

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
