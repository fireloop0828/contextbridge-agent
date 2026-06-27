"""Data Browser page – browse ingested documents, chunks, and images.

Layout:
1. Collection selector (sidebar)
2. Document list with chunk counts
3. Expandable document detail → chunk cards with text + metadata
4. Image preview gallery
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ingestion.document_manager import source_display_name
from src.observability.dashboard.services.data_service import DataService


def render() -> None:
    """Render the Data Browser page."""
    st.header("🔍 知识浏览")

    try:
        svc = DataService()
    except Exception as exc:
        st.error(f"初始化 DataService 失败：{exc}")
        return

    # ── Collection selector ────────────────────────────────────────
    # Prefer the default collection from settings.yaml when available.
    default_collection = "default"
    try:
        from src.core.settings import load_settings

        settings = load_settings()
        if getattr(settings, "vector_store", None) and getattr(settings.vector_store, "collection_name", None):
            cand = settings.vector_store.collection_name
            if isinstance(cand, str) and cand.strip():
                default_collection = cand.strip()
    except Exception:
        pass

    collections = svc.list_collections()
    if not isinstance(collections, list):
        collections = ["default"]
    if "default" not in collections:
        collections.insert(0, "default")
    if default_collection not in collections:
        collections.insert(0, default_collection)

    default_index = 0
    try:
        default_index = collections.index(default_collection)
    except ValueError:
        default_index = 0
    collection = st.selectbox(
        "知识库",
        options=collections,
        index=default_index,
        key="db_collection_filter",
        help="选择要浏览的 collection（知识库分区）。",
    )
    coll_arg = collection if collection else None

    # ── Document list ──────────────────────────────────────────────
    try:
        docs = svc.list_documents(coll_arg)
    except Exception as exc:
        st.error(f"加载文档列表失败：{exc}")
        return

    if not docs:
        st.info(
            "**当前知识库中没有文档。** "
            "请前往「文档入库」页面上传文件，"
            "或在上方选择其他知识库。"
        )
        return

    st.subheader(f"📄 文档列表 ({len(docs)})")

    for idx, doc in enumerate(docs):
        display_name = source_display_name(doc["source_path"])
        label = f"📑 {display_name}  —  {doc['chunk_count']} 个分块 · {doc['image_count']} 张图片"
        with st.expander(label, expanded=(len(docs) == 1)):
            # ── Document metadata ──────────────────────────────────
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("分块数", doc["chunk_count"])
            col_b.metric("图片数", doc["image_count"])
            col_c.metric("知识库", doc.get("collection", "—"))
            st.caption(
                f"**文件名：** {display_name}  ·  "
                f"**哈希：** `{doc['source_hash'][:16]}…`  ·  "
                f"**处理时间：** {doc.get('processed_at', '—')}"
            )

            st.divider()

            # ── Chunk cards ────────────────────────────────────────
            chunks = svc.get_chunks(doc["source_hash"], coll_arg)
            if chunks:
                st.markdown(f"### 📦 分块 ({len(chunks)})")
                for cidx, chunk in enumerate(chunks):
                    text = chunk.get("text", "")
                    meta = chunk.get("metadata", {})
                    chunk_id = chunk["id"]

                    # Title from metadata or first line
                    title = meta.get("title", "")
                    if not title:
                        title = text[:60].replace("\n", " ").strip()
                        if len(text) > 60:
                            title += "…"

                    with st.container(border=True):
                        st.markdown(
                            f"**分块 {cidx + 1}** · `{chunk_id[-16:]}` · "
                            f"{len(text)} 字符"
                        )
                        # Show the actual chunk text (scrollable)
                        _height = max(120, min(len(text) // 2, 600))
                        st.text_area(
                            "内容",
                            value=text,
                            height=_height,
                            disabled=True,
                            key=f"chunk_text_{idx}_{cidx}",
                            label_visibility="collapsed",
                        )
                        # Expandable metadata
                        with st.expander("📋 元数据", expanded=False):
                            st.json(meta)
            else:
                st.caption("向量库中未找到该文档的分块。")

            # ── Image preview ──────────────────────────────────────
            images = svc.get_images(doc["source_hash"], coll_arg)
            if images:
                st.divider()
                st.markdown(f"### 🖼️ 图片 ({len(images)})")
                img_cols = st.columns(min(len(images), 4))
                for iidx, img in enumerate(images):
                    with img_cols[iidx % len(img_cols)]:
                        img_path = Path(img.get("file_path", ""))
                        if img_path.exists():
                            st.image(str(img_path), caption=img["image_id"], width=200)
                        else:
                            st.caption(f"{img['image_id']}（文件缺失）")
