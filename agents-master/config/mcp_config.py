"""MCP 配置加载、持久化与运行时解析。"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

import streamlit as st

from config.paths import APP_DIR

CONFIG_FILE_PATH = os.path.join(APP_DIR, "config.json")

_DEFAULT_MCP_CONFIG = {
    "get_current_time": {
        "command": "python",
        "args": ["./mcp_server_time.py"],
        "transport": "stdio",
    }
}


def load_config_from_json() -> dict:
    """
    从 config.json 加载 MCP 工具配置。
    若文件不存在则创建并写入默认配置。
    """
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, encoding="utf-8") as f:
                return json.load(f)
        save_config_to_json(_DEFAULT_MCP_CONFIG)
        return dict(_DEFAULT_MCP_CONFIG)
    except Exception as e:
        st.error(f"加载配置文件失败：{str(e)}")
        return dict(_DEFAULT_MCP_CONFIG)


def save_config_to_json(config: dict) -> bool:
    """将配置写入 config.json。"""
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"保存配置文件失败：{str(e)}")
        return False


def _resolve_rag_server_python(cwd: str) -> str:
    """优先使用 rag-server 独立虚拟环境中的 Python。"""
    for rel in (".venv/bin/python", ".venv/bin/python3", "venv/bin/python"):
        candidate = os.path.join(cwd, rel)
        if os.path.isfile(candidate):
            return candidate
    return sys.executable


def _resolve_amap_maps_command() -> str | None:
    """
    解析高德 MCP 可执行文件，避免 npx -y 每次初始化耗时 ~15s。

    优先级：项目 node_modules/.bin → npx 历史缓存。
    """
    candidates = [
        os.path.join(APP_DIR, "node_modules", ".bin", "mcp-amap"),
    ]
    candidates.extend(
        sorted(
            glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/.bin/mcp-amap")),
            reverse=True,
        )
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def mcp_config_signature(config: dict) -> str:
    """用于判断 MCP 配置是否变化（resolve 之后）。"""
    return json.dumps(config, sort_keys=True, ensure_ascii=False)


def configs_equal(a: dict, b: dict) -> bool:
    return mcp_config_signature(a) == mcp_config_signature(b)


def _interpolate_env_vars(value: str) -> str:
    """将形如 ${VAR_NAME} 的占位符替换为环境变量值。"""
    if not isinstance(value, str) or "${" not in value:
        return value

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.environ.get(var, match.group(0))

    return re.sub(r"\$\{([A-Z0-9_]+)\}", repl, value)


def resolve_mcp_config(config: dict) -> dict:
    """
    解析 MCP 配置：
    - python 命令 → 当前解释器或 rag-server 虚拟环境解释器
    - 相对 cwd → 绝对路径
    """
    resolved = {}
    for name, cfg in config.items():
        cfg = dict(cfg)
        cwd = cfg.get("cwd")
        if cwd:
            if not os.path.isabs(cwd):
                cwd = os.path.normpath(os.path.join(APP_DIR, cwd))
            cfg["cwd"] = cwd

        is_rag_server = (
            name == "rag-server"
            or (cwd and os.path.basename(cwd) == "rag-server")
            or cfg.get("args") == ["-m", "src.mcp_server.server"]
        )

        if cfg.get("command") in ("python", "python3", "python3.12"):
            if is_rag_server and cwd:
                cfg["command"] = _resolve_rag_server_python(cwd)
            else:
                cfg["command"] = sys.executable

        if isinstance(cfg.get("args"), list):
            cfg["args"] = [
                _interpolate_env_vars(x) if isinstance(x, str) else x
                for x in cfg["args"]
            ]

        env = cfg.get("env")
        if env is None:
            env = {}
        elif not isinstance(env, dict):
            env = {}

        env = {
            k: (_interpolate_env_vars(v) if isinstance(v, str) else v)
            for k, v in env.items()
        }

        is_amap_server = (
            name == "amap-maps"
            or cfg.get("command") in ("mcp-amap", "npx")
            or (
                cfg.get("command") == "npx"
                and "@amap/amap-maps-mcp-server" in (cfg.get("args") or [])
            )
        )
        if is_amap_server:
            use_npx = (
                cfg.get("command") == "npx"
                and "@amap/amap-maps-mcp-server" in (cfg.get("args") or [])
            )
            if not use_npx:
                amap_bin = _resolve_amap_maps_command()
                if amap_bin:
                    cfg["command"] = amap_bin
                    cfg["args"] = []
                elif cfg.get("command") in ("mcp-amap", "amap-maps-mcp-server"):
                    cfg["command"] = "npx"
                    cfg["args"] = ["-y", "@amap/amap-maps-mcp-server"]
            if "AMAP_MAPS_API_KEY" not in env:
                amap_key = os.environ.get("AMAP_MAPS_API_KEY")
                if amap_key:
                    env["AMAP_MAPS_API_KEY"] = amap_key

        cfg["env"] = env
        resolved[name] = cfg
    return resolved
