"""LangSmith 追踪配置管理：读写 .env、应用环境变量、清理 SDK 缓存。

LangChain / LangGraph 通过 langsmith SDK 自动上报 trace，只需在进程内提供：
    LANGSMITH_TRACING_V2=true
    LANGSMITH_API_KEY=lsv2_pt_xxx
    LANGSMITH_PROJECT=<项目名>
    LANGSMITH_WORKSPACE_ID=<org-scoped Key 必填>
    LANGSMITH_ENDPOINT=<可选，私有化部署时填写>
用户可在侧边栏填写，保存后写入 .env 并立即生效。

注意：langsmith SDK 的 get_env_var 按 ("LANGSMITH", "LANGCHAIN") 顺序读取，
即 LANGSMITH_* 前缀【优先于】LANGCHAIN_*。本模块以 LANGSMITH_* 为主变量名，
同时兼容旧的 LANGCHAIN_* 变量。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

# 模块所在目录 = agents-master/
_BASE_DIR = Path(__file__).resolve().parent
_ENV_FILE = _BASE_DIR / ".env"

# 追踪相关环境变量。
# langsmith SDK 的 get_env_var 按 ("LANGSMITH", "LANGCHAIN") 顺序读取，
# 因此 LANGSMITH_* 前缀优先；本模块以 LANGSMITH_* 为主变量名，LANGCHAIN_* 作为兼容回退。
TRACING_ENABLED_VAR = "LANGSMITH_TRACING_V2"
API_KEY_VARS = ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")
PROJECT_VARS = ("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT")
ENDPOINT_VARS = ("LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT")
WORKSPACE_ID_VARS = ("LANGSMITH_WORKSPACE_ID", "LANGCHAIN_WORKSPACE_ID")

# 保存配置时，需要清掉旧的 LANGCHAIN_* 残留，避免 UI 状态和 SDK 读到不一致的值。
# （SDK 优先读 LANGSMITH_*，所以旧 LANGCHAIN_* 不会遮蔽新值，但留着会造成 .env 脏乱。）
_STALE_LANGCHAIN_VARS = (
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
    "LANGCHAIN_ENDPOINT",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_WORKSPACE_ID",
)

DEFAULT_PROJECT = "agents-master"
DEFAULT_ENDPOINT = "https://api.smith.langchain.com"


def _key_type(api_key: str) -> str:
    """根据 Key 前缀判断类型：'service' 或 'personal'。"""
    if (api_key or "").strip().lower().startswith("lsv2_sk_"):
        return "service"
    return "personal"


def _read_env_value(vars_: tuple[str, ...], default: str = "") -> str:
    """按 vars_ 元组顺序读取环境变量（LANGSMITH_* 优先于 LANGCHAIN_*）。"""
    for v in vars_:
        val = os.environ.get(v, "").strip()
        if val:
            return val
    return default


def _remove_env_keys(path: Path, keys: tuple[str, ...]) -> None:
    """从 .env 文件中删除指定 key 的行（python-dotenv 没有删除 API，直接过滤文本）。"""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return
    out = [
        ln
        for ln in lines
        if not any(ln.strip().startswith(f"{k}=") for k in keys)
    ]
    if len(out) != len(lines):
        path.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_langsmith_env(*, force_tracing_default: bool = True) -> None:
    """
    应用 LangSmith 环境变量（Streamlit 每次 rerun 都会执行 load_dotenv，
    本函数确保追踪开关等有稳定默认值，避免残留脏配置）。
    """
    api_key = _read_env_value(API_KEY_VARS)
    if not api_key:
        os.environ[TRACING_ENABLED_VAR] = "false"
        return

    os.environ[TRACING_ENABLED_VAR] = os.environ.get(
        TRACING_ENABLED_VAR, "false" if force_tracing_default else ""
    ).strip() or ("false" if force_tracing_default else "")

    if not os.environ.get(PROJECT_VARS[0]):
        os.environ[PROJECT_VARS[0]] = _read_env_value(
            PROJECT_VARS, DEFAULT_PROJECT
        )
    if not os.environ.get(ENDPOINT_VARS[0]):
        os.environ[ENDPOINT_VARS[0]] = _read_env_value(
            ENDPOINT_VARS, DEFAULT_ENDPOINT
        )
    # org-scoped Key 必须带 workspace 上下文，否则 LangSmith 返回 403
    ws = _read_env_value(WORKSPACE_ID_VARS)
    if ws and not os.environ.get(WORKSPACE_ID_VARS[0]):
        os.environ[WORKSPACE_ID_VARS[0]] = ws


def reset_langsmith_client_cache() -> None:
    """LangSmith / langchain-core 对 client 与项目名/开关都有模块级 lru_cache，
    改配置后需清理才能在当前进程内立即生效（否则 trace 会继续进旧项目或不上传）。
    不同版本内部结构不同，全部兜底 try/except。"""
    # 项目名、开关等 lru_cache：保存配置后必须清，否则 get_tracer_project() /
    # tracing_is_enabled() 仍返回进程早期缓存的旧值（如 "default" / False）
    try:
        from langsmith.utils import get_env_var, get_tracer_project

        for _fn in (get_env_var, get_tracer_project):
            if hasattr(_fn, "cache_clear"):
                _fn.cache_clear()
    except Exception:
        pass
    try:
        from langchain_core.tracers import langchain as _lc_tracers

        if hasattr(_lc_tracers, "_get_client"):
            _lc_tracers._get_client.cache_clear()
    except Exception:
        pass
    try:
        import langsmith.utils.client as _ls_utils

        if hasattr(_ls_utils, "_LANGSMITH_CLIENT"):
            _ls_utils._LANGSMITH_CLIENT = None
    except Exception:
        pass
    try:
        from langsmith.client import Client as _Client

        if hasattr(_Client, "_singleton"):
            _Client._singleton = None
    except Exception:
        pass


def save_langsmith_settings(
    *,
    api_key: str,
    project: str,
    tracing: bool,
    endpoint: str = DEFAULT_ENDPOINT,
    workspace_id: str = "",
) -> dict[str, str]:
    """把 LangSmith 配置写入 .env 并应用到当前进程。

    workspace_id：
      - Service Key（lsv2_sk_）是 org-scoped，LangSmith 要求显式指定 workspace，
        通过请求头 X-Tenant-Id 发送，否则 403。
      - Personal Access Token（lsv2_pt_）已内嵌 Default Workspace，不需要也不应
        设置 workspace_id；设置后反而可能与服务端解析冲突导致 403。

    返回 {key: 写入后的值} 供 UI 展示。
    """
    api_key = (api_key or "").strip()
    project = (project or "").strip() or DEFAULT_PROJECT
    endpoint = (endpoint or "").strip() or DEFAULT_ENDPOINT
    workspace_id = (workspace_id or "").strip()
    tracing_v = "true" if tracing else "false"

    if not api_key:
        tracing_v = "false"

    # Personal Access Token 已内嵌 Default Workspace，不需要 workspace_id
    if _key_type(api_key) == "personal":
        workspace_id = ""

    _ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 清掉旧的 LANGCHAIN_* 残留，保持 .env 干净且与 SDK 优先级一致
    _remove_env_keys(_ENV_FILE, _STALE_LANGCHAIN_VARS)
    for key, value in (
        (TRACING_ENABLED_VAR, tracing_v),
        (API_KEY_VARS[0], api_key),
        (PROJECT_VARS[0], project),
        (ENDPOINT_VARS[0], endpoint),
        (WORKSPACE_ID_VARS[0], workspace_id),
    ):
        set_key(str(_ENV_FILE), key, value, quote_mode="never")

    # 应用进当前进程环境
    os.environ[TRACING_ENABLED_VAR] = tracing_v
    if api_key:
        os.environ[API_KEY_VARS[0]] = api_key
        os.environ.pop(API_KEY_VARS[1], None)
        os.environ[PROJECT_VARS[0]] = project
        os.environ[ENDPOINT_VARS[0]] = endpoint
        if workspace_id:
            os.environ[WORKSPACE_ID_VARS[0]] = workspace_id
        else:
            os.environ.pop(WORKSPACE_ID_VARS[0], None)
        os.environ.pop(WORKSPACE_ID_VARS[1], None)
        # 重新读取 .env 以保持 load_dotenv 语义一致（.env 里现在是 LANGSMITH_* 主变量）
        load_dotenv(_ENV_FILE, override=True)
        reset_langsmith_client_cache()
    else:
        os.environ.pop(API_KEY_VARS[0], None)
        os.environ.pop(API_KEY_VARS[1], None)
        os.environ[TRACING_ENABLED_VAR] = "false"

    return {
        "api_key": api_key,
        "project": project,
        "tracing": tracing_v,
        "endpoint": endpoint,
        "workspace_id": workspace_id,
    }


def langsmith_status() -> dict[str, object]:
    """当前 LangSmith 配置状态（供 UI 展示）。"""
    api_key = _read_env_value(API_KEY_VARS)
    key_type = _key_type(api_key)
    workspace_id = _read_env_value(WORKSPACE_ID_VARS)
    # 如果当前保存的是 PAT 但 .env 里还残留 workspace_id，返回空，避免 UI 误导
    if key_type == "personal":
        workspace_id = ""
    return {
        "configured": bool(api_key),
        "tracing": os.environ.get(TRACING_ENABLED_VAR, "").lower() == "true",
        "api_key": api_key,
        "project": _read_env_value(PROJECT_VARS, DEFAULT_PROJECT),
        "endpoint": _read_env_value(ENDPOINT_VARS, DEFAULT_ENDPOINT),
        "workspace_id": workspace_id,
        "key_type": key_type,
    }
