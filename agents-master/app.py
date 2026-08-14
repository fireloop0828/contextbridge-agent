import streamlit as st
import asyncio
import importlib
import nest_asyncio
import os
import platform
import re
import traceback

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
else:
    # Streamlit 会 uvloop.install()，nest_asyncio 无法 patch uvloop.Loop
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# 应用 nest_asyncio：允许在已运行的事件循环中嵌套调用异步代码
nest_asyncio.apply()

# 创建并复用全局事件循环（只创建一次，持续使用）
if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    st.session_state.event_loop = loop
    asyncio.set_event_loop(loop)

from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.tool_node import ToolNode
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langsmith_config import apply_langsmith_env
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils import astream_graph, random_uuid
from export_service import save_markdown_export, travel_export_filename
from modes.travel import state_machine as tm
import timing_log as tlog
from prompts import build_system_prompt
from config import (
    APP_DIR,
    EXPORT_OUTPUT_DIR,
    configs_equal,
    create_chat_model,
    get_available_models,
    load_config_from_json,
    mcp_config_signature,
    resolve_mcp_config,
    save_config_to_json,
)

# Streamlit 长驻进程可能缓存旧版 travel_mode，开发时热更新后需 reload
if not hasattr(tm, "PHASE_POI_SELECTION"):
    importlib.reload(tm)
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig

# 加载环境变量（从 .env 读取 API 密钥等配置）
load_dotenv(override=True)
# 应用 LangSmith 追踪配置（未填 Key 时默认关闭）
apply_langsmith_env()

# 初始化登录相关会话状态
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 是否启用登录
use_login = os.environ.get("USE_LOGIN", "false").lower() == "true"


def get_main_page_branding() -> dict[str, str]:
    """根据当前对话模式返回页面标题、说明与浏览器标签文案。"""
    from modes.registry import branding

    b = branding()
    return {
        "page_title": b.page_title,
        "page_icon": b.page_icon,
        "title": b.title,
        "subtitle": b.subtitle,
    }


# 根据登录状态设置页面布局
if use_login and not st.session_state.authenticated:
    # 登录页使用默认（较窄）布局
    st.set_page_config(page_title="MCP 智能体", page_icon="🧠")
else:
    tm.init_travel_state()
    _page_branding = get_main_page_branding()
    st.set_page_config(
        page_title=_page_branding["page_title"],
        page_icon=_page_branding["page_icon"],
        layout="wide",
    )

# 启用登录且未认证时显示登录页
if use_login and not st.session_state.authenticated:
    st.title("🔐 登录")
    st.markdown("使用本系统前请先登录。")

    # 登录表单（窄屏居中展示）
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submit_button = st.form_submit_button("登录")

        if submit_button:
            expected_username = os.environ.get("USER_ID")
            expected_password = os.environ.get("USER_PASSWORD")

            if username == expected_username and password == expected_password:
                st.session_state.authenticated = True
                st.success("✅ 登录成功，请稍候…")
                st.rerun()
            else:
                st.error("❌ 用户名或密码错误。")

    # 登录页不渲染主应用
    st.stop()

# 主页面标题与说明（随对话模式切换）
_main_page_branding = get_main_page_branding()
st.title(_main_page_branding["title"])
st.markdown(_main_page_branding["subtitle"])


# 初始化会话状态
if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = False  # 会话是否已初始化
    st.session_state.agent = None  # ReAct 智能体实例
    st.session_state.history = []  # 对话历史
    st.session_state.mcp_client = None  # MCP 客户端实例
    st.session_state.timeout_seconds = (
        300  # 响应超时（秒），默认 300
    )
    _default_models = get_available_models()
    st.session_state.selected_model = (
        _default_models[0] if _default_models else "qwen-plus-2025-07-28"  # 默认模型
    )
    st.session_state.recursion_limit = 100  # 递归调用上限，默认 100

if "thread_id" not in st.session_state:
    st.session_state.thread_id = random_uuid()

if "exported_files" not in st.session_state:
    st.session_state.exported_files = []

if "applied_model" not in st.session_state:
    st.session_state.applied_model = st.session_state.get("selected_model", "")

tm.init_travel_state()
from session_store import init_session_store_state

init_session_store_state()
from memory_store import sync_profile_preferences_to_session

sync_profile_preferences_to_session()
tlog.init_timing_history()

# --- 函数定义 ---


def _abs_export_path(rel_or_abs: str) -> str:
    """将 data/outputs/... 转为绝对路径。"""
    path = rel_or_abs.strip().replace("\\", "/")
    if os.path.isabs(path):
        return path
    if path.startswith("data/outputs/"):
        return os.path.join(APP_DIR, path)
    return os.path.join(EXPORT_OUTPUT_DIR, os.path.basename(path))


def extract_export_paths(final_tool: str) -> list[str]:
    """从工具调用输出中解析已写入的 Markdown 相对路径。"""
    if not final_tool:
        return []
    paths: list[str] = []
    for match in re.finditer(r"data/outputs/[A-Za-z0-9_\-\u4e00-\u9fff.]+\.md", final_tool):
        paths.append(match.group(0))
    for blob in re.finditer(r"\{[^{}]*\"path\"\s*:\s*\"([^\"]+)\"[^{}]*\}", final_tool):
        p = blob.group(1).replace("\\", "/")
        if p.endswith(".md") and "outputs" in p:
            paths.append(p if p.startswith("data/") else f"data/outputs/{os.path.basename(p)}")
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen and os.path.isfile(_abs_export_path(p)):
            seen.add(p)
            unique.append(p)
    return unique


def _register_exports(paths: list[str]) -> None:
    """记录本次会话内生成的导出文件（去重）。"""
    for rel in paths:
        abs_path = _abs_export_path(rel)
        if not os.path.isfile(abs_path):
            continue
        entry = {
            "path": rel,
            "filename": os.path.basename(abs_path),
            "abs_path": abs_path,
        }
        if not any(e.get("abs_path") == abs_path for e in st.session_state.exported_files):
            st.session_state.exported_files.append(entry)


def render_export_downloads(export_paths: list[str], *, key_prefix: str = "dl") -> None:
    """在助手消息下方展示 Markdown 下载按钮。"""
    if not export_paths:
        return
    st.caption("📥 可下载的 Markdown 成品")
    cols = st.columns(min(len(export_paths), 3))
    for idx, rel in enumerate(export_paths):
        abs_path = _abs_export_path(rel)
        if not os.path.isfile(abs_path):
            continue
        with cols[idx % len(cols)]:
            with open(abs_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ {os.path.basename(abs_path)}",
                    data=f.read(),
                    file_name=os.path.basename(abs_path),
                    mime="text/markdown",
                    key=f"{key_prefix}_{abs_path}_{idx}",
                    use_container_width=True,
                )


async def cleanup_mcp_client(*, clear_tools: bool = True):
    """
    重置 MCP 客户端引用。

    langchain-mcp-adapters >= 0.1 不再支持 async with 上下文管理器，
    每次工具调用会自行建连，此处仅清空 session 中的 client 引用。
    """
    st.session_state.mcp_client = None
    if clear_tools:
        st.session_state.mcp_tools = None
        st.session_state.applied_mcp_config_sig = None


def get_streaming_callback(text_placeholder, tool_placeholder, timing: tlog.TimingCollector | None = None):
    """
    创建流式输出回调函数。

    实时展示 LLM 生成的文本回复与工具调用信息，分区域显示。

    参数:
        text_placeholder: 用于展示文本回复的 Streamlit 占位组件
        tool_placeholder: 用于展示工具调用的 Streamlit 占位组件

    返回:
        callback_func: 流式回调函数
        accumulated_text: 累积的文本片段列表
        accumulated_tool: 累积的工具调用信息列表
    """
    accumulated_text = []
    accumulated_tool = []

    def callback_func(message: dict):
        nonlocal accumulated_text, accumulated_tool
        if timing is not None:
            timing.on_stream_message(message)
        message_content = message.get("content", None)

        if isinstance(message_content, AIMessageChunk):
            content = message_content.content
            # 内容为列表形式（多见于 Claude 模型）
            if isinstance(content, list) and len(content) > 0:
                message_chunk = content[0]
                # 处理文本块
                if message_chunk["type"] == "text":
                    accumulated_text.append(message_chunk["text"])
                    text_placeholder.markdown("".join(accumulated_text))
                # 处理工具调用块
                elif message_chunk["type"] == "tool_use":
                    if "partial_json" in message_chunk:
                        accumulated_tool.append(message_chunk["partial_json"])
                    else:
                        tool_call_chunks = message_content.tool_call_chunks
                        tool_call_chunk = tool_call_chunks[0]
                        accumulated_tool.append(
                            "\n```json\n" + str(tool_call_chunk) + "\n```\n"
                        )
                    with tool_placeholder.expander(
                        "🔧 工具调用详情", expanded=True
                    ):
                        st.markdown("".join(accumulated_tool))
            # 存在 tool_calls 属性（多见于 OpenAI 模型）
            elif (
                hasattr(message_content, "tool_calls")
                and message_content.tool_calls
                and len(message_content.tool_calls[0]["name"]) > 0
            ):
                tool_call_info = message_content.tool_calls[0]
                accumulated_tool.append("\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 工具调用详情", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # 内容为普通字符串
            elif isinstance(content, str):
                accumulated_text.append(content)
                text_placeholder.markdown("".join(accumulated_text))
            # 存在无效的工具调用信息
            elif (
                hasattr(message_content, "invalid_tool_calls")
                and message_content.invalid_tool_calls
            ):
                tool_call_info = message_content.invalid_tool_calls[0]
                accumulated_tool.append("\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 工具调用详情（无效）", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # 存在 tool_call_chunks 属性
            elif (
                hasattr(message_content, "tool_call_chunks")
                and message_content.tool_call_chunks
            ):
                tool_call_chunk = message_content.tool_call_chunks[0]
                accumulated_tool.append(
                    "\n```json\n" + str(tool_call_chunk) + "\n```\n"
                )
                with tool_placeholder.expander(
                    "🔧 工具调用详情", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # additional_kwargs 中含 tool_calls（兼容多种模型）
            elif (
                hasattr(message_content, "additional_kwargs")
                and "tool_calls" in message_content.additional_kwargs
            ):
                tool_call_info = message_content.additional_kwargs["tool_calls"][0]
                accumulated_tool.append("\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 工具调用详情", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
        # 工具执行结果消息（ToolMessage）
        elif isinstance(message_content, ToolMessage):
            accumulated_tool.append(
                "\n```json\n" + str(message_content.content) + "\n```\n"
            )
            with tool_placeholder.expander("🔧 工具调用详情", expanded=True):
                st.markdown("".join(accumulated_tool))
        return None

    return callback_func, accumulated_text, accumulated_tool


def format_agent_error(exc: BaseException) -> tuple[str, str | None]:
    """
    将底层异常转为用户可读说明。

    返回:
        (展示用短消息, 完整 traceback 或 None)
    """
    detail = traceback.format_exc()
    raw = str(exc)
    model = st.session_state.get("selected_model", "未知")

    if "AllocationQuota.FreeTierOnly" in raw or (
        "free tier" in raw.lower() and "exhausted" in raw.lower()
    ):
        return (
            f"❌ 模型 **{model}** 的百炼**免费额度已用尽**（403）。\n\n"
            "请到 [阿里云百炼控制台](https://bailian.console.aliyun.com/)：\n"
            "1. 关闭「**仅使用免费额度**」并开通按量付费；或\n"
            "2. 侧边栏换用其他已开通且有额度的模型，点击 **「应用」**。\n\n"
            "旅行规划会多次调用 MCP 工具，Token 消耗较大，免费额度容易在生成阶段耗尽。",
            detail,
        )

    try:
        from openai import AuthenticationError, RateLimitError

        if isinstance(exc, AuthenticationError):
            return (
                "❌ API 密钥无效或未授权。请检查 `.env` 中的 `DASHSCOPE_API_KEY` 是否有效。",
                detail,
            )
        if isinstance(exc, RateLimitError):
            return (
                f"❌ 模型 **{model}** 触发限流或配额不足，请稍后重试或升级百炼套餐。",
                detail,
            )
    except ImportError:
        pass

    if "403" in raw and (
        "PermissionDenied" in type(exc).__name__ or "permission" in raw.lower()
    ):
        return (
            f"❌ 无权使用模型 **{model}**（403）。请确认百炼控制台已开通该模型并具备可用额度。",
            detail,
        )

    if "429" in raw or "rate limit" in raw.lower():
        return ("❌ 请求过于频繁（429），请稍后再试。", detail)

    if "CUQPS_HAS_EXCEEDED_THE_LIMIT" in raw or "EXCEEDED_THE_LIMIT" in raw:
        return (
            "❌ **高德地图 API 并发超限**（CUQPS_HAS_EXCEEDED_THE_LIMIT）。\n\n"
            "旅行生成阶段会连续调用地理编码/路线规划，免费或低配 Key 容易触发限流。\n\n"
            "建议：\n"
            "1. 稍等 10–30 秒后点击「重置对话」或重新发送「继续生成」；\n"
            "2. 登录 [高德开放平台](https://console.amap.com/) 检查 Key 的 **QPS/日配额** 并升级；\n"
            "3. 换用配额更高的 Web 服务 Key 写入 `.env` 的 `AMAP_MAPS_API_KEY`。\n\n"
            "已优化：同类工具错误将回传给 Agent 尝试降级继续，但若连续超限仍可能失败。",
            detail,
        )

    if "401" in raw or "authentication" in raw.lower():
        return ("❌ API 认证失败，请检查密钥配置。", detail)

    return (f"❌ 处理问题时出错：{raw}", detail)


def _mcp_tool_error_message(exc: Exception) -> str:
    """
    MCP 工具失败时回传给 LLM 的说明（避免整轮对话崩溃，便于降级继续）。
    """
    raw = str(exc)
    if "CUQPS_HAS_EXCEEDED_THE_LIMIT" in raw or "EXCEEDED_THE_LIMIT" in raw:
        return (
            "【高德 API 并发超限 CUQPS】本次工具调用被拒绝。"
            "请不要再连续调用 maps_geo、maps_direction_*、maps_distance；"
            "改用 maps_text_search / maps_search_detail 已有信息，"
            "路线与坐标在攻略中标注「待核实」或给出经验估算，并继续完成正文。"
        )
    if "DAILY_QUERY_OVER_LIMIT" in raw or "USER_DAILY_QUERY_OVER_LIMIT" in raw:
        return (
            "【高德 API 日配额超限】今日调用已达上限。"
            "请跳过高德路线/地理编码，用 RAG 与已有 POI 信息完成攻略，"
            "交通章节标注「待核实」。"
        )
    if "INVALID_USER_KEY" in raw or "INVALID_USER_SCODE" in raw:
        return f"【高德 API 密钥无效】{raw}。请检查 AMAP_MAPS_API_KEY。"
    return f"【工具调用失败】{raw}"


async def process_query(
    query,
    text_placeholder,
    tool_placeholder,
    timeout_seconds=60,
    timing: tlog.TimingCollector | None = None,
    recursion_limit: int | None = None,
):
    """
    处理用户提问并生成流式回复。

    将问题交给智能体，实时流式返回结果；超时则返回错误信息。

    参数:
        query: 用户输入的问题文本
        text_placeholder: 展示文本回复的 Streamlit 组件
        tool_placeholder: 展示工具调用的 Streamlit 组件
        timeout_seconds: 响应超时时间（秒）

    返回:
        response: 智能体响应对象
        final_text: 最终文本回复
        final_tool: 最终工具调用信息
    """
    try:
        if st.session_state.agent:
            streaming_callback, accumulated_text_obj, accumulated_tool_obj = (
                get_streaming_callback(text_placeholder, tool_placeholder, timing)
            )
            try:
                response = await asyncio.wait_for(
                    astream_graph(
                        st.session_state.agent,
                        {"messages": [HumanMessage(content=query)]},
                        callback=streaming_callback,
                        config=RunnableConfig(
                            recursion_limit=(
                                recursion_limit
                                if recursion_limit is not None
                                else st.session_state.recursion_limit
                            ),
                            thread_id=st.session_state.thread_id,
                        ),
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                error_msg = f"⏱️ 请求已超过 {timeout_seconds} 秒，请稍后重试。"
                return {"error": error_msg}, error_msg, ""

            final_text = "".join(accumulated_text_obj)
            final_tool = "".join(accumulated_tool_obj)
            return response, final_text, final_tool
        else:
            return (
                {"error": "🚫 智能体尚未初始化。"},
                "🚫 智能体尚未初始化。",
                "",
            )
    except Exception as e:
        friendly, detail = format_agent_error(e)
        return {"error": friendly, "error_detail": detail}, friendly, ""


def auto_export_travel_plan_from_chat(
    display_text: str,
    intake: dict,
    *,
    phase: str = "",
) -> list[str]:
    """
    O5：将对话中的完整攻略正文服务端写入文件，避免 LLM 在 write_markdown_document 再输出一遍。
    仅当正文结构确认为完整攻略时写盘（intake/POI 问答不会触发）。
    """
    plan_part, appendix = tm.split_travel_plan_and_appendix(display_text)
    if not tm.looks_like_travel_plan(plan_part):
        return []
    body = tm.normalize_travel_plan_body(plan_part).strip()
    if not body:
        return []
    if appendix:
        body = body.rstrip() + "\n\n" + appendix
    dest = (intake.get("destination") or "旅行攻略").strip()
    days = intake.get("duration_days")
    title = f"{dest}旅行攻略" if not days else f"{dest}{days}日攻略"
    rel = save_markdown_export(
        body,
        title=title,
        filename=travel_export_filename(intake),
    )
    return [rel] if rel else []


async def _build_agent_from_tools(tools: list) -> None:
    """用已加载的 MCP 工具列表构建 ReAct Agent。"""
    model = create_chat_model(st.session_state.selected_model)
    prompt_mode = st.session_state.get("app_mode", tm.APP_MODE_GENERAL)
    st.session_state.agent_prompt_mode = prompt_mode
    system_prompt = build_system_prompt(prompt_mode)
    tool_node = ToolNode(tools, handle_tool_errors=_mcp_tool_error_message)
    st.session_state.agent = create_react_agent(
        model,
        tool_node,
        checkpointer=MemorySaver(),
        prompt=system_prompt,
    )
    st.session_state.session_initialized = True


async def initialize_session(mcp_config=None):
    """
    初始化 MCP 会话与智能体（全量：连接所有 MCP Server 并 get_tools）。

    参数:
        mcp_config: MCP 工具配置（JSON 结构）；为 None 时从 config.json 读取

    返回:
        bool: 是否初始化成功
    """
    try:
        load_dotenv(override=True)
        await cleanup_mcp_client()

        if mcp_config is None:
            mcp_config = load_config_from_json()
        mcp_config = resolve_mcp_config(mcp_config)

        client = MultiServerMCPClient(mcp_config)
        tools = await client.get_tools()
        st.session_state.tool_count = len(tools)
        st.session_state.mcp_client = client
        st.session_state.mcp_tools = tools
        st.session_state.applied_mcp_config_sig = mcp_config_signature(mcp_config)

        await _build_agent_from_tools(tools)
        return True
    except Exception as e:
        st.session_state.session_initialized = False
        st.session_state.agent = None
        st.session_state.mcp_tools = None
        st.error(f"❌ 初始化失败：{e}")
        with st.expander("查看错误详情"):
            st.code(traceback.format_exc())
        return False


async def _rebuild_agent_from_cached_tools() -> bool:
    """仅重建 Agent（复用已缓存的 mcp_tools，不重新 get_tools）。"""
    tools = st.session_state.get("mcp_tools")
    if not tools:
        return False
    await _build_agent_from_tools(tools)
    return True


def rebuild_agent_only(*, spinner_label: str = "正在更新智能体…") -> bool:
    """切换模型 / 对话模式时调用：不重连 MCP，只重建 Agent。"""
    if not st.session_state.get("mcp_tools"):
        return reconnect_agent(spinner_label=spinner_label, reload_mcp=True)
    load_dotenv(override=True)
    with st.spinner(spinner_label):
        success = st.session_state.event_loop.run_until_complete(
            _rebuild_agent_from_cached_tools()
        )
    if success:
        st.session_state.applied_model = st.session_state.selected_model
        st.session_state.agent_prompt_mode = st.session_state.get(
            "app_mode", tm.APP_MODE_GENERAL
        )
    return success


def get_mcp_config() -> dict:
    """获取当前 MCP 配置（与 config.json 同步）。"""
    if "pending_mcp_config" not in st.session_state:
        st.session_state.pending_mcp_config = load_config_from_json()
    return st.session_state.pending_mcp_config


def reconnect_agent(
    *,
    mcp_config: dict | None = None,
    spinner_label: str = "正在连接 MCP 并启动智能体…",
    reload_mcp: bool = True,
) -> bool:
    """
    重建 Agent。默认全量重连 MCP；reload_mcp=False 时仅复用已缓存工具（同 rebuild_agent_only）。
    """
    if not reload_mcp:
        return rebuild_agent_only(spinner_label=spinner_label)

    load_dotenv(override=True)
    config = mcp_config if mcp_config is not None else get_mcp_config()
    st.session_state.pending_mcp_config = config

    persisted = load_config_from_json()
    if not configs_equal(config, persisted):
        save_config_to_json(config)

    st.session_state.session_initialized = False
    st.session_state.agent = None
    with st.spinner(spinner_label):
        success = st.session_state.event_loop.run_until_complete(
            initialize_session(config)
        )
    if success:
        st.session_state.applied_model = st.session_state.selected_model
        st.session_state.agent_prompt_mode = st.session_state.get(
            "app_mode", tm.APP_MODE_GENERAL
        )
    return success


def ensure_session_ready() -> bool:
    """若尚未初始化则自动连接 MCP（用于首次进入页面）。"""
    if st.session_state.session_initialized:
        return True
    return reconnect_agent(spinner_label="正在连接 MCP 服务器…")


from ui.chat import render_chat
from ui.sidebar import render_sidebar

render_sidebar(use_login=use_login)

if not st.session_state.session_initialized:
    ensure_session_ready()

render_chat()
