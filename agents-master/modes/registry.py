"""模式注册表与路由。"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from modes.general import mode as general_mode
from modes.knowledge_qa import mode as knowledge_qa_mode
from modes.travel import mode as travel_mode_module

# 注册顺序即 UI 展示顺序；intent 扫描时 travel 优先于 knowledge_qa
_MODE_MODULES: tuple[ModuleType, ...] = (
    general_mode,
    travel_mode_module,
    knowledge_qa_mode,
)

_BY_ID: dict[str, ModuleType] = {m.ID: m for m in _MODE_MODULES}
_BY_LABEL: dict[str, ModuleType] = {m.LABEL: m for m in _MODE_MODULES}

DEFAULT_MODE_ID = general_mode.ID


def list_modes() -> list[ModuleType]:
    return sorted(_MODE_MODULES, key=lambda m: m.ORDER)


def list_mode_labels() -> list[str]:
    return [m.LABEL for m in list_modes()]


def get_mode(mode_id: str) -> ModuleType:
    mode = _BY_ID.get(mode_id)
    if mode is None:
        return general_mode
    return mode


def get_mode_by_label(label: str) -> ModuleType:
    return _BY_LABEL.get(label, general_mode)


def get_active_mode() -> ModuleType:
    import streamlit as st

    return get_mode(st.session_state.get("app_mode", DEFAULT_MODE_ID))


def is_travel_mode(mode_id: str | None = None) -> bool:
    import streamlit as st

    mid = mode_id if mode_id is not None else st.session_state.get("app_mode", "")
    return mid == travel_mode_module.ID


def build_system_prompt(mode_id: str | None = None) -> str:
    mode = get_mode(mode_id) if mode_id else get_active_mode()
    return mode.build_system_prompt()


def branding(mode_id: str | None = None) -> Any:
    mode = get_mode(mode_id) if mode_id else get_active_mode()
    return mode.branding()


def mode_sidebar_caption(mode_id: str | None = None) -> str:
    mode = get_mode(mode_id) if mode_id else get_active_mode()
    if mode.ID == travel_mode_module.ID and travel_mode_module.is_flow_started():
        return travel_mode_module.sidebar_caption()
    return mode.description()


def route_by_intent(text: str, *, current_mode_id: str) -> str | None:
    """
    仅在通用模式下扫描其他模式的意图规则。
    按注册顺序匹配，travel 优先于 knowledge_qa。
    """
    if current_mode_id != general_mode.ID:
        return None
    for mode in _MODE_MODULES:
        if mode.ID == general_mode.ID:
            continue
        if mode.detect_intent(text):
            return mode.ID
    return None


def enter_mode(mode_id: str, *, reset: bool = False) -> bool:
    """切换至目标模式；返回是否需要重建 Agent。"""
    return get_mode(mode_id).on_enter(reset=reset)


def exit_to_general(from_mode_id: str) -> bool:
    """从指定模式退回通用；返回是否需要重建 Agent。"""
    if from_mode_id == general_mode.ID:
        return False
    if from_mode_id == travel_mode_module.ID:
        return travel_mode_module.on_exit()
    return get_mode(from_mode_id).on_exit()
