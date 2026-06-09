"""旅行模式：O10 RAG 集合缓存 + O7 跨回合工具结论长期记忆。"""

from __future__ import annotations

import json
import re
from typing import Any

# 写入长期记忆时，单条工具输出摘要上限（仅影响「后续回合」注入，不截断当轮 ReAct）
TOOL_ENTRY_SUMMARY_MAX = 500
# 注入 [TRAVEL_CONTEXT] 时最多携带最近 N 个回合的工具记忆
TOOL_MEMORY_INJECT_TURNS = 6

_RAG_TOOL_NAMES = frozenset(
    {"list_collections", "query_knowledge_hub", "get_document_summary"}
)
_MAP_TOOL_PREFIX = "maps_"


def init_travel_tool_memory() -> None:
    import streamlit as st

    if "travel_tool_memory" not in st.session_state:
        st.session_state.travel_tool_memory = []
    if "rag_collections_cache" not in st.session_state:
        st.session_state.rag_collections_cache = []


def clear_travel_tool_memory() -> None:
    import streamlit as st

    st.session_state.travel_tool_memory = []
    st.session_state.rag_collections_cache = []


def get_cached_rag_collections() -> list[str]:
    import streamlit as st

    init_travel_tool_memory()
    raw = st.session_state.get("rag_collections_cache") or []
    return [str(x) for x in raw if x]


def _extract_tool_name_from_json_blob(blob: str) -> str | None:
    for pattern in (
        r'"name"\s*:\s*"([^"]+)"',
        r"'name'\s*:\s*'([^']+)'",
    ):
        m = re.search(pattern, blob)
        if m:
            return m.group(1)
    return None


def _summarize_tool_content(tool_name: str, content: str) -> str:
    """规则摘要（后续可换 LLM 二次摘要）；当轮仍保留完整 tool 输出。"""
    text = (content or "").strip()
    if not text:
        return ""
    if tool_name == "list_collections":
        return text[:TOOL_ENTRY_SUMMARY_MAX]
    if tool_name in _RAG_TOOL_NAMES:
        return text[:TOOL_ENTRY_SUMMARY_MAX]
    if tool_name.startswith(_MAP_TOOL_PREFIX) or tool_name == "get_current_time":
        return text[:TOOL_ENTRY_SUMMARY_MAX]
    return text[:TOOL_ENTRY_SUMMARY_MAX]


def _split_tool_blocks(tool_output_text: str) -> list[tuple[str, str]]:
    """从流式拼接的 tool 展示文本中粗分工具块。"""
    if not tool_output_text or not tool_output_text.strip():
        return []
    blocks: list[tuple[str, str]] = []
    parts = re.split(r"```json\s*", tool_output_text)
    for part in parts[1:]:
        if "```" in part:
            blob, _ = part.split("```", 1)
        else:
            blob = part
        blob = blob.strip()
        if not blob:
            continue
        name = _extract_tool_name_from_json_blob(blob) or "unknown_tool"
        blocks.append((name, blob))
    if not blocks and tool_output_text.strip():
        blocks.append(("tool_output", tool_output_text.strip()[:2000]))
    return blocks


def try_cache_rag_collections_from_tool_output(tool_output_text: str) -> list[str]:
    """
    解析 list_collections 工具返回，写入 session（O10）。
    返回本次解析到的 collection 名列表。
    """
    import streamlit as st

    init_travel_tool_memory()
    found: list[str] = []
    for name, blob in _split_tool_blocks(tool_output_text):
        if name != "list_collections":
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        items = data
        if isinstance(data, dict):
            items = data.get("collections") or data.get("files") or data.get("data") or []
        if isinstance(items, dict):
            items = list(items.keys())
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    found.append(item)
                elif isinstance(item, dict):
                    cname = item.get("name") or item.get("collection") or item.get("id")
                    if cname:
                        found.append(str(cname))
    if found:
        merged = list(dict.fromkeys(st.session_state.rag_collections_cache + found))
        st.session_state.rag_collections_cache = merged
    return found


def ingest_tool_round_memory(*, phase: str, tool_output_text: str) -> None:
    """
    O7：本回合结束后，将 tool 输出摘要写入长期记忆表。
    当轮 ReAct 内仍为完整 ToolMessage；仅影响后续回合 [TRAVEL_CONTEXT] 注入。
    """
    import streamlit as st

    if not tool_output_text or not tool_output_text.strip():
        return
    init_travel_tool_memory()
    try_cache_rag_collections_from_tool_output(tool_output_text)

    entries: list[dict[str, str]] = []
    for tool_name, blob in _split_tool_blocks(tool_output_text):
        summary = _summarize_tool_content(tool_name, blob)
        if summary:
            entries.append({"tool": tool_name, "summary": summary})

    if not entries:
        return

    memory: list[dict[str, Any]] = st.session_state.travel_tool_memory
    memory.append({"phase": phase, "tools": entries})
    st.session_state.travel_tool_memory = memory[-TOOL_MEMORY_INJECT_TURNS:]


def trim_checkpoint_after_tool_ingest() -> None:
    """
    O4：工具结论已写入 travel_tool_memory 后，重置 Agent thread_id。

    避免 LangGraph checkpoint 与 [TRAVEL_CONTEXT] 注入的工具摘要重复占 Token。
    UI 聊天历史与结构化 intake 不受影响。
    """
    import streamlit as st

    from utils import random_uuid

    st.session_state.thread_id = random_uuid()


def format_tool_memory_for_context() -> str:
    """格式化为可注入 [TRAVEL_CONTEXT] 的「既往回合工具结论」文本。"""
    import streamlit as st

    init_travel_tool_memory()
    memory: list[dict[str, Any]] = st.session_state.get("travel_tool_memory") or []
    if not memory:
        return ""

    lines = [
        "【既往回合工具结论摘要（非本回合；本回合工具结果以 Agent 上下文为准）】"
    ]
    for idx, turn in enumerate(memory, start=1):
        phase = turn.get("phase", "?")
        lines.append(f"- 回合{idx}（phase={phase}）")
        for item in turn.get("tools") or []:
            tool = item.get("tool", "?")
            summary = (item.get("summary") or "").replace("\n", " ")
            if len(summary) > 220:
                summary = summary[:220] + "…"
            lines.append(f"  · {tool}: {summary}")
    return "\n".join(lines)
