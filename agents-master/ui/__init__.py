"""Streamlit UI 组件（侧边栏、聊天主区）。"""

from __future__ import annotations

import sys
from types import ModuleType


def get_app_module() -> ModuleType:
    """
    返回 Streamlit 主脚本模块。

    `streamlit run app.py` 时实际执行的是 __main__，若再 `import app` 会
    完整重跑 app.py 一遍，导致 UI 组件 key 重复。
    """
    for name in ("__main__", "app"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "reconnect_agent"):
            return mod
    import app as main

    return main
