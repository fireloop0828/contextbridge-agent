"""知识库 QA 模式：以 RAG 检索为主的轻量模式包。"""

from __future__ import annotations

import os
import re

from modes.types import ModeBranding

ID = "knowledge_qa"
LABEL = "知识库问答"
ORDER = 2
DESCRIPTION = (
    "专注 RAG 知识库检索与问答：list_collections、"
    "query_knowledge_hub、get_document_summary，回答附带来源。"
)


def description() -> str:
    return DESCRIPTION

_SYSTEM_PATH = os.path.join(os.path.dirname(__file__), "system.md")

_INTENT_RE = re.compile(
    r"(知识库|检索|查一下|查询|文档|资料|手册|collection|"
    r"有哪些集合|list_collections|query_knowledge|RAG|"
    r"知识 hub|travel_plan|embedding|向量库|入库)",
    re.IGNORECASE,
)


def _load_system_prompt() -> str:
    try:
        with open(_SYSTEM_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        from prompts import load_general_system_prompt

        return load_general_system_prompt()


def branding() -> ModeBranding:
    return ModeBranding(
        page_title="知识库问答",
        page_icon="📚",
        title="📚 知识库问答",
        subtitle="✨ 基于 RAG 知识库检索回答问题，回答附带文档来源。",
    )


def chat_placeholder() -> str:
    return "📚 提问知识库内容，如「travel_plan 里有什么？」"


def build_system_prompt() -> str:
    return _load_system_prompt()


def build_agent(tools: list, model, system_prompt: str | None = None):
    """构建知识库问答的 LangGraph 编排图（node/edge/state）。

    参数:
        tools: 已加载的 MCP 工具列表
        model: 聊天模型实例
        system_prompt: 自定义 system prompt；缺省使用本模式 system.md
    """
    from .graph import build_rag_graph

    prompt = system_prompt if system_prompt is not None else _load_system_prompt()
    return build_rag_graph(tools=tools, model=model, system_prompt=prompt)


def detect_intent(text: str) -> bool:
    return bool(text and _INTENT_RE.search(text))


def process_after_agent(final_text: str) -> str:
    """回答后处理：程序化追加检索来源块（格式稳定，不依赖 LLM 自觉标注）。

    供 ui/chat.py 在知识库模式回答完成后调用；无来源或正文已含来源时不重复。
    """
    import streamlit as st

    block = st.session_state.get("knowledge_qa_last_sources") or ""
    if not block:
        return final_text
    if "（来源" in final_text:
        return final_text
    return (final_text.rstrip() + "\n\n" + block).strip()


def on_enter(*, reset: bool = False) -> bool:
    import streamlit as st

    needs = st.session_state.get("agent_prompt_mode") != ID
    st.session_state.app_mode = ID
    st.session_state.agent_prompt_mode = ID
    return needs


def on_exit() -> bool:
    import streamlit as st

    needs = st.session_state.get("agent_prompt_mode") == ID
    st.session_state.app_mode = "general"
    st.session_state.agent_prompt_mode = "general"
    return needs
