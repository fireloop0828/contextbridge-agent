"""Factory for selecting document loaders by file extension."""

from __future__ import annotations

from pathlib import Path

from src.libs.loader.base_loader import BaseLoader
from src.libs.loader.pdf_loader import PdfLoader
from src.libs.loader.txt_loader import TxtLoader

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}


def get_loader_for_path(
    file_path: str | Path,
    *,
    collection: str = "default",
    image_storage_dir: str | None = None,
) -> BaseLoader:
    """Return the appropriate loader for *file_path*."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        storage = image_storage_dir or f"data/images/{collection}"
        return PdfLoader(extract_images=True, image_storage_dir=storage)
    if suffix == ".txt":
        return TxtLoader()
    raise ValueError(
        f"Unsupported file type: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )
