"""侧边栏：对话模式、系统设置、MCP 工具、导出与操作。"""

from __future__ import annotations

import json
import os

import streamlit as st

import travel_mode as tm
import timing_log as tlog
from session_store import (
    apply_snapshot,
    archive_current_session,
    clear_persisted_latest,
    describe_latest_for_restore,
    format_session_state_markdown,
    has_restorable_latest,
    init_session_store_state,
    list_archives,
    load_latest_snapshot,
    load_snapshot_from_file,
    save_latest_autosave,
    start_blank_session,
)
from ui import get_app_module
from ui.display_labels import format_mcp_server_label

MODE_LABEL_GENERAL = "通用模式"
MODE_LABEL_TRAVEL = "旅行规划"
MODE_LABEL_TO_APP = {
    MODE_LABEL_GENERAL: tm.APP_MODE_GENERAL,
    MODE_LABEL_TRAVEL: tm.APP_MODE_TRAVEL,
}
APP_MODE_TO_LABEL = {v: k for k, v in MODE_LABEL_TO_APP.items()}
_LEGACY_MODE_LABELS = {
    "💬 通用对话": MODE_LABEL_GENERAL,
    "🧳 旅行规划": MODE_LABEL_TRAVEL,
    "通用": MODE_LABEL_GENERAL,
    "通用对话": MODE_LABEL_GENERAL,
}

MODE_SIDEBAR_INTRO: dict[str, str] = {
    tm.APP_MODE_GENERAL: (
        "多轮 ReAct 推理，按需调用已连接 MCP 工具，"
        "适合开放问答、检索与文档导出等通用任务。"
    ),
    tm.APP_MODE_TRAVEL: (
        "对话式旅行规划工作流：必玩推荐 → 需求采集 → 知识库攻略 →"
        "高德路线规划 + 天气查询 + 住宿美食推荐 ，生成可下载 Markdown 行程。"
    ),
}


def _is_travel_flow_started() -> bool:
    phase = st.session_state.get("travel_phase", tm.PHASE_INTAKE_1)
    if phase != tm.PHASE_INTAKE_1:
        return True
    if st.session_state.get("travel_intake_user_turns", 0) > 0:
        return True
    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    if (intake.get("destination") or "").strip():
        return True
    return False


def get_mode_sidebar_caption(app_mode: str) -> str:
    if app_mode != tm.APP_MODE_TRAVEL:
        return MODE_SIDEBAR_INTRO[tm.APP_MODE_GENERAL]
    if not _is_travel_flow_started():
        return MODE_SIDEBAR_INTRO[tm.APP_MODE_TRAVEL]

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
    return "正在生成攻略，请稍候…"


def mark_mode_segmented_sync_from_app() -> None:
    st.session_state._sync_mode_segmented_from_app = True


def sync_mode_segmented_before_widget() -> None:
    if not st.session_state.get("_sync_mode_segmented_from_app"):
        return
    st.session_state.mode_segmented = APP_MODE_TO_LABEL.get(
        st.session_state.get("app_mode", tm.APP_MODE_GENERAL),
        MODE_LABEL_GENERAL,
    )
    del st.session_state._sync_mode_segmented_from_app


def _ensure_mode_segmented_initialized() -> None:
    if "mode_segmented" not in st.session_state:
        legacy = st.session_state.pop("mode_select", None)
        if legacy in _LEGACY_MODE_LABELS:
            legacy = _LEGACY_MODE_LABELS[legacy]
        st.session_state.mode_segmented = legacy or APP_MODE_TO_LABEL.get(
            st.session_state.get("app_mode", tm.APP_MODE_GENERAL),
            MODE_LABEL_GENERAL,
        )
        return
    current = st.session_state.mode_segmented
    if current in _LEGACY_MODE_LABELS:
        st.session_state.mode_segmented = _LEGACY_MODE_LABELS[current]


def _on_mode_segmented_change() -> None:
    """仅更新 session 状态；勿在此调用 st.spinner / rebuild（会重复注册 widget key）。"""
    label = st.session_state.get("mode_segmented", MODE_LABEL_GENERAL)
    if label in _LEGACY_MODE_LABELS:
        label = _LEGACY_MODE_LABELS[label]
    selected_app_mode = MODE_LABEL_TO_APP.get(label, tm.APP_MODE_GENERAL)
    prev_app_mode = st.session_state.get("app_mode", tm.APP_MODE_GENERAL)
    if selected_app_mode == prev_app_mode:
        return

    if selected_app_mode == tm.APP_MODE_TRAVEL:
        needs_rebuild = tm.enter_travel_mode(reset_intake=True)
        spinner = "正在切换至旅行规划模式…"
    else:
        needs_rebuild = tm.exit_travel_mode()
        spinner = "正在切换至通用对话模式…"

    if not st.session_state.session_initialized:
        st.session_state._pending_mode_switch = "reconnect"
    elif needs_rebuild:
        st.session_state._pending_mode_switch = "rebuild"
    else:
        return
    st.session_state._pending_mode_switch_label = spinner


def _apply_pending_mode_switch() -> None:
    """在主脚本流程中执行模式切换后的 Agent 重建（可安全使用 spinner）。"""
    pending = st.session_state.pop("_pending_mode_switch", None)
    if not pending:
        return
    spinner = st.session_state.pop("_pending_mode_switch_label", "正在切换模式…")
    main = get_app_module()
    if pending == "reconnect":
        main.reconnect_agent(spinner_label=spinner)
    elif pending == "rebuild":
        main.rebuild_agent_only(spinner_label=spinner)


def _render_mode_segment() -> None:
    sync_mode_segmented_before_widget()
    _ensure_mode_segmented_initialized()
    prev_app_mode = st.session_state.get("app_mode", tm.APP_MODE_GENERAL)
    st.segmented_control(
        "模式",
        options=[MODE_LABEL_GENERAL, MODE_LABEL_TRAVEL],
        key="mode_segmented",
        label_visibility="collapsed",
        width="stretch",
        on_change=_on_mode_segmented_change,
    )
    st.caption(get_mode_sidebar_caption(prev_app_mode))


def _render_system_settings() -> None:
    main = get_app_module()
    available_models = main.get_available_models()
    if not available_models:
        st.warning(
            "⚠️ 未配置 API 密钥。请在 .env 中设置 DASHSCOPE_API_KEY（百炼）、"
            "ANTHROPIC_API_KEY 或 OPENAI_API_KEY。"
        )
        available_models = ["qwen3.7-plus"]

    model_pending = (
        st.session_state.selected_model
        != st.session_state.get("applied_model", "")
    )
    if model_pending and st.session_state.session_initialized:
        st.caption("模型已更改，点击右侧「应用」后生效。")

    col_model_select, col_model_apply = st.columns([4, 1], gap="small")
    with col_model_select:
        st.session_state.selected_model = st.selectbox(
            "🤖 选择模型",
            options=available_models,
            index=(
                available_models.index(st.session_state.selected_model)
                if st.session_state.selected_model in available_models
                else 0
            ),
            label_visibility="visible",
        )
    with col_model_apply:
        st.markdown(
            "<div style='height:1.75rem'></div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "应用",
            key="apply_model_button",
            use_container_width=True,
            type="primary",
        ):
            if main.rebuild_agent_only(spinner_label="正在切换模型…"):
                st.success(f"✅ 已切换至模型：{st.session_state.selected_model}")
                st.rerun()
            else:
                st.error("❌ 模型切换失败，请检查 API 密钥与网络。")

    st.session_state.timeout_seconds = st.slider(
        "⏱️ 响应超时时间（秒）",
        min_value=60,
        max_value=400,
        value=st.session_state.timeout_seconds,
        step=10,
        help="设置智能体生成回复的最长等待时间，复杂任务可适当调高。",
    )
    st.session_state.recursion_limit = st.slider(
        "⏱️ 递归调用上限（次）",
        min_value=10,
        max_value=200,
        value=st.session_state.recursion_limit,
        step=10,
        help="设置递归调用次数上限，过高可能导致内存占用过大。",
    )


def _render_mcp_tools() -> None:
    main = get_app_module()
    if "mcp_tools_expander" not in st.session_state:
        st.session_state.mcp_tools_expander = False

    with st.expander("🧰 添加 MCP 工具", expanded=st.session_state.mcp_tools_expander):
        loaded_config = main.load_config_from_json()
        default_config_text = json.dumps(loaded_config, indent=2, ensure_ascii=False)

        if "pending_mcp_config" not in st.session_state:
            try:
                st.session_state.pending_mcp_config = loaded_config
            except Exception as e:
                st.error(f"初始化 MCP 配置失败：{e}")

        st.subheader("添加工具（JSON 格式）")
        st.markdown(
            """
        请粘贴 **单个工具** 的 JSON 配置。

        [如何配置？](https://teddylee777.notion.site/MCP-Tool-Setup-Guide-English-1d324f35d1298030a831dfb56045906a)

        ⚠️ **注意**：JSON 须用花括号 `{}` 包裹。
        """
        )

        example_json = {
            "github": {
                "command": "npx",
                "args": [
                    "-y",
                    "@smithery/cli@latest",
                    "run",
                    "@smithery-ai/github",
                    "--config",
                    '{"githubPersonalAccessToken":"your_token_here"}',
                ],
                "transport": "stdio",
            }
        }
        default_text = json.dumps(example_json, indent=2, ensure_ascii=False)
        new_tool_json = st.text_area("工具 JSON", default_text, height=250)

        if st.button(
            "添加工具",
            type="primary",
            key="add_tool_button",
            use_container_width=True,
        ):
            try:
                if not new_tool_json.strip().startswith(
                    "{"
                ) or not new_tool_json.strip().endswith("}"):
                    st.error("JSON 须以花括号开头和结尾（{}）。")
                    st.markdown('正确格式：`{ "工具名": { ... } }`')
                else:
                    parsed_tool = json.loads(new_tool_json)
                    if "mcpServers" in parsed_tool:
                        parsed_tool = parsed_tool["mcpServers"]
                        st.info("检测到 `mcpServers` 格式，已自动转换。")
                    if len(parsed_tool) == 0:
                        st.error("请至少添加一个工具。")
                    else:
                        success_tools = []
                        for tool_name, tool_config in parsed_tool.items():
                            if "url" in tool_config:
                                tool_config["transport"] = "sse"
                                st.info(
                                    f"工具「{tool_name}」含 URL，已将传输方式设为 sse。"
                                )
                            elif "transport" not in tool_config:
                                tool_config["transport"] = "stdio"
                            if (
                                "command" not in tool_config
                                and "url" not in tool_config
                            ):
                                st.error(
                                    f"工具「{tool_name}」须包含 `command` 或 `url` 字段。"
                                )
                            elif "command" in tool_config and "args" not in tool_config:
                                st.error(
                                    f"工具「{tool_name}」使用 command 时须包含 `args` 字段。"
                                )
                            elif "command" in tool_config and not isinstance(
                                tool_config["args"], list
                            ):
                                st.error(
                                    f"工具「{tool_name}」的 `args` 须为数组（[]）格式。"
                                )
                            else:
                                st.session_state.pending_mcp_config[tool_name] = (
                                    tool_config
                                )
                                success_tools.append(tool_name)
                        if success_tools:
                            if main.reconnect_agent(
                                spinner_label="正在添加 MCP 工具并重新连接…"
                            ):
                                if len(success_tools) == 1:
                                    st.success(
                                        f"✅ 已添加并启用工具「{success_tools[0]}」。"
                                    )
                                else:
                                    tool_names = ", ".join(success_tools)
                                    st.success(
                                        f"✅ 已添加并启用 {len(success_tools)} 个工具（{tool_names}）。"
                                    )
                                st.session_state.mcp_tools_expander = False
                                st.rerun()
                            else:
                                st.error("❌ 工具已写入配置，但连接 MCP 失败。")
            except json.JSONDecodeError as e:
                st.error(f"JSON 解析错误：{e}")
                st.markdown(
                    """
                **修复建议**：
                1. 检查 JSON 格式是否正确。
                2. 所有键名须用双引号（"）包裹。
                3. 字符串值也须用双引号包裹。
                4. 字符串内的双引号须转义（\\"）。
                """
                )
            except Exception as e:
                st.error(f"发生错误：{e}")

    with st.expander("📋 已注册工具列表", expanded=True):
        try:
            pending_config = st.session_state.pending_mcp_config
        except Exception as e:
            st.error("不是有效的 MCP 工具配置。")
        else:
            for tool_name in list(pending_config.keys()):
                display_name = format_mcp_server_label(tool_name)
                col1, col2 = st.columns([7, 2])
                with col1:
                    st.markdown(f"- **{display_name}**")
                    if display_name != tool_name:
                        st.caption(f"标识：{tool_name}")
                if col2.button("删除", key=f"delete_{tool_name}"):
                    del st.session_state.pending_mcp_config[tool_name]
                    if main.reconnect_agent(
                        spinner_label=f"正在移除工具「{display_name}」并重新连接…"
                    ):
                        st.success(f"✅ 已删除并停用工具「{display_name}」。")
                        st.rerun()
                    else:
                        st.error(
                            f"❌ 已从配置移除「{display_name}」，但重连 MCP 失败。"
                        )

            mcp_tools = st.session_state.get("mcp_tools") or []
            if mcp_tools:
                with st.expander(
                    f"工具能力明细（{len(mcp_tools)} 个）", expanded=False
                ):
                    for tool in mcp_tools:
                        raw_name = getattr(tool, "name", None) or str(tool)
                        label = tlog.get_tool_display_label(raw_name)
                        if label != raw_name:
                            st.markdown(f"- **{label}** · `{raw_name}`")
                        else:
                            st.markdown(f"- `{raw_name}`")


def _apply_pending_restore_rebuild() -> None:
    """恢复会话快照后重建 Agent（Prompt 模式可能变化）。"""
    if not st.session_state.pop("_pending_restore_rebuild", False):
        return
    main = get_app_module()
    if st.session_state.session_initialized:
        main.rebuild_agent_only(spinner_label="正在恢复会话上下文…")
    else:
        main.reconnect_agent(spinner_label="正在恢复会话并连接 MCP…")


def _render_session_restore_banner() -> None:
    """P0：刷新后可恢复上次结构化快照。"""
    init_session_store_state()
    if st.session_state.get("_session_restore_checked"):
        return
    if st.session_state.get("history"):
        st.session_state._session_restore_checked = True
        return
    if not has_restorable_latest():
        st.session_state._session_restore_checked = True
        return

    desc = describe_latest_for_restore()
    st.info(f"检测到未完成的会话快照：{desc}")
    col_restore, col_discard = st.columns(2)
    with col_restore:
        if st.button("恢复上次会话", key="restore_latest_session", use_container_width=True):
            snapshot = load_latest_snapshot()
            if snapshot:
                apply_snapshot(snapshot)
                st.session_state._session_restore_checked = True
                st.session_state._pending_restore_rebuild = True
                mark_mode_segmented_sync_from_app()
                st.success("✅ 已恢复会话。")
                st.rerun()
    with col_discard:
        if st.button("放弃恢复", key="discard_latest_session", use_container_width=True):
            clear_persisted_latest()
            st.session_state._session_restore_checked = True
            st.rerun()


def _render_memory_panel() -> None:
    """记忆面板：长期画像、本轮旅行进度（可选）、已归档对话。"""
    st.subheader("🧠 记忆面板")

    with st.expander("跨会话记忆（画像 + 会话摘要）", expanded=False):
        try:
            from memory_recall import format_long_term_memory_markdown

            st.markdown(format_long_term_memory_markdown())
            st.caption(
                "归档或生成攻略后自动更新；偏好也可在对话中说「请记住…」。"
                "历史整段备份见下方「已归档对话」。"
            )
        except Exception as exc:
            st.caption(f"长期记忆暂不可用：{exc}")

    if st.session_state.get("app_mode") == tm.APP_MODE_TRAVEL:
        with st.expander("本轮旅行进度", expanded=False):
            st.markdown(format_session_state_markdown())
            st.caption(
                "仅 **当前页** 的行程需求、阶段与工具摘要；"
                "不是聊天气泡全文，也不是跨会话长期记忆。"
            )

    archives = list_archives(limit=5)
    if archives:
        with st.expander(f"已归档对话（{len(archives)}）", expanded=False):
            for idx, item in enumerate(archives):
                label = item.get("label") or os.path.basename(item["path"])
                saved = (item.get("saved_at") or "")[:19]
                st.caption(f"{label} · {saved}")
                if st.button(
                    f"恢复：{label[:20]}",
                    key=f"restore_archive_{idx}",
                    use_container_width=True,
                ):
                    snapshot = load_snapshot_from_file(item["path"])
                    if snapshot:
                        apply_snapshot(snapshot)
                        save_latest_autosave()
                        st.session_state._pending_restore_rebuild = True
                        mark_mode_segmented_sync_from_app()
                        st.success(f"✅ 已从归档恢复：{label}")
                        st.rerun()


_NEW_CHAT_HELP = (
    "将当前会话归档（保留行程需求、工具摘要、"
    "导出指针与最近聊天气泡），然后打开空白页。可在记忆面板下恢复会话。"
    "适合「大理行程告一段落，开始规划桂林」。"
)
_RESET_CHAT_HELP = (
    "不归档，直接清空当前页聊天、Agent checkpoint 与旅行进度；"
    "磁盘上的 latest.json 快照一并删除。适合排错或彻底重来。"
)


def _render_conversation_actions() -> None:
    st.subheader("🔄 对话操作")

    if st.button(
        "新对话（归档当前）",
        use_container_width=True,
        type="secondary",
        help=_NEW_CHAT_HELP,
    ):
        path = archive_current_session()
        start_blank_session(keep_preferences=True)
        if path:
            st.toast(
                "已成功归档，可从【记忆面板 → 已归档对话】中恢复",
                icon="📦",
            )
        else:
            st.toast("当前无内容可归档，已打开空白页", icon="📄")
        st.rerun()

    if st.button(
        "重置对话（不保留）",
        use_container_width=True,
        type="primary",
        help=_RESET_CHAT_HELP,
    ):
        clear_persisted_latest()
        start_blank_session(keep_preferences=True)
        st.success("✅ 对话已重置。")
        st.rerun()


def _render_exports_and_actions(*, use_login: bool) -> None:
    main = get_app_module()
    exports = st.session_state.get("exported_files") or []
    if exports:
        st.divider()
        st.subheader("📥 已导出 Markdown")
        for idx, entry in enumerate(reversed(exports[-5:])):
            abs_path = entry.get("abs_path") or main._abs_export_path(
                entry.get("path", "")
            )
            if not os.path.isfile(abs_path):
                continue
            with open(abs_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ {entry.get('filename', os.path.basename(abs_path))}",
                    data=f.read(),
                    file_name=entry.get("filename", os.path.basename(abs_path)),
                    mime="text/markdown",
                    key=f"sidebar_export_{abs_path}_{idx}",
                    use_container_width=True,
                )

    st.divider()
    st.subheader("⏱️ 耗时测试")
    history = st.session_state.get("timing_history") or []
    st.caption(f"已记录 {len(history)} 个回合（含 LLM 与 MCP 工具分段）。")
    if history:
        last = history[-1]
        summary = last.get("summary") or {}
        st.markdown(
            f"最近一回合：**{last.get('total_ms')} ms** "
            f"（LLM {summary.get('llm_total_ms', 0)} ms / "
            f"RAG {summary.get('rag_total_ms', 0)} ms / "
            f"工具 {summary.get('tool_total_ms', 0)} ms）"
        )
        report_md = tlog.format_timing_report_markdown(history)
        report_json = tlog.format_timing_report_json(history)
        st.download_button(
            label="⬇️ 导出耗时测试条例（Markdown）",
            data=report_md.encode("utf-8"),
            file_name=f"timing-test-report-{len(history)}-turns.md",
            mime="text/markdown",
            key="download_timing_md",
            use_container_width=True,
        )
        st.download_button(
            label="⬇️ 导出原始数据（JSON）",
            data=report_json.encode("utf-8"),
            file_name=f"timing-test-data-{len(history)}-turns.json",
            mime="application/json",
            key="download_timing_json",
            use_container_width=True,
        )
        with st.expander("预览最近回合", expanded=False):
            st.markdown(tlog.format_turn_table(last))
    else:
        st.caption("完成对话后，可在此导出 Markdown 测试条例或 JSON 明细。")

    st.divider()
    _render_memory_panel()
    st.divider()
    _render_conversation_actions()

    if use_login and st.session_state.authenticated:
        st.divider()
        if st.button("退出登录", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            st.success("✅ 已退出登录。")
            st.rerun()


def render_sidebar(*, use_login: bool) -> None:
    """渲染完整侧边栏（模式 + 设置 + 导出/操作）。"""
    _apply_pending_mode_switch()
    _apply_pending_restore_rebuild()
    with st.sidebar:
        _render_session_restore_banner()
        st.subheader("📋 对话模式")
        _render_mode_segment()
        st.divider()
        st.subheader("⚙️ 系统设置")
        _render_system_settings()
        st.divider()
        st.subheader("🔧 工具设置")
        _render_mcp_tools()
        _render_exports_and_actions(use_login=use_login)
