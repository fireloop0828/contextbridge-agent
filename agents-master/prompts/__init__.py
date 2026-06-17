"""Prompt 模板加载与 System Prompt 组装。"""

from __future__ import annotations

import os

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))
GENERAL_SYSTEM_PATH = os.path.join(PROMPTS_DIR, "general_system.md")
# 旅行 Prompt 已迁至 modes/travel/；以下路径仅供兼容旧引用
GENERAL_SYSTEM_TRAVEL_PATH = os.path.join(PROMPTS_DIR, "general_system_travel.md")
TRAVEL_PLANNER_PATH = os.path.join(PROMPTS_DIR, "travel-planner.md")


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
    """旅行规划专用 Prompt（委托 modes/travel）。"""
    from modes.travel.prompts import load_travel_planner_prompt as _load

    return _load()


def load_general_system_travel_prompt() -> str:
    """旅行模式精简 System Prompt（委托 modes/travel）。"""
    from modes.travel.prompts import load_general_system_travel_prompt as _load

    return _load()


def build_travel_system_prompt() -> str:
    """旅行模式完整 System Prompt（委托 modes/travel）。"""
    from modes.travel.prompts import build_system_prompt as _build

    return _build()


def build_system_prompt(app_mode: str) -> str:
    """按模式 id 组装 System Prompt（委托 modes.registry）。"""
    from modes.registry import build_system_prompt as registry_build

    return registry_build(app_mode)
