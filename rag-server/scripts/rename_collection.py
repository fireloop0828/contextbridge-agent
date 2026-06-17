#!/usr/bin/env python
"""Rename a knowledge base collection (data-preserving).

This script migrates an existing collection name (e.g. "knowledge_hub") to a new
name (e.g. "travel_plan") WITHOUT changing content:

- ChromaDB: copy all vectors/documents/metadatas to a new collection, then delete old
- BM25: move index directory data/db/bm25/<old> -> data/db/bm25/<new>
- Images: move data/images/<old> -> data/images/<new> (if exists)
- Ingestion history: update ingestion_history.db collection field

Usage:
  python scripts/rename_collection.py --old knowledge_hub --new travel_plan

Notes:
  - Requires rag-server dependencies (chromadb) installed.
  - Safe to re-run: will refuse if target collection already exists.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rename a knowledge base collection")
    p.add_argument("--old", required=True, help="Old collection name (source)")
    p.add_argument("--new", required=True, help="New collection name (target)")
    return p.parse_args()


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(repo_root: Path, rel: str) -> Path:
    # Keep consistent with src.core.settings.resolve_path behavior (repo-root relative).
    return (repo_root / rel).resolve()


def _migrate_chroma(repo_root: Path, persist_dir: Path, old: str, new: str) -> None:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )

    existing = {c.name for c in client.list_collections()}
    if old not in existing:
        raise RuntimeError(f"Source collection not found in ChromaDB: {old!r}")
    if new in existing:
        raise RuntimeError(f"Target collection already exists in ChromaDB: {new!r}")

    src = client.get_collection(name=old)
    dst = client.get_or_create_collection(name=new, metadata={"hnsw:space": "cosine"})

    payload = src.get(include=["embeddings", "documents", "metadatas"])
    ids = payload.get("ids") or []
    if not ids:
        # Empty is allowed: still create new and delete old for consistency.
        client.delete_collection(old)
        return

    embeddings = payload.get("embeddings")
    documents = payload.get("documents")
    metadatas = payload.get("metadatas")

    # Use upsert for idempotency.
    dst.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    # Delete old collection after successful copy.
    client.delete_collection(old)


def _move_dir_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise RuntimeError(f"Target path already exists: {dst}")
    shutil.move(str(src), str(dst))


def _update_ingestion_history(repo_root: Path, old: str, new: str) -> None:
    db_path = _resolve_path(repo_root, "data/db/ingestion_history.db")
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE ingestion_history SET collection = ? WHERE collection = ?",
            (new, old),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    args = _parse_args()
    old = args.old.strip()
    new = args.new.strip()
    if not old or not new:
        raise SystemExit("old/new collection names must be non-empty")
    if old == new:
        raise SystemExit("old and new collection names are the same")

    repo_root = _resolve_repo_root()

    # Load settings for persist directory if possible; fall back to default.
    persist_dir = _resolve_path(repo_root, "data/db/chroma")
    try:
        from src.core.settings import load_settings, resolve_path as core_resolve_path

        s = load_settings()
        persist_dir = core_resolve_path(getattr(s.vector_store, "persist_directory", "./data/db/chroma"))
    except Exception:
        pass

    print(f"[1/4] Migrating ChromaDB: {old} -> {new}")
    _migrate_chroma(repo_root, persist_dir=persist_dir, old=old, new=new)

    print("[2/4] Moving BM25 index directory (if exists)")
    _move_dir_if_exists(
        _resolve_path(repo_root, f"data/db/bm25/{old}"),
        _resolve_path(repo_root, f"data/db/bm25/{new}"),
    )

    print("[3/4] Moving image directory (if exists)")
    _move_dir_if_exists(
        _resolve_path(repo_root, f"data/images/{old}"),
        _resolve_path(repo_root, f"data/images/{new}"),
    )

    print("[4/4] Updating ingestion history DB (if exists)")
    _update_ingestion_history(repo_root, old=old, new=new)

    print("Done.")


if __name__ == "__main__":
    # Ensure repo root is on sys.path when invoked directly.
    import sys

    sys.path.insert(0, str(_resolve_repo_root()))
    main()

