"""Plain text (.txt) loader for the ingestion pipeline."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader


class TxtLoader(BaseLoader):
    """Load UTF-8 plain text and Markdown files into standardized Document objects."""

    _SUPPORTED_SUFFIXES = {".txt", ".md"}

    def load(self, file_path: str | Path) -> Document:
        path = self._validate_file(file_path)
        suffix = path.suffix.lower()
        if suffix not in self._SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported text file type: {suffix}. "
                f"Supported: {sorted(self._SUPPORTED_SUFFIXES)}"
            )

        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"

        try:
            text_content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text_content = path.read_text(encoding="utf-8", errors="replace")

        if not text_content.strip():
            raise ValueError(f"Text file is empty: {path}")

        metadata: Dict[str, Any] = {
            "source_path": str(path),
            "doc_type": "md" if suffix == ".md" else "txt",
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
