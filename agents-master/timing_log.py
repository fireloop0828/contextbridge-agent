"""轻量耗时采集：用于旅行规划/通用对话的性能测试与条例导出。"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# 工具名 → 使用目的（导出报告「使用目的」列）
_TOOL_PURPOSES: dict[str, str] = {
    "query_knowledge_hub": "混合检索+Rerank，获取攻略/景点知识",
    "list_collections": "列举可用知识库集合",
    "get_document_summary": "获取文档摘要与元信息",
    "maps_weather": "查询目的地天气预报",
    "maps_geo": "地址转经纬度坐标",
    "maps_text_search": "POI/景点关键词检索",
    "maps_search_detail": "查询 POI 详情（开放时间、评分等）",
    "maps_direction_driving": "驾车路线规划",
    "maps_direction_walking": "步行路线规划",
    "maps_direction_transit_integrated": "公共交通路线规划",
    "maps_direction_bicycling": "骑行路线规划",
    "get_current_time": "获取当前时间，解析相对日期",
    "write_markdown_document": "将行程 Markdown 写入本地文件",
}

_RAG_TOOL_NAMES = frozenset(
    {"query_knowledge_hub", "list_collections", "get_document_summary"}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _mono_ms(start: float, end: float | None = None) -> float:
    end = end if end is not None else time.monotonic()
    return round((end - start) * 1000.0, 1)


def _extract_tool_name_from_call_info(info: Any) -> str | None:
    if info is None:
        return None
    if isinstance(info, dict):
        name = info.get("name")
        if name:
            return str(name)
        func = info.get("function")
        if isinstance(func, dict) and func.get("name"):
            return str(func["name"])
    name = getattr(info, "name", None)
    if name:
        return str(name)
    return None


def _extract_tool_name_from_message_content(message_content: Any) -> str | None:
    try:
        from langchain_core.messages.tool import ToolMessage

        if isinstance(message_content, ToolMessage):
            if getattr(message_content, "name", None):
                return str(message_content.name)
    except ImportError:
        pass

    if hasattr(message_content, "tool_calls") and message_content.tool_calls:
        return _extract_tool_name_from_call_info(message_content.tool_calls[0])

    if hasattr(message_content, "tool_call_chunks") and message_content.tool_call_chunks:
        return _extract_tool_name_from_call_info(message_content.tool_call_chunks[0])

    ak = getattr(message_content, "additional_kwargs", None) or {}
    if isinstance(ak, dict) and ak.get("tool_calls"):
        return _extract_tool_name_from_call_info(ak["tool_calls"][0])

    content = getattr(message_content, "content", None)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                return item.get("name") or item.get("id")
    return None


def classify_tool(tool_name: str) -> tuple[str, str, str]:
    """
    将 MCP 工具名映射为报告列：具体类型 / 具体名称 / 使用目的。
    """
    name = tool_name or "unknown_tool"
    if name in _RAG_TOOL_NAMES:
        return (
            "mcp-server-rag",
            name,
            _TOOL_PURPOSES.get(name, "RAG 知识库检索"),
        )
    if name.startswith("maps_"):
        return (
            "mcp-server-高德",
            name,
            _TOOL_PURPOSES.get(name, "高德地图数据查询"),
        )
    if name == "get_current_time":
        return ("mcp-server-时间", name, _TOOL_PURPOSES[name])
    if name == "write_markdown_document":
        return ("mcp-server-文档导出", name, _TOOL_PURPOSES[name])
    if "rag" in name.lower() or "knowledge" in name.lower():
        return ("mcp-server-rag", name, _TOOL_PURPOSES.get(name, "RAG 知识库检索"))
    return ("mcp-server-其他", name, "MCP 工具调用")


def is_rag_tool(tool_name: str) -> bool:
    cat, _, _ = classify_tool(tool_name)
    return cat == "mcp-server-rag"


def enrich_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """为原始事件补充报告展示字段。"""
    enriched: list[dict[str, Any]] = []
    llm_round = 0
    for e in events:
        if e.get("type") == "llm":
            llm_round += 1
            enriched.append(
                {
                    **e,
                    "category_type": "LLM推理",
                    "display_name": f"第{llm_round}轮推理",
                    "purpose": "生成回复并决策工具调用",
                }
            )
        else:
            cat, display_name, purpose = classify_tool(str(e.get("name", "")))
            enriched.append(
                {
                    **e,
                    "category_type": cat,
                    "display_name": display_name,
                    "purpose": purpose,
                }
            )
    return enriched


class TimingCollector:
    """单次用户提问 → Agent 响应的耗时采集器。"""

    def __init__(self) -> None:
        self.turn_id = str(uuid4())[:8]
        self.meta: dict[str, Any] = {}
        self.started_mono = time.monotonic()
        self.started_at = _now_iso()
        self.events: list[dict[str, Any]] = []
        self._llm_start: float | None = time.monotonic()
        self._pending_tool: dict[str, float] = {}
        self._open_tool_name: str | None = None
        self.status = "running"
        self.error: str | None = None

    def set_meta(self, **kwargs: Any) -> None:
        self.meta.update(kwargs)

    def on_graph_node(self, node: str | None) -> None:
        if node:
            self.meta["last_graph_node"] = node

    def on_stream_message(self, message: dict[str, Any]) -> None:
        content = message.get("content")
        node = message.get("node")
        if node:
            self.on_graph_node(str(node))

        if content is None:
            return

        try:
            from langchain_core.messages.ai import AIMessageChunk
            from langchain_core.messages.tool import ToolMessage
        except ImportError:
            AIMessageChunk = type(None)  # type: ignore
            ToolMessage = type(None)  # type: ignore

        if AIMessageChunk != type(None) and isinstance(content, AIMessageChunk):
            tool_name = _extract_tool_name_from_message_content(content)
            if tool_name:
                self._start_tool(tool_name)
                return
            if isinstance(content.content, str) and content.content:
                self._touch_llm()
            elif isinstance(content.content, list):
                for item in content.content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        self._touch_llm()
                    elif item.get("type") == "tool_use":
                        self._start_tool(item.get("name") or "unknown_tool")
            return

        if ToolMessage != type(None) and isinstance(content, ToolMessage):
            name = _extract_tool_name_from_message_content(content) or self._open_tool_name
            self._end_tool(name or "unknown_tool")
            return

    def _touch_llm(self) -> None:
        if self._llm_start is None:
            self._llm_start = time.monotonic()

    def _finalize_llm_segment(self) -> None:
        if self._llm_start is None:
            return
        end = time.monotonic()
        self.events.append(
            {
                "type": "llm",
                "name": "model_inference",
                "duration_ms": _mono_ms(self._llm_start, end),
            }
        )
        self._llm_start = None

    def _start_tool(self, name: str) -> None:
        self._finalize_llm_segment()
        if self._open_tool_name and self._open_tool_name != name:
            self._end_tool(self._open_tool_name)
        self._open_tool_name = name
        if name not in self._pending_tool:
            self._pending_tool[name] = time.monotonic()

    def _end_tool(self, name: str) -> None:
        start = self._pending_tool.pop(name, None)
        if start is None and self._open_tool_name:
            start = self._pending_tool.pop(self._open_tool_name, None)
        if start is None:
            start = time.monotonic()
        end = time.monotonic()
        self.events.append(
            {
                "type": "tool",
                "name": name,
                "duration_ms": _mono_ms(start, end),
            }
        )
        if self._open_tool_name == name:
            self._open_tool_name = None
        self._llm_start = time.monotonic()

    def finish(self, *, status: str = "ok", error: str | None = None) -> dict[str, Any]:
        if self._open_tool_name:
            self._end_tool(self._open_tool_name)
        self._finalize_llm_segment()
        self.status = status
        self.error = error
        total_ms = _mono_ms(self.started_mono)
        return self._build_record(total_ms)

    def _build_record(self, total_ms: float) -> dict[str, Any]:
        enriched = enrich_events(self.events)
        llm_events = [e for e in enriched if e["type"] == "llm"]
        tool_events = [e for e in enriched if e["type"] == "tool"]
        rag_events = [e for e in tool_events if e.get("category_type") == "mcp-server-rag"]

        llm_total = round(sum(e["duration_ms"] for e in llm_events), 1)
        tool_total = round(sum(e["duration_ms"] for e in tool_events), 1)
        rag_total = round(sum(e["duration_ms"] for e in rag_events), 1)
        accounted = round(llm_total + tool_total, 1)
        other_ms = round(max(0.0, total_ms - accounted), 1)

        return {
            "turn_id": self.turn_id,
            "started_at": self.started_at,
            "status": self.status,
            "error": self.error,
            "meta": dict(self.meta),
            "total_ms": total_ms,
            "summary": {
                "llm_total_ms": llm_total,
                "llm_rounds": len(llm_events),
                "tool_total_ms": tool_total,
                "tool_calls": len(tool_events),
                "rag_total_ms": rag_total,
                "rag_calls": len(rag_events),
                "other_ms": other_ms,
            },
            "events": enriched,
        }


def init_timing_history() -> None:
    import streamlit as st

    if "timing_history" not in st.session_state:
        st.session_state.timing_history = []
    if "timing_current" not in st.session_state:
        st.session_state.timing_current = None


def append_timing_record(record: dict[str, Any]) -> None:
    import streamlit as st

    init_timing_history()
    st.session_state.timing_history.append(record)
    st.session_state.timing_current = record


def clear_timing_history() -> None:
    import streamlit as st

    st.session_state.timing_history = []
    st.session_state.timing_current = None


def _format_timeline_table(events: list[dict[str, Any]]) -> list[str]:
    if not events:
        return []
    lines = [
        "**时间线**",
        "",
        "| 序号 | 具体类型 | 具体名称 | 使用目的 | 耗时 |",
        "|------|----------|----------|----------|------|",
    ]
    for idx, e in enumerate(events, start=1):
        lines.append(
            f"| {idx} "
            f"| {e.get('category_type', '—')} "
            f"| {e.get('display_name', e.get('name', '—'))} "
            f"| {e.get('purpose', '—')} "
            f"| {e.get('duration_ms')} ms |"
        )
    lines.append("")
    return lines


def format_turn_table(record: dict[str, Any]) -> str:
    """单回合报告（Markdown）。"""
    meta = record.get("meta") or {}
    lines = [
        f"### 回合 {record.get('turn_id')}（{record.get('started_at')}）",
        "",
        f"- **状态**：{record.get('status')}",
        f"- **总耗时**：{record.get('total_ms')} ms",
    ]
    preview = meta.get("user_query_preview")
    if preview:
        lines.append(f"- **输入摘要**：{preview}")
    lines.append("")

    if record.get("error"):
        lines.append(f"- **错误**：{record['error']}")
        lines.append("")

    s = record.get("summary") or {}
    lines.extend(
        [
            "**汇总**",
            "",
            "| 类别 | 耗时 | 次数 |",
            "|------|------|------|",
            f"| LLM 推理 | {s.get('llm_total_ms', 0)} ms | {s.get('llm_rounds', 0)} 轮 |",
            f"| RAG 检索 | {s.get('rag_total_ms', 0)} ms | {s.get('rag_calls', 0)} 次 |",
            f"| MCP/工具（合计） | {s.get('tool_total_ms', 0)} ms | {s.get('tool_calls', 0)} 次 |",
            f"| 其他 | {s.get('other_ms', 0)} ms | 编排/连接等 |",
            "",
        ]
    )
    lines.extend(_format_timeline_table(record.get("events") or []))
    return "\n".join(lines)


def format_timing_report_markdown(
    history: list[dict[str, Any]],
    *,
    title: str = "Agent 耗时测试记录",
) -> str:
    """生成完整测试条例 Markdown（可多回合）。"""
    lines = [
        f"# {title}",
        "",
        f"- **生成时间**：{_now_iso()}",
        f"- **回合数**：{len(history)}",
        "",
        "---",
        "",
    ]
    if not history:
        lines.append("（暂无记录，请先完成至少一次对话。）")
        return "\n".join(lines)

    total_all = round(sum(r.get("total_ms", 0) for r in history), 1)
    llm_all = round(
        sum((r.get("summary") or {}).get("llm_total_ms", 0) for r in history), 1
    )
    rag_all = round(
        sum((r.get("summary") or {}).get("rag_total_ms", 0) for r in history), 1
    )
    tool_all = round(
        sum((r.get("summary") or {}).get("tool_total_ms", 0) for r in history), 1
    )
    rag_calls_all = sum((r.get("summary") or {}).get("rag_calls", 0) for r in history)

    lines.extend(
        [
            "## 全局汇总",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 全部回合总耗时 | {total_all} ms |",
            f"| LLM 合计 | {llm_all} ms |",
            f"| RAG 检索合计 | {rag_all} ms（{rag_calls_all} 次） |",
            f"| MCP/工具合计 | {tool_all} ms |",
            f"| LLM 占比 | {round(llm_all / total_all * 100, 1) if total_all else 0}% |",
            f"| RAG 占比 | {round(rag_all / total_all * 100, 1) if total_all else 0}% |",
            "",
            "---",
            "",
            "## 分回合明细",
            "",
        ]
    )

    for record in history:
        lines.append(format_turn_table(record))
        lines.append("---")
        lines.append("")

    lines.extend(
        [
            "## 测试填写建议",
            "",
            "| 测试项 | 填写说明 |",
            "|--------|----------|",
            "| 测试场景 | 如：云南 5 日游 / 西安 1 日游 |",
            "| 总耗时 | 见全局汇总 |",
            "| RAG 耗时 | 见汇总「RAG 检索」及时间线中 mcp-server-rag 行 |",
            "| 最慢环节 | 见各回合时间线耗时列 |",
            "| LLM 轮次 | 见汇总 LLM 推理次数 |",
            "| 是否成功 | status 是否为 ok |",
            "",
        ]
    )
    return "\n".join(lines)


def format_timing_report_json(history: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "generated_at": _now_iso(),
            "turn_count": len(history),
            "records": history,
        },
        ensure_ascii=False,
        indent=2,
    )
