"""长期记忆召回：组装 [USER_MEMORY] 注入块。"""

from __future__ import annotations

from memory_store import (
    format_profile_for_context,
    load_profile,
    search_session_summaries,
)


def build_user_memory_block(*, search_query: str = "") -> str:
    """
    构建注入 Agent 的长期记忆块。
    Profile 全量 +（有 query 时）向量 Top-K 相关摘要。
    """
    profile = load_profile()
    profile_text = format_profile_for_context(profile)
    vector_lines: list[str] = []
    q = (search_query or "").strip()
    if len(q) >= 4:
        hits = search_session_summaries(q, top_k=3)
        for hit in hits:
            text = str(hit.get("text") or "").strip()
            if text:
                vector_lines.append(f"- {text}")

    if not profile_text and not vector_lines:
        return ""

    parts = ["[USER_MEMORY]"]
    if profile_text:
        parts.append(profile_text)
    if vector_lines:
        parts.append("相关历史摘要：")
        parts.extend(vector_lines)
    parts.append("[/USER_MEMORY]")
    return "\n".join(parts)


def wrap_query_with_user_memory(agent_query: str, *, search_query: str = "") -> str:
    block = build_user_memory_block(search_query=search_query or agent_query)
    if not block:
        return agent_query
    return f"{block}\n\n---\n\n{agent_query}"


def format_long_term_memory_markdown() -> str:
    """侧边栏长期记忆面板。"""
    from memory_store import format_profile_markdown, list_recent_summaries

    lines = [format_profile_markdown()]
    summaries = list_recent_summaries(limit=5)
    if summaries:
        lines.append("**近期会话摘要（向量库）**：")
        for row in summaries:
            meta = row.get("metadata") or {}
            saved = str(meta.get("saved_at", ""))[:19]
            text = str(row.get("text") or "")
            lines.append(f"- {saved} · {text}")
    elif not load_profile().get("recent_tasks"):
        lines.append("_向量库暂无摘要（需归档或生成攻略后写入）_")
    return "\n\n".join(lines)
