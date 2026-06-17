"""旅行模式 handler：回合编排、预取、后处理与交付（ui/chat 唯一入口）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st
from . import state_machine as tm


@dataclass
class TurnBeforeAgent:
    """Agent 调用前的旅行回合准备结果。"""

    agent_query: str | None
    """None 表示需先预取 facts，再 compose_agent_query。"""
    display_user_query: str
    phase: str
    timeout_seconds: int
    recursion_limit: int
    needs_prefetch: bool


@dataclass
class TurnAfterAgent:
    """Agent 回复后的旅行回合处理结果。"""

    display_text: str
    phase_this_turn: str | None
    delivery_phase: str | None
    plan_ready: bool
    export_body: str
    facts_snapshot: dict[str, Any] | None
    attach_facts_to_history: bool


def merge_intake_on_intent_enter(user_query: str) -> None:
    """通用模式意图切入旅行时，合并已解析 intake 字段。"""
    st.session_state.travel_intake = tm.merge_intake_and_track_destination(
        st.session_state.get("travel_intake") or tm.empty_intake(),
        tm.extract_intake_from_user_message(user_query),
    )


def prepare_before_agent(
    user_query: str,
    *,
    base_timeout: int,
    base_recursion: int,
) -> TurnBeforeAgent:
    """推进 phase/intake，必要时标记预取；返回 Agent 入参或 None（待预取）。"""
    old_phase = st.session_state.get("travel_phase", tm.PHASE_INTAKE_1)
    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    new_phase, new_turns, intake = tm.advance_travel_turn(
        user_query,
        phase=old_phase,
        intake=intake,
        intake_user_turns=st.session_state.get("travel_intake_user_turns", 0),
        last_travel_plan_md=st.session_state.get("last_travel_plan_md", ""),
    )
    if tm.should_reset_agent_thread_o9(old_phase, new_phase):
        tm.reset_agent_thread_o9()
    st.session_state._travel_phase_this_turn = new_phase
    st.session_state.travel_phase = new_phase
    st.session_state.travel_intake = intake
    st.session_state.travel_intake_user_turns = new_turns
    if new_phase in (tm.PHASE_INTAKE_1, tm.PHASE_INTAKE_2):
        st.session_state.travel_intake_round = new_turns

    needs_prefetch = new_phase in (tm.PHASE_POI_SELECTION, tm.PHASE_GENERATING)
    agent_query: str | None = None
    if not needs_prefetch:
        agent_query = tm.compose_travel_agent_query(
            user_query,
            phase=new_phase,
            intake=intake,
            intake_user_turns=new_turns,
            last_travel_plan_md=st.session_state.get("last_travel_plan_md", ""),
        )

    return TurnBeforeAgent(
        agent_query=agent_query,
        display_user_query=user_query,
        phase=new_phase,
        timeout_seconds=tm.travel_timeout_seconds(base_timeout, new_phase),
        recursion_limit=tm.travel_recursion_limit(base_recursion, new_phase),
        needs_prefetch=needs_prefetch,
    )


async def prefetch_facts(phase: str) -> None:
    """编排层 MCP 预取（POI / 生成阶段）。"""
    if phase not in (tm.PHASE_POI_SELECTION, tm.PHASE_GENERATING):
        return
    tools = st.session_state.get("mcp_tools")
    if not tools:
        return
    from .pipeline import prefetch_travel_facts

    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    await prefetch_travel_facts(phase=phase, intake=intake, tools=tools)


def compose_agent_query_after_prefetch(user_query: str, phase: str) -> str:
    return tm.compose_travel_agent_query(
        user_query,
        phase=phase,
        intake=st.session_state.get("travel_intake") or tm.empty_intake(),
        intake_user_turns=st.session_state.get("travel_intake_user_turns", 0),
        last_travel_plan_md=st.session_state.get("last_travel_plan_md", ""),
    )


async def process_after_agent(
    raw_text: str,
    *,
    final_tool: str,
    phase_this_turn: str | None,
) -> TurnAfterAgent:
    """清洗回复、增强展示、组装导出正文、校验交付。"""
    display_text, new_phase, intake, last_plan = tm.finalize_assistant_turn(
        phase=st.session_state.get("travel_phase", tm.PHASE_INTAKE_1),
        intake=st.session_state.get("travel_intake") or tm.empty_intake(),
        assistant_text=raw_text,
        intake_user_turns=st.session_state.get("travel_intake_user_turns", 0),
    )
    st.session_state.travel_phase = new_phase
    st.session_state.travel_intake = intake
    if last_plan:
        st.session_state.last_travel_plan_md = last_plan

    delivery_phase = st.session_state.get("travel_phase", phase_this_turn)
    plan_ready = tm.looks_like_travel_plan(display_text)

    if plan_ready:
        tools = st.session_state.get("mcp_tools")
        if tools:
            try:
                from .pipeline import ensure_generating_facts_for_delivery

                await ensure_generating_facts_for_delivery(
                    st.session_state.get("travel_intake") or tm.empty_intake(),
                    tools,
                )
            except Exception:
                pass
        try:
            from .facts import format_travel_plan_display, get_travel_facts

            facts_now = get_travel_facts()
            dest = (
                (facts_now or {}).get("destination")
                if isinstance(facts_now, dict)
                else ""
            )
            display_text = format_travel_plan_display(
                display_text,
                facts_now,
                destination=str(dest or ""),
            )
        except Exception:
            pass

    export_body = display_text
    from .facts import format_facts_markdown_appendix, get_travel_facts

    facts_snapshot = get_travel_facts()
    if plan_ready and facts_snapshot:
        export_body = (
            display_text.rstrip()
            + "\n\n"
            + format_facts_markdown_appendix(facts_snapshot)
        )

    attach = bool(
        facts_snapshot
        and phase_this_turn
        in (tm.PHASE_POI_SELECTION, tm.PHASE_GENERATING, tm.PHASE_REVISION)
    )

    if phase_this_turn and final_tool.strip():
        from .tool_memory import (
            ingest_tool_round_memory,
            trim_checkpoint_after_tool_ingest,
        )

        ingest_tool_round_memory(
            phase=phase_this_turn,
            tool_output_text=final_tool,
        )
        trim_checkpoint_after_tool_ingest()

    return TurnAfterAgent(
        display_text=display_text,
        phase_this_turn=phase_this_turn,
        delivery_phase=delivery_phase,
        plan_ready=plan_ready,
        export_body=export_body,
        facts_snapshot=facts_snapshot if isinstance(facts_snapshot, dict) else None,
        attach_facts_to_history=attach,
    )


def check_delivery_with_exports(
    *,
    delivery_phase: str | None,
    final_text: str,
    export_paths: list[str],
) -> str | None:
    if not delivery_phase:
        return None
    return tm.check_travel_delivery(
        phase_before=delivery_phase,
        final_text=final_text,
        export_paths=export_paths,
    )
