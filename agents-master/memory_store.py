"""长期记忆存储：Profile JSON + Chroma user_memory collection。"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from config.paths import APP_DIR

MEMORY_DIR = os.path.join(APP_DIR, "data", "memory")
PROFILE_PATH = os.path.join(MEMORY_DIR, "profile.json")
CHROMA_DIR = os.path.join(MEMORY_DIR, "chroma")
USER_MEMORY_COLLECTION = "user_memory"
PROFILE_VERSION = 1

PREF_FIELDS = ("default_budget", "default_transport", "default_companions")
PREF_FIELD_LABELS = {
    "default_budget": "预算档",
    "default_transport": "交通方式",
    "default_companions": "同行类型",
}
STABLE_FACT_FIELDS = ("home_city", "nickname")
MAX_RECENT_TASKS = 20
MAX_EXPLICIT_NOTES = 30
MAX_VECTOR_SUMMARIES = 200

# 敏感信息：命中则拒绝写入（整段或字段）
SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[A-Za-z0-9]{10,}", re.I),
    re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*\S+", re.I),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b\d{17}[\dXx]\b"),
    re.compile(
        r"\b\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
    ),
]

EXPLICIT_REMEMBER_RE = re.compile(
    r"(记住|请记住|帮我记|以后要|以后默认|以后都|别忘了|记得帮我)",
    re.I,
)

_chroma_collection = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)


def empty_profile() -> dict[str, Any]:
    return {
        "version": PROFILE_VERSION,
        "updated_at": "",
        "preferences": {field: "" for field in PREF_FIELDS},
        "stable_facts": {field: "" for field in STABLE_FACT_FIELDS},
        "recent_tasks": [],
        "explicit_notes": [],
    }


def contains_sensitive(text: str) -> bool:
    if not text or not str(text).strip():
        return False
    s = str(text)
    return any(p.search(s) for p in SENSITIVE_PATTERNS)


def sanitize_text(text: str) -> str:
    """移除或打码敏感片段；若整段不可救则返回空串。"""
    if not text:
        return ""
    s = str(text).strip()
    if contains_sensitive(s):
        for p in SENSITIVE_PATTERNS:
            s = p.sub("[已过滤]", s)
        if contains_sensitive(s):
            return ""
    return s


def _write_json(path: str, payload: dict[str, Any]) -> None:
    _ensure_dirs()
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_profile() -> dict[str, Any]:
    _ensure_dirs()
    if not os.path.isfile(PROFILE_PATH):
        return empty_profile()
    try:
        with open(PROFILE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return empty_profile()
        base = empty_profile()
        base["updated_at"] = str(data.get("updated_at") or "")
        prefs = data.get("preferences") or {}
        for field in PREF_FIELDS:
            val = sanitize_text(str(prefs.get(field) or ""))
            base["preferences"][field] = val
        facts = data.get("stable_facts") or {}
        for field in STABLE_FACT_FIELDS:
            val = sanitize_text(str(facts.get(field) or ""))
            base["stable_facts"][field] = val
        tasks = data.get("recent_tasks") or []
        if isinstance(tasks, list):
            base["recent_tasks"] = [
                t for t in tasks if isinstance(t, dict) and not contains_sensitive(json.dumps(t, ensure_ascii=False))
            ][-MAX_RECENT_TASKS:]
        notes = data.get("explicit_notes") or []
        if isinstance(notes, list):
            base["explicit_notes"] = [
                n
                for n in notes
                if isinstance(n, dict)
                and sanitize_text(str(n.get("text") or ""))
            ][-MAX_EXPLICIT_NOTES:]
        return base
    except (OSError, json.JSONDecodeError):
        return empty_profile()


def save_profile(profile: dict[str, Any]) -> None:
    profile = dict(profile)
    profile["version"] = PROFILE_VERSION
    profile["updated_at"] = _now_iso()
    _write_json(PROFILE_PATH, profile)


def merge_preferences(profile: dict[str, Any], new_prefs: dict[str, str]) -> dict[str, Any]:
    """以新会话偏好覆盖同名字段（仅非空）。"""
    out = dict(profile)
    prefs = dict(out.get("preferences") or empty_profile()["preferences"])
    for field in PREF_FIELDS:
        val = sanitize_text(str(new_prefs.get(field) or ""))
        if val:
            prefs[field] = val
    out["preferences"] = prefs
    return out


def merge_stable_facts(profile: dict[str, Any], facts: dict[str, str]) -> dict[str, Any]:
    out = dict(profile)
    current = dict(out.get("stable_facts") or empty_profile()["stable_facts"])
    for field in STABLE_FACT_FIELDS:
        val = sanitize_text(str(facts.get(field) or ""))
        if val:
            current[field] = val
    out["stable_facts"] = current
    return out


def append_recent_task(profile: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    out = dict(profile)
    tasks = list(out.get("recent_tasks") or [])
    clean = {k: v for k, v in task.items() if v and not contains_sensitive(str(v))}
    if not clean:
        return out
    export_path = clean.get("export_path", "")
    if export_path:
        tasks = [t for t in tasks if t.get("export_path") != export_path]
    tasks.append(clean)
    out["recent_tasks"] = tasks[-MAX_RECENT_TASKS:]
    return out


def append_explicit_note(profile: dict[str, Any], text: str, *, saved_at: str = "") -> dict[str, Any]:
    out = dict(profile)
    note = sanitize_text(text)
    if not note:
        return out
    notes = list(out.get("explicit_notes") or [])
    if any(n.get("text") == note for n in notes):
        return out
    notes.append({"text": note, "saved_at": saved_at or _now_iso()})
    out["explicit_notes"] = notes[-MAX_EXPLICIT_NOTES:]
    return out


def format_profile_for_context(profile: dict[str, Any] | None = None) -> str:
    """格式化为 [USER_MEMORY] 块内容。"""
    profile = profile or load_profile()
    lines: list[str] = []
    prefs = profile.get("preferences") or {}
    pref_parts = [
        f"{PREF_FIELD_LABELS.get(k, k)}={v}"
        for k, v in prefs.items()
        if v
    ]
    if pref_parts:
        lines.append("偏好：" + "；".join(pref_parts))
    facts = profile.get("stable_facts") or {}
    fact_parts = [f"{k}={v}" for k, v in facts.items() if v]
    if fact_parts:
        lines.append("稳定事实：" + "；".join(fact_parts))
    tasks = profile.get("recent_tasks") or []
    if tasks:
        last = tasks[-3:]
        task_lines = []
        for t in last:
            parts = [
                str(t.get("summary") or ""),
                str(t.get("export_path") or ""),
                str(t.get("destination") or ""),
            ]
            task_lines.append(" / ".join(p for p in parts if p))
        lines.append("近期任务：" + " | ".join(task_lines))
    notes = profile.get("explicit_notes") or []
    if notes:
        note_texts = [str(n.get("text") or "") for n in notes[-5:] if n.get("text")]
        if note_texts:
            lines.append("显式记住：" + "；".join(note_texts))
    return "\n".join(lines)


def format_profile_markdown() -> str:
    """侧边栏只读展示。"""
    profile = load_profile()
    lines = [f"**更新于**：{(profile.get('updated_at') or '—')[:19]}"]
    ctx = format_profile_for_context(profile)
    if ctx:
        lines.append(ctx)
    else:
        lines.append("（尚无长期 Profile 记录）")
    return "\n\n".join(lines)


def _get_embedding_function():
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        return OpenAIEmbeddingFunction(
            api_key=api_key,
            api_base=os.environ.get(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            model_name=os.environ.get("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3"),
        )
    except Exception:
        return None


def _get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection
    try:
        import chromadb

        _ensure_dirs()
        ef = _get_embedding_function()
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        if ef is not None:
            _chroma_collection = client.get_or_create_collection(
                name=USER_MEMORY_COLLECTION,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            _chroma_collection = client.get_or_create_collection(
                name=USER_MEMORY_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return _chroma_collection
    except Exception:
        return None


def chroma_available() -> bool:
    return _get_chroma_collection() is not None


def add_session_summary(
    summary: str,
    *,
    metadata: dict[str, Any],
    doc_id: str | None = None,
) -> bool:
    """写入会话摘要；近重复则跳过。"""
    text = sanitize_text(summary)
    if not text or len(text) < 8:
        return False
    coll = _get_chroma_collection()
    if coll is None:
        return False
    try:
        existing = coll.query(query_texts=[text], n_results=3)
        if existing and existing.get("distances"):
            dists = existing["distances"][0]
            if dists and min(dists) < 0.15:
                return False
    except Exception:
        pass
    meta = {k: str(v) for k, v in metadata.items() if v is not None}
    meta["source"] = meta.get("source", "session")
    doc_id = doc_id or f"mem_{uuid.uuid4().hex[:12]}"
    try:
        coll.add(ids=[doc_id], documents=[text], metadatas=[meta])
        _trim_vector_collection(coll)
        return True
    except Exception:
        return False


def _trim_vector_collection(coll) -> None:
    try:
        count = coll.count()
        if count <= MAX_VECTOR_SUMMARIES:
            return
        data = coll.get(include=["metadatas"])
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []
        if not ids:
            return
        pairs = list(zip(ids, metas))
        pairs.sort(key=lambda x: str((x[1] or {}).get("saved_at", "")))
        to_remove = [p[0] for p in pairs[: count - MAX_VECTOR_SUMMARIES]]
        if to_remove:
            coll.delete(ids=to_remove)
    except Exception:
        pass


def search_session_summaries(query: str, *, top_k: int = 3) -> list[dict[str, Any]]:
    text = sanitize_text(query)
    if not text or len(text) < 2:
        return []
    coll = _get_chroma_collection()
    if coll is None:
        return []
    try:
        if coll.count() == 0:
            return []
        result = coll.query(query_texts=[text], n_results=min(top_k, 5))
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        out: list[dict[str, Any]] = []
        for doc, meta, dist in zip(docs, metas, dists):
            if dist is not None and dist > 0.55:
                continue
            out.append(
                {
                    "text": doc,
                    "metadata": meta or {},
                    "distance": dist,
                }
            )
        return out
    except Exception:
        return []


def list_recent_summaries(*, limit: int = 5) -> list[dict[str, Any]]:
    coll = _get_chroma_collection()
    if coll is None:
        return []
    try:
        if coll.count() == 0:
            return []
        data = coll.get(include=["documents", "metadatas"])
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        rows = [
            {"id": i, "text": d, "metadata": m or {}}
            for i, d, m in zip(ids, docs, metas)
        ]
        rows.sort(key=lambda r: str((r.get("metadata") or {}).get("saved_at", "")), reverse=True)
        return rows[:limit]
    except Exception:
        return []


def sync_profile_preferences_to_session() -> None:
    """启动时将长期偏好填入 session（不覆盖用户已填项）。"""
    try:
        import streamlit as st
    except ImportError:
        return
    from session_store import USER_PREF_FIELDS, empty_user_preferences

    profile = load_profile()
    prefs = profile.get("preferences") or {}
    if "user_preferences" not in st.session_state:
        st.session_state.user_preferences = empty_user_preferences()
    current = st.session_state.user_preferences
    for field in USER_PREF_FIELDS:
        long_val = str(prefs.get(field) or "").strip()
        if long_val and not str(current.get(field) or "").strip():
            current[field] = long_val
