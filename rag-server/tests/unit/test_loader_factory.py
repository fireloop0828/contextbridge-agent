"""Tests for document loader factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.libs.loader.loader_factory import SUPPORTED_EXTENSIONS, get_loader_for_path
from src.libs.loader.txt_loader import TxtLoader


def test_supported_extensions_include_markdown_and_docx() -> None:
    assert ".md" in SUPPORTED_EXTENSIONS
    assert ".docx" in SUPPORTED_EXTENSIONS


def test_get_loader_for_md(tmp_path: Path) -> None:
    md_file = tmp_path / "travel-plan-洛阳.md"
    md_file.write_text("# 洛阳\n\n龙门石窟必玩。", encoding="utf-8")

    loader = get_loader_for_path(md_file)
    assert isinstance(loader, TxtLoader)

    document = loader.load(md_file)
    assert "龙门石窟" in document.text
    assert document.metadata["doc_type"] == "md"


def test_get_loader_rejects_unknown_suffix(tmp_path: Path) -> None:
    bad = tmp_path / "notes.xyz"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file type"):
        get_loader_for_path(bad)
