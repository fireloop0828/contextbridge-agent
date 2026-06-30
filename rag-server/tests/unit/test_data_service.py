"""Unit tests for DataService list_documents collection scoping."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import MagicMock, patch

from src.ingestion.document_manager import DocumentInfo
from src.observability.dashboard.services.data_service import DataService


class TestDataServiceListDocuments:
    def test_list_all_collections_counts_per_collection_store(self) -> None:
        """All-docs listing must query each doc's collection, not default only."""
        svc = DataService()
        manager = MagicMock()

        alpha_doc = DocumentInfo(
            source_path="a.pdf",
            source_hash="hash_a",
            collection="agent_notes",
            chunk_count=33,
            image_count=0,
            processed_at="2026-06-30T08:00:00+00:00",
        )
        travel_doc = DocumentInfo(
            source_path="b.pdf",
            source_hash="hash_b",
            collection="travel_plan",
            chunk_count=12,
            image_count=2,
            processed_at="2026-06-30T09:00:00+00:00",
        )

        def _list_documents(collection: str | None = None):
            if collection == "agent_notes":
                return [alpha_doc]
            if collection == "travel_plan":
                return [travel_doc]
            return []

        manager.list_documents.side_effect = _list_documents

        with patch.object(svc, "_ensure_stores") as ensure_stores, patch(
            "src.libs.loader.file_integrity.SQLiteIntegrityChecker"
        ) as integrity_cls:
            integrity_cls.return_value.list_processed.return_value = [
                {"collection": "agent_notes", "file_hash": "hash_a"},
                {"collection": "travel_plan", "file_hash": "hash_b"},
            ]
            svc._manager = manager

            docs = svc.list_documents()

        assert ensure_stores.call_args_list == [
            (("agent_notes",),),
            (("travel_plan",),),
        ]
        assert [d["collection"] for d in docs] == ["agent_notes", "travel_plan"]
        assert docs[0]["chunk_count"] == 33
        assert docs[1]["chunk_count"] == 12
        assert docs[1]["image_count"] == 2

    def test_list_single_collection_uses_requested_store(self) -> None:
        svc = DataService()
        manager = MagicMock()
        manager.list_documents.return_value = [
            DocumentInfo(
                source_path="a.pdf",
                source_hash="hash_a",
                collection="agent_notes",
                chunk_count=5,
            )
        ]
        svc._manager = manager

        with patch.object(svc, "_ensure_stores") as ensure_stores:
            docs = svc.list_documents("agent_notes")

        ensure_stores.assert_called_once_with("agent_notes")
        manager.list_documents.assert_called_once_with("agent_notes")
        assert docs == [asdict(manager.list_documents.return_value[0])]
