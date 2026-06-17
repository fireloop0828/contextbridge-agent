"""通用模式：开放问答 + 全量 MCP 工具。"""

from __future__ import annotations

from modes.types import ModeBranding
from prompts import load_general_system_prompt

ID = "general"
LABEL = "通用模式"
ORDER = 0
DESCRIPTION = (
    "多轮 ReAct 推理，按需调用已连接 MCP 工具，"
    "适合开放问答、检索与文档导出等通用任务。"
)


def description() -> str:
    return DESCRIPTION


def branding() -> ModeBranding:
    return ModeBranding(
        page_title="MCP 智能体",
        page_icon="🧠",
        title="💬 MCP 工具智能体",
        subtitle="✨ 向支持 MCP 工具的 ReAct 智能体提问。",
    )


def chat_placeholder() -> str:
    return "💬 输入你的问题"


def build_system_prompt() -> str:
    return load_general_system_prompt()


def detect_intent(_text: str) -> bool:
    return False


def on_enter(*, reset: bool = False) -> bool:
    import streamlit as st

    needs = st.session_state.get("agent_prompt_mode") != ID
    st.session_state.app_mode = ID
    st.session_state.agent_prompt_mode = ID
    return needs


def on_exit() -> bool:
    return False
