"""知识库问答模式：RAG 工具的确定性调用与结果解析。

本模块自包含，不依赖其他模式包（如 modes.travel），
只模仿必要的工具调用/结果解析逻辑，保证模式包之间互不影响。
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

EXCERPT_MAX = 400


# ---------------------------------------------------------------------------
# 工具调用（确定性，不经 LLM 决策）
# ---------------------------------------------------------------------------
def tools_by_name(tools: list[Any]) -> dict[str, Any]:
    return {getattr(t, "name", ""): t for t in tools if getattr(t, "name", None)}


async def call_tool(tools_map: dict[str, Any], name: str, args: dict[str, Any]) -> Any:
    tool = tools_map.get(name)
    if not tool:
        raise RuntimeError(f"工具未连接：{name}")
    return await tool.ainvoke(args)


def tool_result_to_text(result: Any) -> str:
    """将 LangChain/MCP 工具返回值统一为文本。"""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


# ---------------------------------------------------------------------------
# JSON 解析辅助
# ---------------------------------------------------------------------------
def try_parse_json(text: str) -> Any | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# RAG 检索结果解析（模仿 travel 的 parse_rag_results，但独立实现）
# ---------------------------------------------------------------------------
def _basename(path: str) -> str:
    return os.path.basename(path.replace("\\", "/"))


def _is_rag_boilerplate(excerpt: str) -> bool:
    """跳过检索头、引用列表等非正文片段。"""
    s = (excerpt or "").strip()
    # 极短片段（<10 字符）视为无有效信息；10 字符以上的正常引用予以保留
    if not s or len(s) < 10:
        return True
    if re.match(r"^#+\s*检索结果", s):
        return True
    if "针对查询" in s and "找到" in s and "条相关结果" in s:
        return True
    if s.startswith("## 引用来源") or s.startswith("引用来源"):
        return True
    return False


def _iter_rag_content_blocks(text: str) -> list[str]:
    """按 `### [N]` 切分 RAG 正文块，跳过顶部的检索摘要头。"""
    parts = re.split(r"###\s*\[\d+\]", text)
    if len(parts) > 1:
        return [p for p in parts[1:] if p.strip()]
    return []


def parse_rag_results(
    raw: Any, *, query: str, collection: str = ""
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """解析 query_knowledge_hub 返回：正文块与 JSON citations 两种形态。"""
    text = tool_result_to_text(raw)
    if "未找到相关结果" in text or "未找到与查询相关" in text:
        return [], _build_rag_meta(query=query, collection=collection, raw_count=0)

    out: list[dict[str, Any]] = []
    for block in _iter_rag_content_blocks(text):
        if not block.strip():
            continue
        source_m = re.search(r"\*\*来源:\*\*\s*`?([^`\n]+)`?", block)
        score_m = re.search(r"\*\*相关度:\*\*\s*([^\n]+)", block)
        quote_m = re.search(r">\s*(.+?)(?:\n\n|\n###|\Z)", block, re.DOTALL)
        excerpt = (quote_m.group(1) if quote_m else "").strip()
        if not excerpt:
            continue
        excerpt = re.sub(r"\s+", " ", excerpt)
        if len(excerpt) > EXCERPT_MAX:
            excerpt = excerpt[:EXCERPT_MAX] + "…"
        if _is_rag_boilerplate(excerpt):
            continue
        source_doc = _basename(source_m.group(1).strip()) if source_m else ""
        out.append(
            {
                "id": f"RAG-{len(out) + 1}",
                "collection": collection,
                "query": query,
                "excerpt": excerpt,
                "source_doc": source_doc,
                "score": (score_m.group(1).strip() if score_m else ""),
            }
        )

    if not out:
        cit_data = try_parse_json(text)
        if isinstance(cit_data, dict):
            citations = cit_data.get("citations") or []
            if isinstance(citations, list):
                for item in citations:
                    if not isinstance(item, dict):
                        continue
                    excerpt = (item.get("content") or item.get("excerpt") or "").strip()
                    if not excerpt or _is_rag_boilerplate(excerpt):
                        continue
                    out.append(
                        {
                            "id": f"RAG-{len(out) + 1}",
                            "collection": collection,
                            "query": query,
                            "excerpt": excerpt[:EXCERPT_MAX],
                            "source_doc": _basename(
                                str(item.get("source") or item.get("file") or "")
                            ),
                            "score": str(item.get("score") or ""),
                        }
                    )

    return out, _build_rag_meta(query=query, collection=collection, raw_count=len(out))


def _build_rag_meta(
    *, query: str, collection: str, raw_count: int
) -> dict[str, Any]:
    meta: dict[str, Any] = {"query": query, "collection": collection, "raw_count": raw_count}
    if raw_count == 0:
        meta["notice"] = "未找到与查询相关的知识库内容。"
    return meta


# ---------------------------------------------------------------------------
# 来源块格式化（界面在回答后程序化追加，保证格式稳定、不依赖 LLM）
# ---------------------------------------------------------------------------
SOURCE_EXCERPT_LEN = 24


def _source_excerpt(text: str) -> str:
    """去掉 markdown 符号、压缩空白，截前 N 字作为来源要点。"""
    s = re.sub(r"[#*`>_~|\[\]()]", "", text or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip("-·")
    if len(s) > SOURCE_EXCERPT_LEN:
        s = s[:SOURCE_EXCERPT_LEN] + "…"
    return s


def _score_value(item: dict[str, Any]) -> float:
    try:
        return float(item.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def format_sources_block(rag_results: list[dict[str, Any]]) -> str:
    """将检索结果按来源文档去重，生成用户可读的来源块。

    同一文档多条命中取相关度最高的一条；要点为 excerpt 前 N 字。
    无来源时返回空串（界面不追加任何内容）。
    """
    if not rag_results:
        return ""
    best: dict[str, dict[str, Any]] = {}
    for item in rag_results:
        src = str(item.get("source_doc") or "").strip()
        if not src:
            continue
        prev = best.get(src)
        if prev is None or _score_value(item) > _score_value(prev):
            best[src] = item
    if not best:
        return ""
    lines: list[str] = []
    for src, item in best.items():
        snippet = _source_excerpt(item.get("excerpt"))
        lines.append(f"- {src}（{snippet}）" if snippet else f"- {src}")
    return "\n---\n（来源：\n" + "\n".join(lines) + "）"


# ---------------------------------------------------------------------------
# 集合列表缓存（session 级，key 与模式隔离，互不影响）
# ---------------------------------------------------------------------------
def get_cached_collections() -> list[str]:
    import streamlit as st

    raw = st.session_state.get("knowledge_qa_collections_cache") or []
    return [str(x) for x in raw if x]


_MD_COLLECTION_LINE_RE = re.compile(r"^\s*\d+\.\s*\*\*(.+?)\*\*")


def parse_collections_from_tool_output(text: str) -> list[str]:
    """从 list_collections 工具输出提取集合名。

    支持两种形态：
    1. JSON：``{"collections": [...]}`` 或 ``[{...}, ...]``
    2. Markdown（rag-server 默认输出）：``1. **travel_plan** - 5 documents``
    """
    found: list[str] = []
    data = try_parse_json(text)
    if isinstance(data, dict):
        items = (
            data.get("collections")
            or data.get("files")
            or data.get("data")
            or list(data.keys())
        )
    elif isinstance(data, list):
        items = data
    else:
        items = []
    for item in items or []:
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, dict):
            cname = item.get("name") or item.get("collection") or item.get("id")
            if cname:
                found.append(str(cname))
    if not found:
        # Markdown 形态：形如 `1. **travel_plan** - 5 documents` 的行
        for line in (text or "").splitlines():
            m = _MD_COLLECTION_LINE_RE.match(line)
            if m:
                cname = m.group(1).strip()
                if cname:
                    found.append(cname)
    return list(dict.fromkeys(found))


def cache_collections(names: list[str]) -> None:
    import streamlit as st

    merged = list(dict.fromkeys(get_cached_collections() + [n for n in names if n]))
    if merged:
        st.session_state["knowledge_qa_collections_cache"] = merged


async def fetch_collections(tools_map: dict[str, Any]) -> list[str]:
    """确定性获取集合列表，优先读 session 缓存，miss 时调用 list_collections。"""
    cached = get_cached_collections()
    if cached:
        return cached
    if "list_collections" not in tools_map:
        return []
    try:
        raw = await call_tool(tools_map, "list_collections", {"include_stats": True})
        found = parse_collections_from_tool_output(tool_result_to_text(raw))
        cache_collections(found)
        return found
    except Exception as exc:
        logger.warning("list_collections failed: %s", exc)
        return get_cached_collections()
