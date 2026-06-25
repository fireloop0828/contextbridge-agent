"""Ingestion Manager page – upload files, trigger ingestion, delete documents.

Layout:
1. File uploader + collection selector
2. Ingest button → progress bar (using on_progress callback)
3. Document list with delete buttons
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st

from src.ingestion.document_manager import source_display_name
from src.observability.dashboard.services.data_service import DataService


def _run_ingestion(
    uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile",
    collection: str,
    progress_bar: "st.delta_generator.DeltaGenerator",
    status_text: "st.delta_generator.DeltaGenerator",
) -> None:
    """Save the uploaded file to a temp location and run the pipeline."""
    from src.core.settings import load_settings
    from src.core.trace import TraceContext, TraceCollector
    from src.ingestion.pipeline import IngestionPipeline

    settings = load_settings()

    # Write uploaded file to a temp location
    suffix = Path(uploaded_file.name).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    _STAGE_LABELS = {
        "integrity": "🔍 检查文件完整性…",
        "load": "📄 加载文档…",
        "split": "✂️ 分块处理…",
        "transform": "🔄 转换分块（LLM 精炼 + 增强）…",
        "embed": "🔢 编码向量…",
        "upsert": "💾 写入数据库…",
    }

    def on_progress(stage: str, current: int, total: int) -> None:
        frac = (current - 1) / total  # stage just started, show partial progress
        label = _STAGE_LABELS.get(stage, stage)
        progress_bar.progress(frac, text=f"[{current}/{total}] {label}")
        status_text.caption(label)

    trace = TraceContext(trace_type="ingestion")
    trace.metadata["source_path"] = uploaded_file.name
    trace.metadata["collection"] = collection
    trace.metadata["source"] = "dashboard"

    try:
        pipeline = IngestionPipeline(settings, collection=collection)
        result = pipeline.run(
            file_path=tmp_path,
            trace=trace,
            on_progress=on_progress,
            source_path=uploaded_file.name,
        )
        if not result.success:
            error_msg = result.error or "未知错误"
            status_text.error(f"入库失败：{error_msg}")
            return
        progress_bar.progress(1.0, text="✅ 完成")
        status_text.success(f"已成功将 **{uploaded_file.name}** 入库到知识库 **{collection}**。")
    except Exception as exc:
        trace.metadata["error"] = str(exc)
        trace.record_stage("load", {
            "error": str(exc),
            "method": Path(uploaded_file.name).suffix.lstrip(".") or "unknown",
        })
        status_text.error(f"入库失败：{exc}")
    finally:
        TraceCollector().collect(trace)
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def render() -> None:
    """Render the Ingestion Manager page."""
    st.header("📥 文档入库")

    # ── Upload section ─────────────────────────────────────────────
    st.subheader("📤 上传文件")

    # Default knowledge base name from settings.yaml (falls back to "default").
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

    uploaded = st.file_uploader(
        "选择文件",
        type=["pdf", "txt", "md", "docx"],
        key="ingest_uploader",
    )

    # Put knowledge base controls UNDER file picker (more space).
    kb_left, kb_right = st.columns([3, 2])
    with kb_right:
        create_new = st.toggle(
            "新增知识库",
            value=False,
            key="ingest_create_new_kb",
            help="关闭：从已有知识库中选择；开启：输入新知识库名（将自动创建）。",
        )
        st.caption("提示：开启后输入的新名称会创建为新的 collection。")

    with kb_left:
        if create_new:
            collection = st.text_input(
                "新知识库名称",
                value="",
                key="ingest_collection_new",
                placeholder="例如：travel_plan",
                help="将自动创建同名知识库（collection），并把本次文档写入其中。",
            )
        else:
            try:
                collections = DataService().list_collections()
            except Exception:
                collections = []
            if not isinstance(collections, list):
                collections = []

            # Ensure the configured default is always selectable.
            if default_collection and default_collection not in collections:
                collections.insert(0, default_collection)
            if "default" not in collections:
                collections.append("default")

            default_index = 0
            try:
                default_index = collections.index(default_collection)
            except Exception:
                default_index = 0

            collection = st.selectbox(
                "选择已有知识库",
                options=collections,
                index=default_index,
                key="ingest_collection_existing",
                help="选择一个已有知识库（collection）。如果你刚创建/入库了新库，刷新后下拉会自动同步。",
            )

    if uploaded is not None:
        if st.button("🚀 开始入库", key="btn_ingest"):
            progress_bar = st.progress(0, text="准备中…")
            status_text = st.empty()
            chosen = (collection or "").strip()
            if not chosen:
                chosen = default_collection or "default"
            _run_ingestion(uploaded, chosen, progress_bar, status_text)

    st.divider()

    # ── Document management section ────────────────────────────────
    st.subheader("🗑️ 已入库文档")

    try:
        svc = DataService()
        docs = svc.list_documents()
    except Exception as exc:
        st.error(f"加载文档列表失败：{exc}")
        return

    if not docs:
        st.info(
            "**尚无已入库的文档。** "
            "请在上方上传 PDF、TXT、MD 或 DOCX 文件，然后点击「开始入库」。"
        )
        return

    for idx, doc in enumerate(docs):
        display_name = source_display_name(doc["source_path"])
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{display_name}** — "
                f"知识库：`{doc.get('collection', '—')}` | "
                f"分块：{doc['chunk_count']} | "
                f"图片：{doc['image_count']}"
            )
        with col_btn:
            if st.button("🗑️ 删除", key=f"del_{idx}"):
                try:
                    result = svc.delete_document(
                        source_path=doc["source_path"],
                        collection=doc.get("collection", "default"),
                        source_hash=doc.get("source_hash"),
                    )
                    if result.success:
                        st.success(
                            f"已删除：移除 {result.chunks_deleted} 个分块、"
                            f"{result.images_deleted} 张图片。"
                        )
                        st.rerun()
                    else:
                        st.warning(f"部分删除失败。错误：{result.errors}")
                except Exception as exc:
                    st.error(f"删除失败：{exc}")
