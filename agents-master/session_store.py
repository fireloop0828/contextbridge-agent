"""会话持久化：结构化快照、归档与恢复（P0/P1）。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from modes.travel import state_machine as tm

SESSION_VERSION = 1
MAX_HISTORY_PERSIST = 40
USER_PREF_FIELDS = ("default_budget", "default_transport", "default_companions")

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sessions")
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, "archives")
LATEST_PATH = os.path.join(SESSIONS_DIR, "latest.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    os.makedirs(ARCHIVES_DIR, exist_ok=True)


def empty_user_preferences() -> dict[str, str]:
    return {field: "" for field in USER_PREF_FIELDS}


def init_session_store_state() -> None:
    """初始化用户偏好等与持久化相关的 session 键。"""
    import streamlit as st

    if "user_preferences" not in st.session_state:
        st.session_state.user_preferences = empty_user_preferences()
    if "_session_restore_checked" not in st.session_state:
        st.session_state._session_restore_checked = False


def _serialize_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in history[-MAX_HISTORY_PERSIST:]:
        item: dict[str, Any] = {"role": msg.get("role"), "content": msg.get("content", "")}
        if msg.get("exports"):
            item["exports"] = msg["exports"]
        if msg.get("travel_facts"):
            item["travel_facts"] = msg["travel_facts"]
        out.append(item)
    return out


def collect_snapshot(*, archived: bool = False, label: str = "") -> dict[str, Any]:
    """从 st.session_state 收集可持久化快照。"""
    import streamlit as st

    from modes.travel.tool_memory import get_cached_rag_collections

    init_session_store_state()
    _ensure_dirs()

    travel_block: dict[str, Any] | None = None
    if st.session_state.get("app_mode") == tm.APP_MODE_TRAVEL:
        travel_facts = st.session_state.get("travel_facts")
        travel_block = {
            "phase": st.session_state.get("travel_phase", tm.PHASE_INTAKE_1),
            "intake": st.session_state.get("travel_intake") or tm.empty_intake(),
            "intake_user_turns": st.session_state.get("travel_intake_user_turns", 0),
            "intake_round": st.session_state.get("travel_intake_round", 0),
            "last_travel_plan_md": st.session_state.get("last_travel_plan_md", ""),
            "last_export_path": st.session_state.get("last_export_path", ""),
            "tool_memory": list(st.session_state.get("travel_tool_memory") or []),
            "rag_collections_cache": get_cached_rag_collections(),
            "must_visit_confirmed": bool(st.session_state.get("must_visit_confirmed")),
            "poi_for_destination": st.session_state.get("poi_for_destination"),
            "travel_facts": travel_facts if isinstance(travel_facts, dict) else None,
        }

    return {
        "version": SESSION_VERSION,
        "saved_at": _now_iso(),
        "archived": archived,
        "label": label.strip(),
        "app_mode": st.session_state.get("app_mode", tm.APP_MODE_GENERAL),
        "thread_id": st.session_state.get("thread_id"),
        "history": _serialize_history(st.session_state.get("history") or []),
        "exported_files": list(st.session_state.get("exported_files") or []),
        "user_preferences": dict(st.session_state.get("user_preferences") or empty_user_preferences()),
        "travel": travel_block,
    }


def _write_json(path: str, payload: dict[str, Any]) -> None:
    _ensure_dirs()
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_latest_autosave() -> None:
    """自动保存当前会话到 latest.json（不含 archived 标记）。"""
    if not _has_meaningful_session():
        return
    payload = collect_snapshot(archived=False)
    _write_json(LATEST_PATH, payload)


def _has_meaningful_session() -> bool:
    import streamlit as st

    if st.session_state.get("history"):
        return True
    if st.session_state.get("app_mode") == tm.APP_MODE_TRAVEL:
        intake = st.session_state.get("travel_intake") or tm.empty_intake()
        if (intake.get("destination") or "").strip():
            return True
        if st.session_state.get("travel_tool_memory"):
            return True
    return False


def clear_persisted_latest() -> None:
    if os.path.isfile(LATEST_PATH):
        try:
            os.remove(LATEST_PATH)
        except OSError:
            pass


def _run_archive_memory_pipeline(payload: dict[str, Any], archive_path: str) -> None:
    """后台执行完整记忆流水线（含 LLM 判断与摘要）。"""
    try:
        from memory_pipeline import run_memory_pipeline

        run_memory_pipeline(
            payload,
            trigger="archive",
            archive_path=archive_path,
            skip_llm=False,
        )
    except Exception:
        pass


def archive_current_session(*, label: str = "", fast: bool = False) -> str | None:
    """归档当前会话到 archives/，返回归档文件路径。

    fast=True 时先写盘并清空 latest（UI 不阻塞），再在后台线程跑完整 LLM 记忆流水线。
    """
    if not _has_meaningful_session():
        return None
    _ensure_dirs()
    payload = collect_snapshot(archived=True, label=label)
    if not label:
        label = _default_archive_label(payload)
        payload["label"] = label
    safe = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(ARCHIVES_DIR, f"{safe}.json")
    _write_json(path, payload)
    clear_persisted_latest()
    if fast:
        import threading

        threading.Thread(
            target=_run_archive_memory_pipeline,
            args=(dict(payload), path),
            daemon=True,
        ).start()
    else:
        _run_archive_memory_pipeline(payload, path)
    return path


def _default_archive_label(payload: dict[str, Any]) -> str:
    travel = payload.get("travel") or {}
    intake = travel.get("intake") or {}
    dest = (intake.get("destination") or "").strip()
    if dest:
        return f"{dest} 行程"
    mode = payload.get("app_mode", tm.APP_MODE_GENERAL)
    if mode == tm.APP_MODE_TRAVEL:
        return "旅行规划会话"
    return "通用对话"


def load_snapshot_from_file(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def load_latest_snapshot() -> dict[str, Any] | None:
    return load_snapshot_from_file(LATEST_PATH)


def has_restorable_latest() -> bool:
    data = load_latest_snapshot()
    if not data:
        return False
    if data.get("archived"):
        return False
    return bool(data.get("history") or data.get("travel"))


def apply_snapshot(snapshot: dict[str, Any]) -> None:
    """将快照恢复到 st.session_state。"""
    import streamlit as st

    from modes.travel.tool_memory import init_travel_tool_memory
    from modes.travel.facts import init_travel_facts_state, set_travel_facts

    init_session_store_state()
    tm.init_travel_state()
    init_travel_tool_memory()
    init_travel_facts_state()

    st.session_state.app_mode = snapshot.get("app_mode", tm.APP_MODE_GENERAL)
    st.session_state.agent_prompt_mode = st.session_state.app_mode
    st.session_state.thread_id = snapshot.get("thread_id") or __import__(
        "utils", fromlist=["random_uuid"]
    ).random_uuid()
    st.session_state.history = list(snapshot.get("history") or [])
    st.session_state.exported_files = list(snapshot.get("exported_files") or [])
    prefs = snapshot.get("user_preferences") or {}
    st.session_state.user_preferences = {
        **empty_user_preferences(),
        **{k: str(v or "") for k, v in prefs.items() if k in USER_PREF_FIELDS},
    }

    travel = snapshot.get("travel")
    if travel and st.session_state.app_mode == tm.APP_MODE_TRAVEL:
        st.session_state.travel_phase = travel.get("phase", tm.PHASE_INTAKE_1)
        st.session_state.travel_intake = travel.get("intake") or tm.empty_intake()
        st.session_state.travel_intake_user_turns = int(travel.get("intake_user_turns") or 0)
        st.session_state.travel_intake_round = int(travel.get("intake_round") or 0)
        st.session_state.last_travel_plan_md = travel.get("last_travel_plan_md") or ""
        st.session_state.last_export_path = travel.get("last_export_path") or ""
        st.session_state.travel_tool_memory = list(travel.get("tool_memory") or [])
        st.session_state.rag_collections_cache = list(travel.get("rag_collections_cache") or [])
        st.session_state.must_visit_confirmed = bool(travel.get("must_visit_confirmed"))
        st.session_state.poi_for_destination = travel.get("poi_for_destination")
        tf = travel.get("travel_facts")
        set_travel_facts(tf if isinstance(tf, dict) else None)
    elif st.session_state.app_mode == tm.APP_MODE_TRAVEL:
        tm.reset_travel_session()


def list_archives(*, limit: int = 8) -> list[dict[str, Any]]:
    _ensure_dirs()
    files = [
        os.path.join(ARCHIVES_DIR, name)
        for name in os.listdir(ARCHIVES_DIR)
        if name.endswith(".json")
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[:limit]:
        data = load_snapshot_from_file(path)
        if not data:
            continue
        out.append(
            {
                "path": path,
                "label": data.get("label") or os.path.basename(path),
                "saved_at": data.get("saved_at", ""),
                "app_mode": data.get("app_mode", tm.APP_MODE_GENERAL),
            }
        )
    return out


def start_blank_session(*, keep_preferences: bool = True) -> None:
    """清空当前对话页（保留 app_mode；可选保留用户偏好）。"""
    import streamlit as st

    import timing_log as tlog
    from modes.travel.tool_memory import clear_travel_tool_memory
    from utils import random_uuid

    prefs = dict(st.session_state.get("user_preferences") or empty_user_preferences())
    st.session_state.thread_id = random_uuid()
    st.session_state.history = []
    st.session_state.exported_files = []
    tlog.clear_timing_history()
    if st.session_state.get("app_mode") == tm.APP_MODE_TRAVEL:
        tm.reset_travel_session()
    else:
        clear_travel_tool_memory()
    if keep_preferences:
        st.session_state.user_preferences = prefs
    else:
        st.session_state.user_preferences = empty_user_preferences()


def format_session_state_markdown() -> str:
    """侧边栏「本轮会话状态」：仅展示当前页结构化 state（非长期记忆、非聊天气泡全文）。"""
    import streamlit as st

    from modes.travel.tool_memory import format_tool_memory_for_context

    app_mode = st.session_state.get("app_mode", tm.APP_MODE_GENERAL)
    history = st.session_state.get("history") or []
    user_turns = sum(1 for m in history if m.get("role") == "user")

    if app_mode != tm.APP_MODE_TRAVEL:
        return (
            f"**模式**：通用对话\n\n"
            f"**本轮**：约 {user_turns} 轮用户发言\n\n"
            "通用模式没有行程需求 / 工具摘要等结构化块。"
            "跨会话画像与摘要见上方「记忆外显」。"
        )

    lines: list[str] = [f"**本轮**：约 {user_turns} 轮用户发言"]
    intake = st.session_state.get("travel_intake") or tm.empty_intake()
    phase = st.session_state.get("travel_phase", tm.PHASE_INTAKE_1)
    lines.append(f"**阶段**：{tm.format_phase_zh(phase)}")
    filled = [
        f"{tm.INTAKE_FIELD_LABELS.get(k, k)}={intake.get(k)}"
        for k in tm.INTAKE_FIELDS
        if tm.is_field_filled(intake.get(k))
    ]
    lines.append("**行程需求**：" + ("；".join(filled) if filled else "（尚无）"))
    missing = tm.compute_missing_fields(intake)
    if missing:
        lines.append("**仍缺**：" + tm.format_missing_fields_zh(missing))

    tool_mem = format_tool_memory_for_context()
    if tool_mem:
        lines.append("**工具结论摘要**：\n```\n" + tool_mem[:1200] + "\n```")
    else:
        lines.append("**工具结论摘要**：（暂无）")

    export_path = st.session_state.get("last_export_path") or ""
    if export_path:
        lines.append(f"**最近导出**：`{export_path}`")
    return "\n\n".join(lines)


def format_memory_panel_markdown() -> str:
    """兼容旧引用。"""
    return format_session_state_markdown()


def describe_latest_for_restore() -> str:
    data = load_latest_snapshot()
    if not data:
        return ""
    travel = data.get("travel") or {}
    intake = travel.get("intake") or {}
    dest = (intake.get("destination") or "").strip()
    phase = travel.get("phase", "")
    saved = (data.get("saved_at") or "")[:19]
    phase_zh = tm.format_phase_zh(phase) if phase else ""
    if dest:
        return f"{dest} · {phase_zh or '旅行'} · 保存于 {saved}"
    if data.get("app_mode") == tm.APP_MODE_TRAVEL:
        return f"旅行规划 · {phase_zh or '进行中'} · 保存于 {saved}"
    turns = len(data.get("history") or [])
    return f"通用对话 · {turns} 条消息 · 保存于 {saved}"
