"""聊天主区：历史消息渲染与用户输入处理。"""

from __future__ import annotations

import streamlit as st

import travel_mode as tm
import timing_log as tlog
from modes import registry as modes
from ui import get_app_module
from ui.sidebar import mark_mode_radio_sync_from_app
from ui.travel_evidence import render_travel_provenance
def print_message() -> None:
    """在页面上渲染对话历史（含工具调用折叠面板与导出下载）。"""
    main = get_app_module()
    i = 0
    while i < len(st.session_state.history):
        message = st.session_state.history[i]

        if message["role"] == "user":
            st.chat_message("user", avatar="🧑‍💻").markdown(message["content"])
            i += 1
        elif message["role"] == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                facts = message.get("travel_facts")
                if facts:
                    render_travel_provenance(
                        facts,
                        key_prefix=f"hist_{i}",
                        show_divider=True,
                        expanded=False,
                    )
                st.markdown(message["content"])
                if message.get("exports"):
                    main.render_export_downloads(
                        message["exports"],
                        key_prefix=f"hist_{i}",
                    )

                if (
                    i + 1 < len(st.session_state.history)
                    and st.session_state.history[i + 1]["role"] == "assistant_tool"
                ):
                    tool_label = (
                        "🔧 原始 Agent 工具调用（高级）"
                        if message.get("travel_facts")
                        else "🔧 工具调用详情"
                    )
                    with st.expander(tool_label, expanded=False):
                        st.markdown(st.session_state.history[i + 1]["content"])
                    i += 2
                else:
                    i += 1
        else:
            i += 1


def handle_travel_user_message(user_query: str) -> tuple[str | None, str, str]:
    """
    旅行模式：推进 phase/intake，返回 (agent_query|None 待预取后构建, display_user_query, new_phase)。

    agent_query 为 None 时表示需在预取 facts 后调用 tm.compose_travel_agent_query。
    """
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

    if new_phase in (tm.PHASE_POI_SELECTION, tm.PHASE_GENERATING):
        return None, user_query, new_phase

    agent_query = tm.compose_travel_agent_query(
        user_query,
        phase=new_phase,
        intake=intake,
        intake_user_turns=new_turns,
        last_travel_plan_md=st.session_state.get("last_travel_plan_md", ""),
    )
    return agent_query, user_query, new_phase


async def prefetch_travel_facts_for_turn(phase: str) -> None:
    """P0：Agent 调用前编排层预取 RAG/高德数据。"""
    if phase not in (tm.PHASE_POI_SELECTION, tm.PHASE_GENERATING):
        return
    tools = st.session_state.get("mcp_tools")
    if not tools:
        return
    from travel_pipeline import prefetch_travel_facts

    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    await prefetch_travel_facts(phase=phase, intake=intake, tools=tools)


def finalize_travel_assistant_text(raw_text: str) -> str:
    """清洗助手回复并更新旅行状态。"""
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
    return display_text


def render_chat() -> None:
    """渲染历史对话与用户输入框，处理一轮完整问答。"""
    main = get_app_module()
    print_message()

    _chat_placeholder = modes.get_active_mode().chat_placeholder()
    user_query = st.chat_input(_chat_placeholder)
    if not user_query:
        return

    if st.session_state.session_initialized:
        current_mode = st.session_state.get("app_mode", modes.DEFAULT_MODE_ID)
        routed = modes.route_by_intent(user_query, current_mode_id=current_mode)
        if routed:
            target = modes.get_mode(routed)
            needs_reconnect = modes.enter_mode(
                routed,
                reset=(routed == tm.APP_MODE_TRAVEL),
            )
            if routed == tm.APP_MODE_TRAVEL:
                st.session_state.travel_intake = tm.merge_intake_and_track_destination(
                    st.session_state.get("travel_intake") or tm.empty_intake(),
                    tm.extract_intake_from_user_message(user_query),
                )
            mark_mode_radio_sync_from_app()
            if not st.session_state.session_initialized:
                main.reconnect_agent(spinner_label=f"正在进入{target.LABEL}…")
            elif needs_reconnect:
                main.rebuild_agent_only(spinner_label=f"正在进入{target.LABEL}…")
            st.toast(f"已进入{target.LABEL}", icon=target.branding().page_icon)

        query_timeout = st.session_state.timeout_seconds
        query_recursion = st.session_state.recursion_limit
        if modes.is_travel_mode():
            pending_query, _, phase_this_turn = handle_travel_user_message(user_query)
            query_timeout = tm.travel_timeout_seconds(
                st.session_state.timeout_seconds, phase_this_turn
            )
            query_recursion = tm.travel_recursion_limit(
                st.session_state.recursion_limit, phase_this_turn
            )
            if pending_query is None:
                with st.spinner("正在预取知识库与地图数据…"):
                    st.session_state.event_loop.run_until_complete(
                        prefetch_travel_facts_for_turn(phase_this_turn)
                    )
                agent_query = tm.compose_travel_agent_query(
                    user_query,
                    phase=phase_this_turn,
                    intake=st.session_state.get("travel_intake") or tm.empty_intake(),
                    intake_user_turns=st.session_state.get("travel_intake_user_turns", 0),
                    last_travel_plan_md=st.session_state.get("last_travel_plan_md", ""),
                )
            else:
                agent_query = pending_query
        else:
            agent_query = user_query

        from memory_recall import wrap_query_with_user_memory

        agent_query = wrap_query_with_user_memory(
            agent_query, search_query=user_query
        )

        timing = tlog.TimingCollector()
        preview = user_query.replace("\n", " ")[:80]
        if len(user_query) > 80:
            preview += "…"
        timing.set_meta(
            app_mode=st.session_state.get("app_mode", tm.APP_MODE_GENERAL),
            travel_phase=st.session_state.get("travel_phase"),
            model=st.session_state.get("selected_model"),
            timeout_seconds=query_timeout,
            recursion_limit=query_recursion,
            user_query_preview=preview,
        )
        st.session_state.timing_current = timing

        st.chat_message("user", avatar="🧑‍💻").markdown(user_query)
        with st.chat_message("assistant", avatar="🤖"):
            from travel_facts import get_travel_facts

            facts_live = get_travel_facts() if modes.is_travel_mode() else None
            if facts_live:
                render_travel_provenance(
                    facts_live, key_prefix="live", show_divider=True, expanded=False
                )
            tool_placeholder = st.empty()
            text_placeholder = st.empty()
            resp, final_text, final_tool = (
                st.session_state.event_loop.run_until_complete(
                    main.process_query(
                        agent_query,
                        text_placeholder,
                        tool_placeholder,
                        query_timeout,
                        timing=timing,
                        recursion_limit=query_recursion,
                    )
                )
            )
        if "error" in resp:
            if st.session_state.get("timing_current") is timing:
                status = (
                    "timeout"
                    if "已超过" in str(resp.get("error", ""))
                    else "error"
                )
                tlog.append_timing_record(
                    timing.finish(status=status, error=resp.get("error", ""))
                )
            st.error(resp["error"])
            if resp.get("error_detail"):
                with st.expander("技术详情（排障用）", expanded=False):
                    st.code(resp["error_detail"])
        else:
            phase_this_turn = None
            delivery_phase = None
            plan_ready = False
            if modes.is_travel_mode():
                phase_this_turn = st.session_state.get("_travel_phase_this_turn")
                final_text = finalize_travel_assistant_text(final_text)
                delivery_phase = st.session_state.get("travel_phase", phase_this_turn)
                plan_ready = tm.looks_like_travel_plan(final_text)

                if plan_ready:
                    tools = st.session_state.get("mcp_tools")
                    if tools:
                        try:
                            from travel_pipeline import ensure_generating_facts_for_delivery

                            st.session_state.event_loop.run_until_complete(
                                ensure_generating_facts_for_delivery(
                                    st.session_state.get("travel_intake")
                                    or tm.empty_intake(),
                                    tools,
                                )
                            )
                        except Exception:
                            pass
                    try:
                        from travel_facts import format_travel_plan_display, get_travel_facts

                        facts_now = get_travel_facts()
                        dest = (
                            (facts_now or {}).get("destination")
                            if isinstance(facts_now, dict)
                            else ""
                        )
                        final_text = format_travel_plan_display(
                            final_text,
                            facts_now,
                            destination=str(dest or ""),
                        )
                    except Exception:
                        pass

            export_paths = main.extract_export_paths(final_tool)
            if modes.is_travel_mode() and not plan_ready:
                export_paths = []

            if modes.is_travel_mode() and plan_ready:
                from travel_facts import format_facts_markdown_appendix, get_travel_facts

                export_body = final_text
                facts_for_export = get_travel_facts()
                if facts_for_export:
                    export_body = (
                        final_text.rstrip()
                        + "\n\n"
                        + format_facts_markdown_appendix(facts_for_export)
                    )
                auto_paths = main.auto_export_travel_plan_from_chat(
                    export_body,
                    st.session_state.get("travel_intake") or tm.empty_intake(),
                )
                for p in auto_paths:
                    if p not in export_paths:
                        export_paths.append(p)
                if not auto_paths:
                    st.warning(
                        "攻略已生成，但自动保存 Markdown 失败。"
                        "请检查 data/outputs/ 目录权限后重试。"
                    )
            main._register_exports(export_paths)
            if export_paths:
                st.session_state.last_export_path = export_paths[-1]
            if (
                export_paths
                and plan_ready
            ):
                try:
                    from memory_pipeline import run_memory_pipeline_from_current

                    run_memory_pipeline_from_current(trigger="travel_export")
                except Exception:
                    pass
            try:
                from memory_pipeline import run_explicit_remember_from_user_text

                run_explicit_remember_from_user_text(user_query)
            except Exception:
                pass
            if delivery_phase:
                warn = tm.check_travel_delivery(
                    phase_before=delivery_phase,
                    final_text=final_text,
                    export_paths=export_paths,
                )
                if warn:
                    st.warning(warn)
            from travel_facts import get_travel_facts

            facts_snapshot = get_travel_facts()
            st.session_state.history.append({"role": "user", "content": user_query})
            assistant_msg = {"role": "assistant", "content": final_text}
            if export_paths:
                assistant_msg["exports"] = export_paths
            if (
                modes.is_travel_mode()
                and facts_snapshot
                and phase_this_turn
                in (tm.PHASE_POI_SELECTION, tm.PHASE_GENERATING, tm.PHASE_REVISION)
            ):
                assistant_msg["travel_facts"] = facts_snapshot
            st.session_state.history.append(assistant_msg)
            if final_tool.strip():
                st.session_state.history.append(
                    {"role": "assistant_tool", "content": final_tool}
                )
            if (
                modes.is_travel_mode()
                and phase_this_turn
                and final_tool.strip()
            ):
                from travel_tool_memory import (
                    ingest_tool_round_memory,
                    trim_checkpoint_after_tool_ingest,
                )

                ingest_tool_round_memory(
                    phase=phase_this_turn,
                    tool_output_text=final_tool,
                )
                trim_checkpoint_after_tool_ingest()
            from session_store import save_latest_autosave

            save_latest_autosave()
            if st.session_state.get("timing_current") is timing:
                tlog.append_timing_record(timing.finish(status="ok"))
            st.rerun()
    else:
        if main.ensure_session_ready():
            st.rerun()
        else:
            st.error(
                "⚠️ 无法连接 MCP 服务器。请检查 config.json、API 密钥，"
                "或侧边栏工具配置后重试。"
            )
