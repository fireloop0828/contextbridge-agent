"""Dashboard configuration reading service.

Wraps :class:`Settings` to provide formatted component information
for the Overview page.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.settings import Settings, load_settings


@dataclass
class ComponentInfo:
    """Summary of a single configured component."""

    name: str
    provider: str
    model: str
    extra: Dict[str, Any]


class ConfigService:
    """Read-only service that exposes application configuration.

    Args:
        settings_path: Path to ``settings.yaml``.
    """

    def __init__(self, settings_path: Optional[str] = None) -> None:
        self._settings_path = settings_path
        self._settings: Optional[Settings] = None

    # ── lazy load ────────────────────────────────────────────────────

    def _load(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings(self._settings_path)
        return self._settings

    def reload(self) -> None:
        """Force reload of settings from disk."""
        self._settings = None

    @property
    def settings(self) -> Settings:
        return self._load()

    # ── component cards ──────────────────────────────────────────────

    def get_component_cards(self) -> List[ComponentInfo]:
        """Return a list of component summaries for the Overview page."""
        s = self._load()
        cards: List[ComponentInfo] = []

        # LLM
        cards.append(ComponentInfo(
            name="大语言模型 (LLM)",
            provider=s.llm.provider,
            model=s.llm.model,
            extra={"温度": s.llm.temperature, "最大 token 数": s.llm.max_tokens},
        ))

        # Embedding
        cards.append(ComponentInfo(
            name="向量嵌入 (Embedding)",
            provider=s.embedding.provider,
            model=s.embedding.model,
            extra={"维度": s.embedding.dimensions},
        ))

        # VectorStore
        cards.append(ComponentInfo(
            name="向量存储",
            provider=s.vector_store.provider,
            model=s.vector_store.collection_name,
            extra={"持久化目录": s.vector_store.persist_directory},
        ))

        # Retrieval
        cards.append(ComponentInfo(
            name="混合检索",
            provider="hybrid",
            model="dense + sparse + RRF",
            extra={
                "稠密 Top-K": s.retrieval.dense_top_k,
                "稀疏 Top-K": s.retrieval.sparse_top_k,
                "融合 Top-K": s.retrieval.fusion_top_k,
            },
        ))

        # Rerank
        cards.append(ComponentInfo(
            name="重排序 (Reranker)",
            provider=s.rerank.provider if s.rerank.enabled else "已禁用",
            model=s.rerank.model if s.rerank.enabled else "-",
            extra={"已启用": s.rerank.enabled, "Top-K": s.rerank.top_k},
        ))

        # Vision LLM
        if s.vision_llm and s.vision_llm.enabled:
            cards.append(ComponentInfo(
                name="视觉大模型",
                provider=s.vision_llm.provider,
                model=s.vision_llm.model,
                extra={"最大图片尺寸": s.vision_llm.max_image_size},
            ))

        # Ingestion
        if s.ingestion:
            cards.append(ComponentInfo(
                name="文档摄取",
                provider=s.ingestion.splitter,
                model="-",
                extra={
                    "分块大小": s.ingestion.chunk_size,
                    "分块重叠": s.ingestion.chunk_overlap,
                    "批大小": s.ingestion.batch_size,
                },
            ))

        return cards
