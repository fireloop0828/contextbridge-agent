"""Prompt 模板加载与 System Prompt 组装。"""

from __future__ import annotations

import os

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))
GENERAL_SYSTEM_PATH = os.path.join(PROMPTS_DIR, "general_system.md")
GENERAL_SYSTEM_TRAVEL_PATH = os.path.join(PROMPTS_DIR, "general_system_travel.md")
TRAVEL_PLANNER_PATH = os.path.join(PROMPTS_DIR, "travel-planner.md")

_TRAVEL_MODE_HEADER = (
    "<TRAVEL_MODE>\n"
    "你处于旅行规划专用模式。必须遵守 travel-planner 流程："
    "先确认目的地后推荐必玩并让用户勾选，再 intake 提问（最多两轮），"
    "最后按工具链生成完整 Markdown 攻略并导出。\n"
    "收到 [TRAVEL_CONTEXT] 时以其中 phase 为准。\n"
    "</TRAVEL_MODE>"
)


def _load_prompt_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def load_general_system_prompt() -> str:
    """通用模式 System Prompt（RAG、导出、回答规范）。"""
    return _load_prompt_file(GENERAL_SYSTEM_PATH)


def load_travel_planner_prompt() -> str:
    """旅行规划专用 Prompt。"""
    return _load_prompt_file(TRAVEL_PLANNER_PATH)


def load_general_system_travel_prompt() -> str:
    """旅行模式精简 System Prompt（去掉通用模式冗余指令）。"""
    return _load_prompt_file(GENERAL_SYSTEM_TRAVEL_PATH)


def build_system_prompt(app_mode: str) -> str:
    """
    按对话模式组装完整 System Prompt。

    通用模式：general_system.md
    旅行模式：general_system_travel.md + TRAVEL_MODE 头 + travel-planner.md（精简）
    """
    import travel_mode as tm

    if app_mode != tm.APP_MODE_TRAVEL:
        return load_general_system_prompt()
    base = load_general_system_travel_prompt()
    travel_doc = load_travel_planner_prompt()
    if not travel_doc:
        return base or load_general_system_prompt()
    return f"{base}\n\n----\n\n{_TRAVEL_MODE_HEADER}\n\n{travel_doc}"
