"""知识库问答模式：LangGraph 图内编排（node / edge / state）。

将 RAG 问答流程拆分为确定性工具链节点 + 少量 LLM 决策点：
    extract_question → classify → list_collections → select_collection
    → query_knowledge →(空结果重试)→ summarize(可选) → answer

本图兼容 app.process_query 的调用协议：
    astream(graph, {"messages": [HumanMessage(...)]}, stream_mode="messages")
即输入含 messages 通道、answer 节点以流式 AIMessageChunk 产出文本。
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from . import rag_tools

logger = logging.getLogger(__name__)

MAX_QUERY_RETRIES = 2
DEFAULT_TOP_K = 5

# 兜底规则：判断是否需要文档总结
_SUMMARY_INTENT_RE = re.compile(r"(总结|概括|概述)\s*(这篇|这个|该)?\s*文档")

# system.md 里定义的推荐流程关键词，用于 classify 快速兜底判断
_RAG_INTENT_HINTS = re.compile(
    r"(知识库|检索|查一下|查询|文档|资料|手册|collection|"
    r"有哪些集合|list_collections|query_knowledge|RAG|"
    r"知识 hub|travel_plan|embedding|向量库|入库|总结.*文档|"
    r"这篇文档|这个文档|该文档|文档里)",
    re.IGNORECASE,
)


class RagState(TypedDict, total=False):
    """知识库问答图状态。"""

    messages: Annotated[list[AnyMessage], add_messages]
    question: str
    needs_rag: bool
    needs_summary: bool
    collection_hint: str
    collections: list[str]
    collection: str
    query: str
    rag_results: list[dict[str, Any]]
    rag_text: str
    retries: int


def _last_human_question(messages: list[AnyMessage]) -> str:
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                return "\n".join(parts)
    return ""


# ---------------------------------------------------------------------------
# 节点
# ---------------------------------------------------------------------------
def _push_status(message: str) -> None:
    """把人类可读的执行状态推送到界面状态区（tool_placeholder）。

    图在 app.process_query 内于 Streamlit 主线程运行，可安全访问
    session_state（与 rag_tools.fetch_collections 同模式）；纯测试等
    界面上下文不可用时静默跳过，不影响图执行。
    """
    try:
        import streamlit as st

        trace = list(st.session_state.get("knowledge_qa_status_trace") or [])
        if not trace or trace[-1] != message:
            trace.append(message)
        st.session_state["knowledge_qa_status_trace"] = trace
        placeholder = st.session_state.get("knowledge_qa_status_placeholder")
        if placeholder is not None:
            with placeholder.expander("🧭 执行状态", expanded=True):
                st.markdown("\n".join(f"- {m}" for m in trace))
    except Exception:
        pass


_USER_MEMORY_BLOCK_RE = re.compile(
    r"\[USER_MEMORY\].*?\[/USER_MEMORY\]", re.DOTALL
)


def _strip_user_memory_block(text: str) -> str:
    """剥离 memory_recall 注入的 [USER_MEMORY]...[/USER_MEMORY] 块，保留真实问题。"""
    s = _USER_MEMORY_BLOCK_RE.sub("", text or "")
    s = re.sub(r"^\s*---?\s*$", "", s, flags=re.MULTILINE).strip()
    return s


async def extract_question(state: RagState) -> dict:
    """从 messages 通道抽取最新用户问题（剥离记忆注入块）。"""
    raw = _last_human_question(state.get("messages") or [])
    if _USER_MEMORY_BLOCK_RE.search(raw or ""):
        _push_status("🧠 正在分析用户画像…")
    return {"question": _strip_user_memory_block(raw)}


async def classify(state: RagState) -> dict:
    """决策点①：LLM 判断是否需要 RAG、集合线索、是否需要文档摘要。"""
    _push_status("🧠 正在分析问题…")
    question = (state.get("question") or "").strip()
    model = _NODE_CTX["model"]  # 由 build_rag_graph 注入
    system = SystemMessage(
        content=(
            "你是知识库问答模式的问题分类器。仅根据用户问题输出 JSON，不要解释：\n"
            '{"needs_rag": bool, "collection_hint": str, "needs_summary": bool}\n'
            "- needs_rag：问题是否需要检索知识库（查文档/资料/手册/集合内容）。"
            "闲聊、寒暄、与知识库无关的通用问题为 false。\n"
            "- collection_hint：问题中明确提到的集合名（如 travel_plan），没有则为空字符串。\n"
            "- needs_summary：用户是否要求总结某个文档内容（涉及 get_document_summary）。"
        )
    )
    try:
        resp = await model.ainvoke([system, HumanMessage(content=question)])
        data = rag_tools.try_parse_json(str(resp.content))
    except Exception as exc:
        logger.warning("classify LLM 调用失败，回退规则判断: %s", exc)
        data = None

    if isinstance(data, dict):
        needs_rag = bool(data.get("needs_rag", False))
        collection_hint = str(data.get("collection_hint") or "").strip()
        needs_summary = bool(data.get("needs_summary", False))
    else:
        # 兜底：规则判断
        needs_rag = bool(_RAG_INTENT_HINTS.search(question))
        collection_hint = _extract_collection_hint(question)
        needs_summary = bool(_SUMMARY_INTENT_RE.search(question))

    return {
        "needs_rag": needs_rag,
        "collection_hint": collection_hint,
        "needs_summary": needs_summary,
    }


def _extract_collection_hint(question: str) -> str:
    m = re.search(r"(?:collection|集合|在)\s*[：:]\s*([\w\-_]+)", question)
    if m:
        return m.group(1)
    m = re.search(r"`([\w\-_]+)`", question)
    if m:
        return m.group(1)
    return ""


async def list_collections(state: RagState) -> dict:
    """确定性调用 list_collections（带 session 缓存）。"""
    tools_map = _NODE_CTX["tools_map"]
    _push_status("🔎 需要检索知识库，正在查找可用知识库…")
    collections = await rag_tools.fetch_collections(tools_map)
    if not collections:
        _push_status("⚠️ 未能获取知识库列表（服务可能未连接）")
    return {"collections": collections}


async def select_collection(state: RagState) -> dict:
    """决策点②：选定检索集合（hint 命中直接用，否则 LLM 选择）。"""
    collections = state.get("collections") or []
    if not collections:
        _push_status("⚠️ 未找到可用的知识库集合，将使用默认集合重试")
        return {"collection": ""}

    hint = (state.get("collection_hint") or "").strip()
    if hint and hint in collections:
        _push_status(f"✅ 已选择集合：{hint}")
        return {"collection": hint}

    question = (state.get("question") or "").strip()
    model = _NODE_CTX["model"]
    listing = "\n".join(f"- {c}" for c in collections)
    system = SystemMessage(
        content=(
            "知识库有以下集合：\n"
            f"{listing}\n\n"
            "根据用户问题选择最相关的集合，只输出集合名（不要引号、不要解释）。\n"
            "无法判断时输出第一个集合名。"
        )
    )
    try:
        resp = await model.ainvoke([system, HumanMessage(content=question)])
        picked = str(resp.content).strip().strip("`\"' \n")
        if picked in collections:
            _push_status(f"✅ 已选择集合：{picked}")
            return {"collection": picked}
        # 输出可能带多余描述，做包含匹配
        for c in collections:
            if c in picked:
                _push_status(f"✅ 已选择集合：{c}")
                return {"collection": c}
    except Exception as exc:
        logger.warning("select_collection LLM 调用失败，回退默认集合: %s", exc)
    _push_status(f"✅ 已选择集合：{collections[0]}")
    return {"collection": collections[0]}


async def query_knowledge(state: RagState) -> dict:
    """确定性调用 query_knowledge_hub 并解析结果。"""
    tools_map = _NODE_CTX["tools_map"]
    question = (state.get("question") or "").strip()
    collection = (state.get("collection") or "").strip()
    query = (state.get("query") or question or "").strip()
    _push_status(f"🔍 正在检索「{query}」…")

    if "query_knowledge_hub" not in tools_map:
        logger.warning("query_knowledge_hub 工具未连接")
        return {"rag_results": [], "rag_text": ""}

    args: dict[str, Any] = {"query": query, "top_k": DEFAULT_TOP_K}
    if collection:
        args["collection"] = collection
    try:
        raw = await rag_tools.call_tool(tools_map, "query_knowledge_hub", args)
    except Exception as exc:
        logger.warning("query_knowledge_hub 调用失败: %s", exc)
        return {"rag_results": [], "rag_text": ""}

    items, meta = rag_tools.parse_rag_results(raw, query=query, collection=collection)
    rag_text = _format_rag_context(items, meta)
    return {"rag_results": items, "rag_text": rag_text}


async def retry_query(state: RagState) -> dict:
    """空结果时改写检索词重试（限次）。"""
    question = (state.get("question") or "").strip()
    retries = int(state.get("retries") or 0)
    collection = (state.get("collection") or "").strip()
    _push_status(f"🔄 未命中，正在换关键词重试（第 {retries + 1} 次）…")

    model = _NODE_CTX["model"]
    system = SystemMessage(
        content=(
            "你是检索词改写器。用户在上一个知识库集合中检索没有结果。\n"
            f"当前集合：{collection or '(未指定)'}\n"
            "根据用户问题改写出一个更短、更可能命中的检索关键词（5~20 字，"
            "提取核心实体/主题，去掉疑问语气）。只输出检索词本身。"
        )
    )
    try:
        resp = await model.ainvoke([system, HumanMessage(content=question)])
        new_query = str(resp.content).strip().strip("`\"' \n")
        new_query = new_query or question
    except Exception as exc:
        logger.warning("retry_query LLM 调用失败，使用原问题: %s", exc)
        new_query = question
    return {"query": new_query, "retries": retries + 1}


async def summarize(state: RagState) -> dict:
    """可选节点：对首个命中文档调用 get_document_summary。"""
    tools_map = _NODE_CTX["tools_map"]
    results = state.get("rag_results") or []
    _push_status("📄 正在获取文档摘要…")
    if not results or "get_document_summary" not in tools_map:
        return {}

    doc_id = str(results[0].get("source_doc") or "").strip()
    collection = (state.get("collection") or "").strip()
    if not doc_id:
        return {}
    args: dict[str, Any] = {"doc_id": doc_id}
    if collection:
        args["collection"] = collection
    try:
        raw = await rag_tools.call_tool(tools_map, "get_document_summary", args)
        summary_text = rag_tools.tool_result_to_text(raw)
    except Exception as exc:
        logger.warning("get_document_summary 调用失败: %s", exc)
        return {}

    rag_text = (state.get("rag_text") or "") + "\n\n【文档摘要】\n" + summary_text[:1200]
    return {"rag_text": rag_text}


async def answer(state: RagState) -> dict:
    """生成最终回答。

    节点内部调用 model.astream() 消费 token：
    - 真实 ChatModel 的 token 会触发 LangGraph 的 on_chat_model_stream 回调，
      由 stream_mode="messages" 逐 token 捕获（ui/chat.py 依赖此机制流式显示）
    - 节点返回完整 AIMessage 写入 messages 通道，保证最终状态正确
    """
    question = (state.get("question") or "").strip()
    rag_text = (state.get("rag_text") or "").strip()
    results = state.get("rag_results") or []
    needs_rag = bool(state.get("needs_rag", False))
    model = _NODE_CTX["model"]
    system_prompt = _NODE_CTX["system_prompt"]

    if needs_rag:
        if results:
            _push_status(f"✅ 检索完成（命中 {len(results)} 条），正在生成回答…")
        else:
            _push_status("❌ 未检索到相关内容，正在如实告知…")
    else:
        _push_status("💬 无需检索，正在直接回答…")

    parts: list[str] = [system_prompt]
    if needs_rag:
        if results:
            parts.append(
                "请基于下面的检索结果回答。来源信息由系统在回答后自动附加，"
                "正文中无需再罗列来源文件名。\n\n"
                f"【检索结果】\n{rag_text}"
            )
        else:
            parts.append(
                "用户需要检索知识库，但未检索到相关内容。"
                "请如实告知用户：知识库中没有找到与问题相关的内容，"
                "并建议换一种问法或检查集合名。不要编造内容。"
            )
    answer_messages: list[BaseMessage] = [SystemMessage(content="\n\n".join(parts))]
    # 携带最近对话历史（最多保留 6 条），保持上下文
    history = list(state.get("messages") or [])
    if history:
        answer_messages.extend(history[-6:])

    final_text = ""
    async for chunk in model.astream(answer_messages):
        final_text += str(getattr(chunk, "content", ""))
    final_text = final_text.strip()

    # 供界面在回答后程序化追加来源块（同一轮内由 ui/chat.py 消费）
    try:
        import streamlit as st

        sources_block = rag_tools.format_sources_block(results)
        if sources_block:
            st.session_state["knowledge_qa_last_sources"] = sources_block
        else:
            st.session_state.pop("knowledge_qa_last_sources", None)
    except Exception:
        pass

    return {"messages": [AIMessage(content=final_text)]}


# ---------------------------------------------------------------------------
# 条件边路由
# ---------------------------------------------------------------------------
def _route_after_classify(state: RagState) -> str:
    if state.get("needs_rag"):
        return "list_collections"
    return "answer"


def _route_after_list(state: RagState) -> str:
    if state.get("collections"):
        return "select_collection"
    return "answer"


def _route_after_query(state: RagState) -> str:
    if not state.get("rag_results"):
        retries = int(state.get("retries") or 0)
        return "retry_query" if retries < MAX_QUERY_RETRIES else "answer"
    if state.get("needs_summary"):
        return "summarize"
    return "answer"


def _route_after_retry(state: RagState) -> str:
    return "query_knowledge"


# 节点闭包上下文（由 build_rag_graph 注入，避免把不可序列化对象放进 state）
_NODE_CTX: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------
def _format_rag_context(
    items: list[dict[str, Any]], meta: dict[str, Any]
) -> str:
    if not items:
        return (meta.get("notice") or "未找到相关结果。")
    lines: list[str] = []
    for item in items:
        src = item.get("source_doc") or "(未知来源)"
        score = item.get("score") or ""
        excerpt = (item.get("excerpt") or "").strip()
        lines.append(f"- 来源：{src}" + (f"（相关度 {score}）" if score else ""))
        lines.append(f"  {excerpt}")
    return "\n".join(lines)


def build_rag_graph(
    tools: list[Any],
    model,
    system_prompt: str,
) -> Any:
    """构建知识库问答编排图。

    参数:
        tools: 已加载的 MCP 工具列表
        model: 聊天模型实例
        system_prompt: 知识库问答模式的 system prompt
    """
    _NODE_CTX.clear()
    _NODE_CTX["tools_map"] = rag_tools.tools_by_name(tools)
    _NODE_CTX["model"] = model
    _NODE_CTX["system_prompt"] = system_prompt

    graph = StateGraph(RagState)
    graph.add_node("extract_question", extract_question)
    graph.add_node("classify", classify)
    graph.add_node("list_collections", list_collections)
    graph.add_node("select_collection", select_collection)
    graph.add_node("query_knowledge", query_knowledge)
    graph.add_node("retry_query", retry_query)
    graph.add_node("summarize", summarize)
    graph.add_node("answer", answer)

    graph.add_edge(START, "extract_question")
    graph.add_edge("extract_question", "classify")
    graph.add_conditional_edges("classify", _route_after_classify)
    graph.add_edge("list_collections", "select_collection")
    graph.add_edge("select_collection", "query_knowledge")
    graph.add_conditional_edges("query_knowledge", _route_after_query)
    graph.add_conditional_edges("retry_query", _route_after_retry)
    graph.add_edge("summarize", "answer")
    graph.add_edge("answer", END)

    compiled = graph.compile()
    return compiled
