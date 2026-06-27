"""Unit tests for collection catalog loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.collection_catalog import (
    CollectionCatalogEntry,
    get_catalog_entry,
    load_collection_catalog,
)


def test_load_collection_catalog_from_repo_file() -> None:
    catalog = load_collection_catalog()
    assert "travel_plan" in catalog
    assert "agent_notes" in catalog
    assert catalog["travel_plan"].description
    assert isinstance(catalog["travel_plan"].topics, list)


def test_load_collection_catalog_missing_file(tmp_path: Path) -> None:
    assert load_collection_catalog(tmp_path / "missing.yaml") == {}


def test_load_collection_catalog_skips_empty_description(tmp_path: Path) -> None:
    path = tmp_path / "collections.yaml"
    path.write_text(
        "collections:\n  ok:\n    description: has text\n  bad:\n    description: ''\n",
        encoding="utf-8",
    )
    catalog = load_collection_catalog(path)
    assert list(catalog.keys()) == ["ok"]


def test_get_catalog_entry() -> None:
    catalog = load_collection_catalog()
    entry = get_catalog_entry("travel_plan", catalog=catalog)
    assert entry is not None
    assert entry.name == "travel_plan"
    assert get_catalog_entry("nonexistent", catalog=catalog) is None
