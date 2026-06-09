"""MCP 工具返回值截断，降低 ReAct 循环中的 context token。"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool


def truncate_tool_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return (
        f"{text[:max_chars]}\n\n"
        f"...[工具输出已截断，省略约 {omitted} 字符；请基于以上内容继续，勿重复调用同一工具]"
    )


def truncate_tool_result(result: Any, max_chars: int) -> Any:
    if isinstance(result, str):
        return truncate_tool_text(result, max_chars)
    if isinstance(result, (dict, list)):
        serialized = json.dumps(result, ensure_ascii=False)
        if len(serialized) <= max_chars:
            return result
        return truncate_tool_text(serialized, max_chars)
    text = str(result)
    if len(text) <= max_chars:
        return result
    return truncate_tool_text(text, max_chars)


def wrap_tools_with_output_limit(tools: list[BaseTool], max_chars: int) -> list[BaseTool]:
    """为工具列表包装输出截断（原地替换 coroutine/func）。"""
    wrapped: list[BaseTool] = []
    for tool in tools:
        wrapped.append(_wrap_single_tool(tool, max_chars))
    return wrapped


def _wrap_single_tool(tool: BaseTool, max_chars: int) -> BaseTool:
    if getattr(tool, "coroutine", None):

        async def acoroutine(*args, _orig=tool.coroutine, **kwargs):
            result = await _orig(*args, **kwargs)
            return truncate_tool_result(result, max_chars)

        return tool.copy(update={"coroutine": acoroutine})

    if getattr(tool, "func", None):

        def func(*args, _orig=tool.func, **kwargs):
            result = _orig(*args, **kwargs)
            return truncate_tool_result(result, max_chars)

        return tool.copy(update={"func": func})

    return tool
