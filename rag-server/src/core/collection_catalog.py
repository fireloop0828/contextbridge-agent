"""Load collection registry (name → description) for Agent-facing list_collections."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.core.settings import resolve_path

DEFAULT_CATALOG_PATH = resolve_path("config/collections.yaml")


@dataclass(frozen=True)
class CollectionCatalogEntry:
    """Human-readable catalog entry for one collection."""

    name: str
    description: str
    use_when: str = ""
    topics: List[str] = field(default_factory=list)


def load_collection_catalog(
    path: Optional[Path] = None,
) -> Dict[str, CollectionCatalogEntry]:
    """Load ``config/collections.yaml`` into a name → entry map.

    Missing file or parse errors return an empty dict (list_collections still works).
    """
    catalog_path = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    if not catalog_path.exists():
        return {}

    try:
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}

    entries: Dict[str, CollectionCatalogEntry] = {}
    collections = raw.get("collections")
    if not isinstance(collections, dict):
        return entries

    for name, data in collections.items():
        key = str(name).strip()
        if not key:
            continue
        if not isinstance(data, dict):
            continue
        description = str(data.get("description") or "").strip()
        if not description:
            continue
        use_when = str(data.get("use_when") or "").strip()
        topics_raw = data.get("topics") or []
        topics = [str(t).strip() for t in topics_raw if str(t).strip()]
        entries[key] = CollectionCatalogEntry(
            name=key,
            description=description,
            use_when=use_when,
            topics=topics,
        )

    return entries


def get_catalog_entry(
    name: str,
    catalog: Optional[Dict[str, CollectionCatalogEntry]] = None,
) -> Optional[CollectionCatalogEntry]:
    """Look up one collection in the catalog."""
    if catalog is None:
        catalog = load_collection_catalog()
    return catalog.get(name)
