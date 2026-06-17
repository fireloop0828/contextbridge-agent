"""旅行规划模式：委托 travel_mode 状态机与编排。"""

from __future__ import annotations

from . import state_machine as tm
from modes.types import ModeBranding
from modes.travel import prompts as travel_prompts

ID = tm.APP_MODE_TRAVEL
LABEL = "旅行规划"
ORDER = 1


def branding() -> ModeBranding:
    return ModeBranding(
        page_title="旅行规划助手",
        page_icon="🧳",
        title="🧳 旅行规划助手",
        subtitle=(
            "✨ 结合高德地图、RAG知识库、时间工具等实际情况，"
            "为您生成可下载的专属行程攻略。"
        ),
    )


def chat_placeholder() -> str:
    return "🧳 描述旅行需求，或补充行程信息…"


def build_system_prompt() -> str:
    return travel_prompts.build_system_prompt()


def detect_intent(text: str) -> bool:
    return tm.detect_travel_intent(text)


def on_enter(*, reset: bool = False) -> bool:
    return tm.enter_travel_mode(reset_intake=reset)


def on_exit() -> bool:
    return tm.exit_travel_mode()


def sidebar_caption() -> str:
    """旅行进行中时的动态说明（非静态 description）。"""
    import streamlit as st

    phase = st.session_state.get("travel_phase", tm.PHASE_INTAKE_1)
    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    missing = tm.compute_missing_fields(intake)

    if phase == tm.PHASE_POI_SELECTION:
        dest = intake.get("destination", "") or "目的地"
        return f"正在为「{dest}」推荐必玩景点，请在对话中勾选必去/想去。"
    if phase in (tm.PHASE_INTAKE_1, tm.PHASE_INTAKE_2):
        if missing:
            return (
                f"继续补充行程信息（尚缺 {len(missing)} 项），"
                "如出行时间、人数、交通与偏好等。"
            )
        return "需求已齐全，即将为您生成攻略。"
    if phase == tm.PHASE_REVISION:
        return "攻略已生成，可继续提出修改意见，或下载 Markdown。"
    if phase == tm.PHASE_GENERATING:
        return "正在生成攻略，请稍候…"
    return description()


def description() -> str:
    return (
        "对话式旅行规划工作流：必玩推荐 → 需求采集 → 知识库攻略 →"
        "高德路线规划 + 天气查询 + 住宿美食推荐，生成可下载 Markdown 行程。"
    )


def is_flow_started() -> bool:
    import streamlit as st

    phase = st.session_state.get("travel_phase", tm.PHASE_INTAKE_1)
    if phase != tm.PHASE_INTAKE_1:
        return True
    if st.session_state.get("travel_intake_user_turns", 0) > 0:
        return True
    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    return bool((intake.get("destination") or "").strip())
