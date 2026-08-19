"""中间件骨架：TurnContext / TurnMiddleware / TurnOrchestrator。

本模块只依赖标准库，不依赖 Streamlit / LangGraph，可独立运行验证。

当前为 V0 骨架：不注入现有流程，仅提供协议与空链可运行能力。
后续按 docs/project-design/中间件化改造方案.md 逐步迁移 ui/chat.py
的横切逻辑（记忆注入/抽取、错误处理、计时、导出、会话落盘等）。
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TurnContext:
    """一轮 Agent 请求的上下文，贯穿 before/after/error 钩子。

    骨架阶段仅承载核心字段；timing / travel_turn / travel_after 等
    在 V1 按需以显式字段或 extra 扩展。
    """

    user_query: str = ""
    """原始用户输入。"""
    agent_query: str = ""
    """注入后传给 Agent 的 query（before 链可改写）。"""
    resp: dict[str, Any] | None = None
    """Agent 调用返回（invoke 产生）。"""
    final_text: str = ""
    """最终文本回复。"""
    final_tool: str = ""
    """最终工具调用信息。"""
    error: str | None = None
    """用户可读错误消息（on_error 链归一化后）。"""
    error_detail: str | None = None
    """技术排障详情（traceback / repr）。"""
    mode_id: str = ""
    """当前对话模式。"""
    phase_this_turn: str | None = None
    """旅行模式本回合 phase。"""
    export_paths: list[str] = field(default_factory=list)
    """本回合生成/发现的导出文件路径。"""
    aborted: bool = False
    """before 链可置 True：跳过 invoke 与剩余 before。"""
    extra: dict[str, Any] = field(default_factory=dict)
    """中间件间附加数据（避免频繁改字段）。"""


class TurnMiddleware(ABC):
    """一轮请求中间件基类，所有钩子默认空实现。"""

    name: str = "unnamed"
    """唯一名，用于排序 / 启停。"""
    order: int = 100
    """链执行顺序（升序；before 正序、after/on_error 逆序）。"""

    def before_agent(self, ctx: TurnContext) -> None:
        """Agent 调用前：改写 agent_query、切换 thread、预取等。"""

    def after_agent(self, ctx: TurnContext) -> None:
        """Agent 调用后：记忆抽取、导出、落盘、历史记录等。"""

    def on_error(self, ctx: TurnContext, exc: Exception) -> None:
        """异常时：错误归一化、降级、告警。"""

    def on_agent_built(self, build_ctx: Any) -> None:
        """（预留）Agent 构建 / 重建钩子。"""


class TurnOrchestrator:
    """管理中间件链并驱动一轮请求。

    invoke 可注入自定义 Agent 调用（如原 process_query）；默认占位实现
    返回成功空结果，便于骨架阶段独立跑通。
    """

    def __init__(
        self,
        chain: list[TurnMiddleware] | None = None,
        invoke: Callable[
            [TurnContext], tuple[dict[str, Any], str, str]
        ] | None = None,
    ) -> None:
        self._chain: list[TurnMiddleware] = list(chain or [])
        self._invoke = invoke or self._default_invoke

    @staticmethod
    def _default_invoke(
        ctx: TurnContext,
    ) -> tuple[dict[str, Any], str, str]:
        """骨架阶段的默认 invoke：不调 Agent，返回占位成功。"""
        return ({"ok": True}, "", "")

    # ---- 链管理 ----

    def register(self, mw: TurnMiddleware) -> "TurnOrchestrator":
        """追加中间件到链尾。"""
        self._chain.append(mw)
        return self

    def unregister(self, name: str) -> bool:
        """按名移除中间件；返回是否实际移除。"""
        before = len(self._chain)
        self._chain = [m for m in self._chain if m.name != name]
        return len(self._chain) < before

    def reorder(self, names: list[str]) -> None:
        """显式指定链顺序；names 必须与已注册集合一致。"""
        by_name = {m.name: m for m in self._chain}
        if set(names) != set(by_name):
            raise ValueError(
                f"names 与已注册中间件不一致，已注册：{sorted(by_name)}"
            )
        self._chain = [by_name[n] for n in names]

    def sorted_chain(self) -> list[TurnMiddleware]:
        return sorted(self._chain, key=lambda m: m.order)

    # ---- 执行 ----

    def run(self, user_query: str, **kwargs: Any) -> TurnContext:
        """同步入口：before 正序 → invoke → on_error（逆序）→ after（逆序）。

        额外 kwargs 会写入 ctx.extra，供中间件读取。
        """
        ctx = TurnContext(user_query=user_query)
        ctx.extra.update(kwargs)
        chain = self.sorted_chain()

        for mw in chain:
            if ctx.aborted:
                break
            mw.before_agent(ctx)

        if not ctx.aborted:
            try:
                ctx.resp, ctx.final_text, ctx.final_tool = self._invoke(ctx)
            except Exception as exc:
                ctx.error = str(exc)
                ctx.error_detail = repr(exc)
                for mw in reversed(chain):
                    mw.on_error(ctx, exc)

        for mw in reversed(chain):
            mw.after_agent(ctx)

        return ctx

    async def arun(self, user_query: str, **kwargs: Any) -> TurnContext:
        """异步入口（预留）：当前复用同步逻辑，Agent 接入时再改造。"""
        return self.run(user_query, **kwargs)
