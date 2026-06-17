"""聊天主区：历史消息渲染与用户输入处理。"""

from __future__ import annotations

import streamlit as st

import timing_log as tlog
from modes.travel import state_machine as tm
from modes import registry as modes
from modes.travel import handler as travel_handler
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
                travel_handler.merge_intake_on_intent_enter(user_query)
            mark_mode_radio_sync_from_app()
            if not st.session_state.session_initialized:
                main.reconnect_agent(spinner_label=f"正在进入{target.LABEL}…")
            elif needs_reconnect:
                main.rebuild_agent_only(spinner_label=f"正在进入{target.LABEL}…")
            st.toast(f"已进入{target.LABEL}", icon=target.branding().page_icon)

        query_timeout = st.session_state.timeout_seconds
        query_recursion = st.session_state.recursion_limit
        travel_turn = None
        if modes.is_travel_mode():
            travel_turn = travel_handler.prepare_before_agent(
                user_query,
                base_timeout=st.session_state.timeout_seconds,
                base_recursion=st.session_state.recursion_limit,
            )
            query_timeout = travel_turn.timeout_seconds
            query_recursion = travel_turn.recursion_limit
            if travel_turn.needs_prefetch:
                with st.spinner("正在预取知识库与地图数据…"):
                    st.session_state.event_loop.run_until_complete(
                        travel_handler.prefetch_facts(travel_turn.phase)
                    )
                agent_query = travel_handler.compose_agent_query_after_prefetch(
                    user_query, travel_turn.phase
                )
            else:
                agent_query = travel_turn.agent_query or user_query
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
            from modes.travel.facts import get_travel_facts

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
            travel_after = None
            if modes.is_travel_mode():
                travel_after = st.session_state.event_loop.run_until_complete(
                    travel_handler.process_after_agent(
                        final_text,
                        final_tool=final_tool,
                        phase_this_turn=st.session_state.get("_travel_phase_this_turn"),
                    )
                )
                final_text = travel_after.display_text

            export_paths = main.extract_export_paths(final_tool)
            if travel_after and not travel_after.plan_ready:
                export_paths = []

            if travel_after and travel_after.plan_ready:
                auto_paths = main.auto_export_travel_plan_from_chat(
                    travel_after.export_body,
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
            if export_paths and travel_after and travel_after.plan_ready:
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
            if travel_after:
                warn = travel_handler.check_delivery_with_exports(
                    delivery_phase=travel_after.delivery_phase,
                    final_text=final_text,
                    export_paths=export_paths,
                )
                if warn:
                    st.warning(warn)

            st.session_state.history.append({"role": "user", "content": user_query})
            assistant_msg = {"role": "assistant", "content": final_text}
            if export_paths:
                assistant_msg["exports"] = export_paths
            if (
                travel_after
                and travel_after.attach_facts_to_history
                and travel_after.facts_snapshot
            ):
                assistant_msg["travel_facts"] = travel_after.facts_snapshot
            st.session_state.history.append(assistant_msg)
            if final_tool.strip():
                st.session_state.history.append(
                    {"role": "assistant_tool", "content": final_tool}
                )
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
