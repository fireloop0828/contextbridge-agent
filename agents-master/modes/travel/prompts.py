"""旅行模式 Prompt 加载（canonical 位置：modes/travel/）。"""

from __future__ import annotations

import os

_MODE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERAL_SYSTEM_TRAVEL_PATH = os.path.join(_MODE_DIR, "general_system_travel.md")
TRAVEL_PLANNER_PATH = os.path.join(_MODE_DIR, "travel-planner.md")

_TRAVEL_MODE_HEADER = (
    "<TRAVEL_MODE>\n"
    "你处于旅行规划专用模式。必须遵守 travel-planner 流程："
    "先确认目的地后推荐必玩并让用户勾选，再 intake 提问（最多两轮），"
    "最后按工具链生成完整 Markdown 攻略并导出。\n"
    "收到 [TRAVEL_CONTEXT] 时以其中 phase 为准。\n"
    "</TRAVEL_MODE>"
)


def _load(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def load_general_system_travel_prompt() -> str:
    return _load(GENERAL_SYSTEM_TRAVEL_PATH)


def load_travel_planner_prompt() -> str:
    return _load(TRAVEL_PLANNER_PATH)


def build_system_prompt() -> str:
    """旅行模式完整 System Prompt。"""
    from prompts import load_general_system_prompt

    base = load_general_system_travel_prompt()
    travel_doc = load_travel_planner_prompt()
    if not travel_doc:
        return base or load_general_system_prompt()
    return f"{base}\n\n----\n\n{_TRAVEL_MODE_HEADER}\n\n{travel_doc}"
