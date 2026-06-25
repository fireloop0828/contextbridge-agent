"""Tests for pipeline source_path (logical document name)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.pipeline import IngestionPipeline


@pytest.fixture()
def md_file(tmp_path: Path) -> Path:
    p = tmp_path / "tmp_upload.md"
    p.write_text("# 标题\n\n正文内容。", encoding="utf-8")
    return p


def test_run_uses_source_path_for_metadata_and_integrity(md_file: Path) -> None:
  settings = MagicMock()
  settings.ingestion.batch_size = 10
  settings.embedding.provider = "openai"
  settings.vector_store.provider = "chroma"
  settings.vector_store.persist_directory = "data/db/chroma"

  document = MagicMock()
  document.id = "doc_test"
  document.text = "# 标题\n\n正文内容。"
  document.metadata = {"doc_type": "md", "source_path": str(md_file), "images": []}

  chunks = [MagicMock()]
  chunks[0].id = "c1"
  chunks[0].text = "正文"
  chunks[0].metadata = {"source_path": str(md_file), "chunk_index": 0}

  with (
      patch.object(IngestionPipeline, "__init__", lambda self, *a, **k: None),
      patch("src.ingestion.pipeline.load_settings", return_value=settings),
  ):
      pipeline = IngestionPipeline.__new__(IngestionPipeline)
      pipeline.settings = settings
      pipeline.collection = "default"
      pipeline.force = False
      pipeline.integrity_checker = MagicMock()
      pipeline.integrity_checker.compute_sha256.return_value = "abc" * 10 + "abcd"
      pipeline.integrity_checker.should_skip.return_value = False
      pipeline._image_storage_dir = "data/images/default"
      pipeline.chunker = MagicMock()
      pipeline.chunker.split_document.return_value = chunks
      pipeline.chunk_refiner = MagicMock()
      pipeline.chunk_refiner.refine_chunks.return_value = (chunks, {"llm": 0, "rule": 1})
      pipeline.metadata_enricher = MagicMock()
      pipeline.metadata_enricher.enrich_chunks.return_value = (chunks, {"llm": 0, "rule": 1})
      pipeline.image_captioner = MagicMock()
      pipeline.image_captioner.caption_chunks.return_value = (chunks, 0)
      pipeline.batch_processor = MagicMock()
      pipeline.batch_processor.process.return_value = MagicMock(
          dense_vectors=[[0.1, 0.2]],
          sparse_stats=[{}],
          errors=[],
      )
      pipeline.vector_upserter = MagicMock()
      pipeline.vector_upserter.upsert.return_value = ["vec1"]
      pipeline.bm25_indexer = MagicMock()
      pipeline.image_storage = MagicMock()
      pipeline.image_storage.list_images.return_value = []

      with patch("src.ingestion.pipeline.get_loader_for_path") as mock_loader_factory:
          loader = MagicMock()
          loader.load.return_value = document
          mock_loader_factory.return_value = loader

          result = pipeline.run(
              str(md_file),
              source_path="travel-plan-洛阳.md",
          )

      assert result.success is True
      assert document.metadata["source_path"] == "travel-plan-洛阳.md"
      pipeline.integrity_checker.mark_success.assert_called_once()
      assert pipeline.integrity_checker.mark_success.call_args[0][1] == "travel-plan-洛阳.md"
