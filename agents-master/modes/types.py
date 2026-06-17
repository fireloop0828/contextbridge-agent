"""多模式抽象：元信息与 branding。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ModeBranding:
    page_title: str
    page_icon: str
    title: str
    subtitle: str


@runtime_checkable
class AgentMode(Protocol):
    """模式包最小接口（设计层）；强流程模式可额外导出编排函数。"""

    id: str
    label: str
    order: int
    description: str

    def branding(self) -> ModeBranding: ...

    def chat_placeholder(self) -> str: ...

    def build_system_prompt(self) -> str: ...

    def detect_intent(self, text: str) -> bool: ...

    def on_enter(self, *, reset: bool = False) -> bool:
        """进入模式；返回是否需要重建 Agent（Prompt 变化）。"""
        ...

    def on_exit(self) -> bool:
        """退出模式；返回是否需要重建 Agent。"""
        ...
