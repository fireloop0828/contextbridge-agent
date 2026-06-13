"""长期记忆流水线：收集 → 值不值得记 → 分类 → 去重 → 落库。"""

from __future__ import annotations

import json
import re
from typing import Any

import travel_mode as tm
from memory_store import (
    EXPLICIT_REMEMBER_RE,
    PREF_FIELDS,
    STABLE_FACT_FIELDS,
    add_session_summary,
    append_explicit_note,
    append_recent_task,
    contains_sensitive,
    load_profile,
    merge_preferences,
    merge_stable_facts,
    sanitize_text,
    save_profile,
)
from session_store import collect_snapshot

HOME_CITY_RE = re.compile(
    r"(?:住在|居住在|家在|来自|常住)([\u4e00-\u9fff]{2,10}?)(?:市|省|区|县|镇)?",
)
NICKNAME_RE = re.compile(
    r"(?:叫我|称呼我|我是|我叫)([\u4e00-\u9fffA-Za-z]{1,8})",
)
EXPLICIT_NOTE_RE = re.compile(
    r"(?:记住|请记住|帮我记|别忘了)[：:,，]?\s*(.{4,80})",
    re.I,
)


def _history_user_texts(history: list[dict[str, Any]], *, limit: int = 12) -> list[str]:
    texts: list[str] = []
    for msg in history[-limit:]:
        if msg.get("role") == "user":
            c = str(msg.get("content") or "").strip()
            if c:
                texts.append(c)
    return texts


def _history_snippet(history: list[dict[str, Any]], *, max_chars: int = 2000) -> str:
    lines: list[str] = []
    for msg in history[-16:]:
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant" and len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"{role}: {content}")
    blob = "\n".join(lines)
    return blob[:max_chars]


def extract_stable_facts_from_texts(texts: list[str]) -> dict[str, str]:
    facts: dict[str, str] = {}
    joined = "\n".join(texts)
    m = HOME_CITY_RE.search(joined)
    if m:
        facts["home_city"] = m.group(1).strip()
    m = NICKNAME_RE.search(joined)
    if m:
        nick = m.group(1).strip()
        if nick not in ("谁", "什么", "哪里"):
            facts["nickname"] = nick
    return facts


def extract_explicit_notes(texts: list[str]) -> list[str]:
    notes: list[str] = []
    for text in texts:
        if not EXPLICIT_REMEMBER_RE.search(text):
            continue
        m = EXPLICIT_NOTE_RE.search(text)
        if m:
            note = sanitize_text(m.group(1).strip())
            if note and note not in notes:
                notes.append(note)
        elif len(text) <= 120:
            note = sanitize_text(text)
            if note and note not in notes:
                notes.append(note)
    return notes


def _intake_filled_count(intake: dict[str, Any]) -> int:
    return sum(1 for f in tm.INTAKE_FIELDS if tm.is_field_filled(intake.get(f)))


def build_candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """从快照构建待评估候选（A 类）。"""
    candidates: list[dict[str, Any]] = []
    prefs = snapshot.get("user_preferences") or {}
    if any(str(prefs.get(f) or "").strip() for f in PREF_FIELDS):
        candidates.append(
            {
                "kind": "preferences",
                "data": {f: str(prefs.get(f) or "") for f in PREF_FIELDS},
                "reason": "会话含用户偏好",
            }
        )

    travel = snapshot.get("travel") or {}
    intake = travel.get("intake") or {}
    phase = travel.get("phase", "")
    export_path = (travel.get("last_export_path") or "").strip()
    if not export_path:
        for entry in snapshot.get("exported_files") or []:
            if isinstance(entry, dict) and entry.get("path"):
                export_path = str(entry["path"])
                break

    dest = str(intake.get("destination") or "").strip()
    filled = _intake_filled_count(intake)
    if dest and filled >= 2:
        candidates.append(
            {
                "kind": "intake",
                "data": dict(intake),
                "reason": f"旅行 intake 终稿（{filled} 项）",
                "phase": phase,
            }
        )

    if export_path:
        candidates.append(
            {
                "kind": "task",
                "data": {
                    "export_path": export_path,
                    "destination": dest,
                    "app_mode": snapshot.get("app_mode", tm.APP_MODE_GENERAL),
                    "phase": phase,
                },
                "reason": "已生成导出文件",
            }
        )

    user_texts = _history_user_texts(snapshot.get("history") or [])
    facts = extract_stable_facts_from_texts(user_texts)
    if facts:
        candidates.append(
            {"kind": "stable_facts", "data": facts, "reason": "用户自述稳定事实"}
        )

    notes = extract_explicit_notes(user_texts)
    for note in notes:
        candidates.append(
            {"kind": "explicit_note", "data": {"text": note}, "reason": "用户显式记住"}
        )

    return candidates


def rule_worthiness(candidate: dict[str, Any], *, trigger: str) -> bool:
    """规则层：明显值得/不值得；边界交给 LLM。"""
    kind = candidate.get("kind")
    if contains_sensitive(json.dumps(candidate.get("data", {}), ensure_ascii=False)):
        return False

    if kind == "explicit_note":
        return True
    if kind == "preferences":
        data = candidate.get("data") or {}
        return any(str(data.get(f) or "").strip() for f in PREF_FIELDS)
    if kind == "task":
        return bool((candidate.get("data") or {}).get("export_path"))
    if kind == "stable_facts":
        data = candidate.get("data") or {}
        return any(str(data.get(f) or "").strip() for f in STABLE_FACT_FIELDS)
    if kind == "intake":
        data = candidate.get("data") or {}
        dest = str(data.get("destination") or "").strip()
        if not dest:
            return False
        phase = candidate.get("phase", "")
        filled = _intake_filled_count(data)
        if trigger == "travel_export":
            return True
        if phase in (tm.PHASE_GENERATING, tm.PHASE_REVISION):
            return filled >= 3
        if trigger == "archive":
            return filled >= 4
        return filled >= 5
    return False


def _resolve_model_name() -> str | None:
    try:
        import streamlit as st

        name = st.session_state.get("selected_model")
        if name:
            return str(name)
    except Exception:
        pass
    try:
        from config.models import get_available_models

        models = get_available_models()
        return models[0] if models else None
    except Exception:
        return None


def _llm_judge_and_summarize(
    candidates: list[dict[str, Any]],
    history_snippet: str,
    snapshot: dict[str, Any],
) -> tuple[list[str], str]:
    """
    LLM：确认值得写入的 kind 列表 + 会话摘要。
    失败时回退规则 + 模板摘要。
    """
    worthy_kinds = [c["kind"] for c in candidates if rule_worthiness(c, trigger="archive")]
    label = str(snapshot.get("label") or "")
    app_mode = snapshot.get("app_mode", tm.APP_MODE_GENERAL)
    travel = snapshot.get("travel") or {}
    intake = travel.get("intake") or {}
    dest = str(intake.get("destination") or "").strip()
    export_path = (travel.get("last_export_path") or "").strip()
    fallback_summary = _fallback_summary(
        label=label,
        app_mode=app_mode,
        dest=dest,
        export_path=export_path,
        history_len=len(snapshot.get("history") or []),
    )

    model_name = _resolve_model_name()
    if not model_name or not candidates:
        return worthy_kinds, fallback_summary

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from config.models import create_chat_model

        model = create_chat_model(model_name)
        cand_json = json.dumps(
            [
                {
                    "kind": c["kind"],
                    "reason": c.get("reason"),
                    "data": c.get("data"),
                }
                for c in candidates
            ],
            ensure_ascii=False,
        )
        sys = (
            "你是记忆整理助手。根据会话片段与候选事实，判断哪些值得写入用户长期记忆。"
            "不要记录 API Key、密码、证件号、手机号。"
            "仅输出 JSON："
            '{"worthy_kinds":["preferences",...],"session_summary":"一句中文摘要"}'
        )
        user = (
            f"触发：归档会话\n标签：{label}\n模式：{app_mode}\n"
            f"候选：{cand_json}\n\n会话片段：\n{history_snippet[:1500]}"
        )
        resp = model.invoke([SystemMessage(content=sys), HumanMessage(content=user)])
        raw = str(getattr(resp, "content", "") or "").strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        kinds = parsed.get("worthy_kinds")
        summary = sanitize_text(str(parsed.get("session_summary") or ""))
        if isinstance(kinds, list) and kinds:
            worthy_kinds = [str(k) for k in kinds if isinstance(k, str)]
        if not summary or len(summary) < 8:
            summary = fallback_summary
        if contains_sensitive(summary):
            summary = fallback_summary
        return worthy_kinds, summary
    except Exception:
        return worthy_kinds, fallback_summary


def _fallback_summary(
    *,
    label: str,
    app_mode: str,
    dest: str,
    export_path: str,
    history_len: int,
) -> str:
    parts: list[str] = []
    if label:
        parts.append(label)
    elif app_mode == tm.APP_MODE_TRAVEL and dest:
        parts.append(f"{dest} 旅行规划")
    else:
        parts.append("通用对话")
    parts.append(f"共 {history_len} 条消息")
    if export_path:
        parts.append(f"已导出 {export_path}")
    return sanitize_text("，".join(parts)) or "会话归档摘要"


def apply_worthy_candidates(
    profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    worthy_kinds: list[str],
    *,
    saved_at: str,
) -> dict[str, Any]:
    kinds_set = set(worthy_kinds)
    for cand in candidates:
        kind = cand.get("kind")
        if kind not in kinds_set:
            continue
        data = cand.get("data") or {}
        if kind == "preferences":
            profile = merge_preferences(profile, data)
        elif kind == "stable_facts":
            profile = merge_stable_facts(profile, data)
        elif kind == "intake":
            dest = str(data.get("destination") or "").strip()
            if dest:
                profile = append_recent_task(
                    profile,
                    {
                        "saved_at": saved_at,
                        "app_mode": tm.APP_MODE_TRAVEL,
                        "summary": f"{dest} 行程需求（intake）",
                        "destination": dest,
                        "intake": {k: data.get(k) for k in tm.INTAKE_FIELDS if tm.is_field_filled(data.get(k))},
                    },
                )
        elif kind == "task":
            dest = str(data.get("destination") or "").strip()
            export_path = str(data.get("export_path") or "").strip()
            summary = f"{dest} 攻略已生成" if dest else "攻略/文档已生成"
            profile = append_recent_task(
                profile,
                {
                    "saved_at": saved_at,
                    "app_mode": str(data.get("app_mode") or tm.APP_MODE_TRAVEL),
                    "summary": summary,
                    "destination": dest,
                    "export_path": export_path,
                },
            )
        elif kind == "explicit_note":
            profile = append_explicit_note(profile, str(data.get("text") or ""), saved_at=saved_at)
    return profile


def run_memory_pipeline(
    snapshot: dict[str, Any],
    *,
    trigger: str = "archive",
    archive_path: str = "",
) -> dict[str, Any]:
    """
    执行长期记忆流水线。
    返回 {"profile_updated": bool, "vector_added": bool, "summary": str}
    """
    result = {"profile_updated": False, "vector_added": False, "summary": ""}
    if not snapshot:
        return result

    candidates = build_candidates(snapshot)
    if not candidates and trigger != "archive":
        return result

    # 规则预筛 + LLM 确认（归档/旅行导出走完整判断）
    preworthy = [c for c in candidates if rule_worthiness(c, trigger=trigger)]
    if not preworthy and trigger == "explicit":
        preworthy = [c for c in candidates if c.get("kind") == "explicit_note"]

    history_snippet = _history_snippet(snapshot.get("history") or [])
    if trigger in ("archive", "travel_export") and candidates:
        worthy_kinds, summary = _llm_judge_and_summarize(candidates, history_snippet, snapshot)
    else:
        worthy_kinds = [c["kind"] for c in preworthy]
        summary = _fallback_summary(
            label=str(snapshot.get("label") or ""),
            app_mode=snapshot.get("app_mode", tm.APP_MODE_GENERAL),
            dest=str((snapshot.get("travel") or {}).get("intake", {}).get("destination") or ""),
            export_path=str((snapshot.get("travel") or {}).get("last_export_path") or ""),
            history_len=len(snapshot.get("history") or []),
        )

    saved_at = str(snapshot.get("saved_at") or "")
    profile = load_profile()
    new_profile = apply_worthy_candidates(profile, candidates, worthy_kinds, saved_at=saved_at)
    if new_profile != profile:
        save_profile(new_profile)
        result["profile_updated"] = True

    if summary and trigger in ("archive", "travel_export", "explicit"):
        meta = {
            "saved_at": saved_at,
            "app_mode": str(snapshot.get("app_mode", "")),
            "source": trigger,
            "archive_path": archive_path,
            "label": str(snapshot.get("label") or ""),
        }
        if add_session_summary(summary, metadata=meta):
            result["vector_added"] = True
    result["summary"] = summary
    return result


def run_memory_pipeline_from_current(
    *,
    trigger: str = "archive",
    archive_path: str = "",
) -> dict[str, Any]:
    snapshot = collect_snapshot(archived=(trigger == "archive"), label="")
    return run_memory_pipeline(snapshot, trigger=trigger, archive_path=archive_path)


def run_explicit_remember_from_user_text(user_text: str) -> dict[str, Any]:
    """用户本轮显式「记住」时调用。"""
    if not EXPLICIT_REMEMBER_RE.search(user_text):
        return {"profile_updated": False, "vector_added": False, "summary": ""}
    snapshot = collect_snapshot()
    notes = extract_explicit_notes([user_text])
    if not notes:
        return {"profile_updated": False, "vector_added": False, "summary": ""}
    profile = load_profile()
    for note in notes:
        profile = append_explicit_note(profile, note)
    save_profile(profile)
    summary = sanitize_text(f"用户显式记住：{notes[0]}")
    meta = {
        "saved_at": snapshot.get("saved_at", ""),
        "app_mode": str(snapshot.get("app_mode", "")),
        "source": "explicit",
    }
    vector_added = add_session_summary(summary, metadata=meta) if summary else False
    return {
        "profile_updated": True,
        "vector_added": vector_added,
        "summary": summary,
    }
