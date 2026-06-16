"""旅行规划模式：状态机、intake、意图检测与消息包装。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

APP_MODE_GENERAL = "general"
APP_MODE_TRAVEL = "travel"

PHASE_POI_SELECTION = "poi_selection"
PHASE_INTAKE_1 = "intake_1"
PHASE_INTAKE_2 = "intake_2"
PHASE_GENERATING = "generating"
PHASE_REVISION = "revision"

PHASE_LABELS: dict[str, str] = {
    PHASE_POI_SELECTION: "必玩景点推荐",
    PHASE_INTAKE_1: "需求采集（第一轮）",
    PHASE_INTAKE_2: "需求采集（补充轮）",
    PHASE_GENERATING: "攻略生成中",
    PHASE_REVISION: "攻略修改",
}

INTAKE_FIELDS = (
    "destination",
    "dates",
    "duration_days",
    "companions",
    "preferences",
    "budget",
    "transport",
    "must_visit",
    "constraints",
)

TRAVEL_INTAKE_BLOCK_RE = re.compile(
    r"<!--TRAVEL_INTAKE:(\{.*?\})-->",
    re.DOTALL,
)

TRAVEL_INTENT_RE = re.compile(
    r"(攻略|行程|旅行计划|旅游规划|去旅行|出游|几日游|一日游|两日游|三日游|规划一下|帮我规划)",
    re.IGNORECASE,
)

DURATION_RE = re.compile(
    r"(\d+)\s*日(游|行程)?|([一二三四五六七八九十两]+)\s*日",
)

DESTINATION_HINT_RE = re.compile(
    r"(?:去|到|在|想去|目的地[是为：:]\s*)([\u4e00-\u9fff]{2,8}?)(?:玩|游|旅行|攻略|一日|两日|\d+日|$|[，,。\s])",
)

# 常见目的地简表（辅触发）
KNOWN_DESTINATIONS = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
    "重庆",
    "西安",
    "南京",
    "苏州",
    "厦门",
    "青岛",
    "大理",
    "丽江",
    "三亚",
    "桂林",
    "武汉",
    "长沙",
    "昆明",
    "哈尔滨",
)

INTAKE_FALLBACK_NOTE = (
    "若无补充，我将根据你已提供的信息做推荐性规划，不确定处会标注「待核实」。"
)

SKIP_INTAKE_RE = re.compile(
    r"(没有补充|无补充|就这些|开始生成|直接生成|不用补充|跳过|随便|你定|按你说的|就这样)",
    re.IGNORECASE,
)

REVISION_INTENT_RE = re.compile(
    r"(改|换|删|加|调整|修改|轻松|累|不去|换成|改为|缩短|延长|预算|住|吃)",
    re.IGNORECASE,
)

INTAKE_FIELD_LABELS: dict[str, str] = {
    "destination": "目的地",
    "dates": "出行时间",
    "duration_days": "天数",
    "companions": "同行类型",
    "preferences": "偏好",
    "budget": "预算",
    "transport": "交通方式",
    "must_visit": "必去地点",
    "constraints": "约束/忌口",
}

POI_SELECTION_TOOL_CHECKLIST = """
【界面已展示「系统预取数据」】含高德 POI 表 + 知识库原文；用户可见，勿在正文重复粘贴大段工具 JSON。
【你的任务】基于预取数据写简短推荐列表，每项带角标 [RAG-N]/[AMAP-PN]；引导用户勾选必去/想去。
【勿重复调用】maps_text_search、query_knowledge_hub（除非预取区明确为空）。
【勿】生成完整攻略、勿调用 write_markdown_document。
""".strip()

GENERATING_TOOL_CHECKLIST = """
【界面已展示「系统预取数据」】天气 [AMAP-W]、路线 [AMAP-RN]、RAG 原文；导出文件会自动附上系统数据附录。
【正文结构】📋行程总览 → 🌤️天气 → 🗺️行程地图参考（Day 1 前）→ Day 1/2/… → 🚌交通/🍜美食/💰预算/🧩实用提示。
【章节标题】固定 emoji（勿省略）：`# 🧳 …` · `## 📋 行程总览` · `## 🌤️ 天气与穿搭` · `## 🗺️ 行程地图参考` · `## 🚌 交通指南` · `## 🍜 美食推荐` · `## 💰 预算估算` · `## 🧩 实用提示`；`## Day N：…` 不加 emoji。
【行程地图参考】每日一行动线（站点用 → 连接），与预取路线/POI 一致；勿放在文末。
【你的任务】写行程叙述；数字天气/路程须引用预取角标，禁止编造。
【勿写长「数据依据」章节】系统已生成；正文保留 3+ 处角标即可。
【勿重复调用】maps_weather、query_knowledge_hub、maps_direction_*（除非预取区为空）。
【勿调用 write_markdown_document】。

【本回合对话输出】完整 Markdown 攻略正文；写完后提示下载。
""".strip()

# O11/6A：改稿全文不再塞入 [TRAVEL_CONTEXT]，见 resolve_revision_plan_body + [PREVIOUS_PLAN]


def empty_intake() -> dict[str, Any]:
    return {field: None for field in INTAKE_FIELDS}


def is_field_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def compute_missing_fields(intake: dict[str, Any]) -> list[str]:
    return [f for f in INTAKE_FIELDS if not is_field_filled(intake.get(f))]


def format_missing_fields_zh(missing: list[str]) -> str:
    return "、".join(INTAKE_FIELD_LABELS.get(f, f) for f in missing)


def format_phase_zh(phase: str) -> str:
    return PHASE_LABELS.get(phase, phase)


def user_wants_skip_intake(text: str) -> bool:
    return bool(text and SKIP_INTAKE_RE.search(text))


def apply_intake_defaults(intake: dict[str, Any]) -> dict[str, Any]:
    """进入生成前为可选字段填默认值。"""
    out = dict(intake)
    for field in ("must_visit", "constraints"):
        if not is_field_filled(out.get(field)):
            out[field] = "无"
    return out


def user_wants_revision(text: str) -> bool:
    return bool(text and REVISION_INTENT_RE.search(text))


def travel_timeout_seconds(base_timeout: int, phase: str) -> int:
    """生成/改稿阶段需要更长超时。"""
    if phase in (PHASE_GENERATING, PHASE_REVISION):
        return max(base_timeout, 240)
    if phase == PHASE_POI_SELECTION:
        return max(base_timeout, 180)
    return base_timeout


def travel_recursion_limit(base_limit: int, phase: str) -> int:
    """按旅行阶段收紧 ReAct 步数，避免工具链过长堆叠 context。"""
    if phase in (PHASE_GENERATING, PHASE_REVISION):
        return min(base_limit, 32)
    if phase == PHASE_POI_SELECTION:
        return min(base_limit, 22)
    return min(base_limit, 12)


def should_reset_agent_thread_o9(phase_before: str, phase_after: str) -> bool:
    """
    O2：POI 阶段结束、进入 intake 或 generating 时，应重置 LangGraph thread。

    仅清空 Agent 侧 checkpoint；UI 聊天历史与 travel_intake / tool_memory 不变。
    """
    return (
        phase_before == PHASE_POI_SELECTION
        and phase_after != PHASE_POI_SELECTION
    )


def reset_agent_thread_o9() -> str:
    """O2：换新 thread_id，丢弃 POI 阶段累积的 ToolMessage。"""
    import streamlit as st

    from utils import random_uuid

    new_id = random_uuid()
    st.session_state.thread_id = new_id
    return new_id


def _poi_session_defaults() -> None:
    import streamlit as st

    if "must_visit_confirmed" not in st.session_state:
        st.session_state.must_visit_confirmed = False
    if "poi_for_destination" not in st.session_state:
        st.session_state.poi_for_destination = None


def mark_poi_selection_done(destination: str) -> None:
    import streamlit as st

    _poi_session_defaults()
    st.session_state.must_visit_confirmed = True
    st.session_state.poi_for_destination = destination


def reset_poi_selection_state() -> None:
    import streamlit as st

    st.session_state.must_visit_confirmed = False
    st.session_state.poi_for_destination = None


def needs_poi_selection(intake: dict[str, Any]) -> bool:
    """已有目的地/区域且尚未完成「必玩推荐→用户勾选」。"""
    import streamlit as st

    _poi_session_defaults()
    dest = intake.get("destination")
    if not is_field_filled(dest):
        return False
    if (
        st.session_state.must_visit_confirmed
        and st.session_state.poi_for_destination == dest
    ):
        return False
    return True


def merge_intake_and_track_destination(
    intake: dict[str, Any], updates: dict[str, Any]
) -> dict[str, Any]:
    """合并 intake；目的地变更时重置必玩确认状态。"""
    old_dest = intake.get("destination")
    merged = merge_intake(intake, updates)
    new_dest = merged.get("destination")
    if is_field_filled(new_dest) and new_dest != old_dest:
        reset_poi_selection_state()
    return merged


def apply_must_visit_from_user_reply(
    intake: dict[str, Any], user_query: str
) -> dict[str, Any]:
    """用户在必玩选择阶段的回复写入 must_visit。"""
    intake = dict(intake)
    if user_wants_skip_intake(user_query) or re.search(
        r"都行|随便|你选|你定|推荐", user_query
    ):
        intake["must_visit"] = "由规划师根据推荐景点安排"
        return intake

    updates = extract_intake_from_user_message(user_query)
    if updates.get("must_visit"):
        return merge_intake(intake, updates)
    if re.search(r"无必去|没有必去|都不", user_query):
        intake["must_visit"] = "无"
        return intake
    text = (user_query or "").strip()
    if text:
        intake["must_visit"] = text[:800]
    return intake


def _route_intake_after_poi(
    intake: dict[str, Any], user_turns: int
) -> tuple[str, int, dict[str, Any]]:
    """必玩选择完成后的 intake / 生成路由。"""
    missing = compute_missing_fields(intake)
    intake = apply_intake_defaults(intake)

    if len(missing) < 3:
        return PHASE_GENERATING, user_turns, intake
    if user_turns >= 2:
        return PHASE_INTAKE_2, user_turns, intake
    return PHASE_INTAKE_1, user_turns, intake


def merge_intake(intake: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(intake)
    for key, value in updates.items():
        if key not in INTAKE_FIELDS:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        merged[key] = value
    return merged


def parse_travel_intake_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    match = TRAVEL_INTAKE_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        if isinstance(data, dict):
            return {k: data.get(k) for k in INTAKE_FIELDS if k in data}
    except json.JSONDecodeError:
        return None
    return None


def strip_travel_intake_block(text: str) -> str:
    if not text:
        return text
    cleaned = TRAVEL_INTAKE_BLOCK_RE.sub("", text)
    return cleaned.rstrip()


def _chinese_numeral_to_int(s: str) -> int | None:
    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if s.isdigit():
        return int(s)
    if s in mapping:
        return mapping[s]
    if s.startswith("十") and len(s) == 2:
        return 10 + (mapping.get(s[1], 0))
    if s.endswith("十") and len(s) == 2:
        return mapping.get(s[0], 0) * 10
    return None


def extract_intake_from_user_message(text: str) -> dict[str, Any]:
    """从用户消息中用规则抽取 intake 字段（补充 Agent 回写）。"""
    updates: dict[str, Any] = {}
    if not text:
        return updates

    for city in KNOWN_DESTINATIONS:
        if city in text:
            updates["destination"] = city
            break

    if "destination" not in updates:
        m = DESTINATION_HINT_RE.search(text)
        if m:
            dest = m.group(1).strip()
            if len(dest) >= 2:
                updates["destination"] = dest

    dm = DURATION_RE.search(text)
    if dm:
        if dm.group(1):
            updates["duration_days"] = int(dm.group(1))
        elif dm.group(3):
            n = _chinese_numeral_to_int(dm.group(3))
            if n:
                updates["duration_days"] = n

    if re.search(r"一日|1\s*日", text) and "duration_days" not in updates:
        updates["duration_days"] = 1

    date_patterns = [
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}",
        r"(下周末|本周末|下周|明天|后天|国庆|春节|五一|清明|端午|中秋)",
    ]
    for pat in date_patterns:
        m = re.search(pat, text)
        if m:
            updates["dates"] = m.group(0)
            break

    if re.search(r"带娃|亲子|孩子", text):
        updates["companions"] = "亲子/带娃"
    elif re.search(r"情侣|二人|两个人", text):
        updates["companions"] = "情侣"
    elif re.search(r"独自|一个人|单人", text):
        updates["companions"] = "独自"
    elif re.search(r"老人|父母|长辈", text):
        updates["companions"] = "带长辈"

    prefs = []
    for label, kw in (
        ("美食", r"美食|吃"),
        ("人文", r"人文|历史|博物馆"),
        ("自然", r"自然|山水"),
        ("轻松", r"轻松|悠闲|不累"),
        ("打卡", r"打卡|网红"),
    ):
        if re.search(kw, text):
            prefs.append(label)
    if prefs:
        updates["preferences"] = "、".join(prefs)

    if re.search(r"预算|省钱|经济", text):
        updates["budget"] = "经济型"
    elif re.search(r"轻奢|中等", text):
        updates["budget"] = "中等"
    elif re.search(r"豪华|不差钱", text):
        updates["budget"] = "充裕"

    if re.search(r"自驾|开车", text):
        updates["transport"] = "自驾"
    elif re.search(r"地铁|公交|公共交通", text):
        updates["transport"] = "公共交通"
    elif re.search(r"高铁|飞机|火车", text):
        updates["transport"] = "大交通+当地公共交通"

    if re.search(r"必去|一定要去", text):
        mv = re.search(r"必去[：:]?\s*([^\n，,。]+)", text)
        updates["must_visit"] = mv.group(1).strip() if mv else "用户提及必去"
    elif re.search(r"没有必去|无必去", text):
        updates["must_visit"] = "无"

    if re.search(r"忌口|不吃|素食|过敏", text):
        updates["constraints"] = "饮食约束（见用户描述）"
    elif re.search(r"体力|走不动|少走路", text):
        updates["constraints"] = "体力有限"
    elif re.search(r"无特殊|没有约束", text):
        updates["constraints"] = "无"

    return updates


def detect_travel_intent(text: str) -> bool:
    """辅触发：意图词 +（目的地或天数）。"""
    if not text or not TRAVEL_INTENT_RE.search(text):
        return False
    updates = extract_intake_from_user_message(text)
    if updates.get("destination") or updates.get("duration_days"):
        return True
    if TRAVEL_INTENT_RE.search(text) and re.search(
        r"一日|两日|三日|\d+\s*日", text
    ):
        return True
    return False


def init_travel_state() -> None:
    import streamlit as st

    from travel_facts import init_travel_facts_state
    from travel_tool_memory import init_travel_tool_memory

    init_travel_tool_memory()
    init_travel_facts_state()
    defaults = {
        "app_mode": APP_MODE_GENERAL,
        "travel_phase": PHASE_INTAKE_1,
        "travel_intake": empty_intake(),
        "travel_intake_user_turns": 0,
        "travel_intake_round": 0,
        "last_travel_plan_md": "",
        "last_export_path": "",
        "agent_prompt_mode": APP_MODE_GENERAL,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def enter_travel_mode(*, reset_intake: bool = False) -> bool:
    """
    进入旅行规划模式。

    返回:
        是否需要重建 Agent（Prompt 模式变化时为 True）。
    """
    import streamlit as st

    needs_reconnect = (
        st.session_state.get("agent_prompt_mode") != APP_MODE_TRAVEL
    )
    st.session_state.app_mode = APP_MODE_TRAVEL
    if reset_intake:
        st.session_state.travel_phase = PHASE_INTAKE_1
        st.session_state.travel_intake = empty_intake()
        st.session_state.travel_intake_user_turns = 0
        st.session_state.travel_intake_round = 0
        st.session_state.last_travel_plan_md = ""
        st.session_state.last_export_path = ""
        reset_poi_selection_state()
    elif st.session_state.get("travel_phase") not in (
        PHASE_POI_SELECTION,
        PHASE_INTAKE_1,
        PHASE_INTAKE_2,
        PHASE_GENERATING,
        PHASE_REVISION,
    ):
        st.session_state.travel_phase = PHASE_INTAKE_1
    st.session_state.agent_prompt_mode = APP_MODE_TRAVEL
    return needs_reconnect


def exit_travel_mode() -> bool:
    """退出旅行模式；返回是否需要重建 Agent。"""
    import streamlit as st

    needs_reconnect = (
        st.session_state.get("agent_prompt_mode") != APP_MODE_GENERAL
    )
    st.session_state.app_mode = APP_MODE_GENERAL
    st.session_state.agent_prompt_mode = APP_MODE_GENERAL
    return needs_reconnect


def _phase_instruction(phase: str, missing: list[str]) -> str:
    missing_zh = format_missing_fields_zh(missing)
    if phase == PHASE_POI_SELECTION:
        return (
            "当前为「必玩景点推荐」阶段：用户已提供目的地/区域。"
            "必须先调用高德与 RAG 查询该区域必玩景点，用编号列表展示并说明来源；"
            "然后询问用户哪些必去、哪些想去、哪些不去。"
            "不要生成完整攻略，不要调用 write_markdown_document。\n"
            f"{POI_SELECTION_TOOL_CHECKLIST}"
        )
    if phase == PHASE_INTAKE_1:
        return (
            "当前为信息收集第 1 轮：仅提问，不要生成攻略。"
            f"仍缺：{missing_zh or '无'}。"
            "不要调用 write_markdown_document。"
        )
    if phase == PHASE_INTAKE_2:
        return (
            "当前为信息收集第 2 轮（最后一问）：继续提问仍缺项。"
            f"仍缺：{missing_zh or '无'}。"
            f"提问末尾必须原文附带：「{INTAKE_FALLBACK_NOTE}」"
            "不要生成攻略，不要调用 write_markdown_document。"
        )
    if phase == PHASE_GENERATING:
        return (
            "当前为生成阶段：按下列工具链拉数，在对话中输出完整 Markdown；"
            "勿调用 write_markdown_document（系统自动导出）。\n"
            f"{GENERATING_TOOL_CHECKLIST}"
        )
    if phase == PHASE_REVISION:
        return (
            "当前为改稿阶段：根据用户意见与【上一版攻略】修订；按需重查工具；"
            "在对话中输出完整新 Markdown，勿调用 write_markdown_document。"
            "保持章节 emoji 与结构：`# 🧳` · `## 📋 行程总览` · `## 🌤️ 天气与穿搭` · "
            "`## 🗺️ 行程地图参考`（Day 1 前）· Day 章节 · `## 🚌/🍜/💰/🧩` 尾部四章。"
        )
    return ""


def build_travel_context(
    *,
    phase: str,
    intake: dict[str, Any],
    missing: list[str],
    intake_user_turns: int,
) -> str:
    from travel_facts import format_travel_facts_block, get_travel_facts
    from travel_tool_memory import format_tool_memory_for_context, get_cached_rag_collections

    payload: dict[str, Any] = {
        "app_mode": APP_MODE_TRAVEL,
        "phase": phase,
        "intake_user_turns": intake_user_turns,
        "intake": intake,
        "missing_fields": missing,
        "missing_count": len(missing),
    }
    collections = get_cached_rag_collections()
    if collections:
        payload["rag_collections_cached"] = collections
        payload["rag_skip_list_collections"] = True

    lines = [
        "[TRAVEL_CONTEXT]",
        json.dumps(payload, ensure_ascii=False, indent=2),
        _phase_instruction(phase, missing),
    ]
    if collections and phase in (
        PHASE_POI_SELECTION,
        PHASE_GENERATING,
        PHASE_REVISION,
    ):
        lines.append(
            "【O10 已缓存 RAG collections】"
            f"{', '.join(collections)}；本轮勿再调用 list_collections。"
        )

    tool_mem = format_tool_memory_for_context()
    if tool_mem:
        lines.append(tool_mem)

    facts_block = format_travel_facts_block(get_travel_facts())
    if facts_block:
        lines.append(facts_block)
    elif phase in (PHASE_POI_SELECTION, PHASE_GENERATING):
        lines.append(
            "【TRAVEL_FACTS】本轮暂无预取数据（可能 MCP 未就绪或预取失败）；"
            "可谨慎调用 query_knowledge_hub / maps_* 补充，并标注待核实。"
        )

    if phase == PHASE_REVISION:
        lines.append(
            "【6A 改稿基准】完整上一版攻略见下方 [PREVIOUS_PLAN] 块（优先已导出文件），"
            "勿依赖本块重复粘贴全文。"
        )

    lines.append("[/TRAVEL_CONTEXT]")
    return "\n".join(lines)


def resolve_revision_plan_body(
    *,
    last_travel_plan_md: str,
    last_export_path: str,
) -> tuple[str, str]:
    """
    6A：改稿基准优先从导出文件读取，其次 session 中的 last_travel_plan_md。
    返回 (正文, source 标签)。
    """
    if last_export_path:
        from config.paths import APP_DIR

        rel = [last_export_path.strip()]
        body = load_plan_from_export_paths(rel, app_dir=APP_DIR)
        if body:
            return body, f"export:{last_export_path}"
    if (last_travel_plan_md or "").strip():
        return last_travel_plan_md.strip(), "session:last_travel_plan_md"
    return "", ""


def prepare_phase_before_agent(
    *,
    phase: str,
    intake: dict[str, Any],
    intake_user_turns: int,
    last_travel_plan_md: str = "",
    user_query: str = "",
) -> tuple[str, int, dict[str, Any]]:
    """
    用户发来消息后、调用 Agent 前，决定本回合 phase 并返回 phase、user_turns、intake。
    """
    intake = dict(intake)
    missing = compute_missing_fields(intake)
    user_turns = intake_user_turns + 1

    if phase == PHASE_REVISION or (
        last_travel_plan_md and user_wants_revision(user_query)
    ):
        return PHASE_REVISION, user_turns, intake

    if phase == PHASE_GENERATING and last_travel_plan_md:
        return PHASE_REVISION, user_turns, intake

    if phase == PHASE_POI_SELECTION:
        dest = intake.get("destination") or ""
        intake = apply_must_visit_from_user_reply(intake, user_query)
        if is_field_filled(intake.get("must_visit")):
            mark_poi_selection_done(str(dest))
        return _route_intake_after_poi(intake, user_turns)

    if needs_poi_selection(intake):
        return PHASE_POI_SELECTION, user_turns, intake

    if phase in (PHASE_INTAKE_1, PHASE_INTAKE_2) and user_wants_skip_intake(
        user_query
    ):
        intake = apply_intake_defaults(intake)
        return PHASE_GENERATING, user_turns, intake

    if phase == PHASE_INTAKE_1:
        if len(missing) < 3:
            intake = apply_intake_defaults(intake)
            return PHASE_GENERATING, user_turns, intake
        if user_turns >= 2:
            return PHASE_INTAKE_2, user_turns, intake
        return PHASE_INTAKE_1, user_turns, intake

    if phase == PHASE_INTAKE_2:
        intake = apply_intake_defaults(intake)
        return PHASE_GENERATING, user_turns, intake

    if phase == PHASE_GENERATING:
        return PHASE_GENERATING, user_turns, intake

    return phase, user_turns, intake


def after_assistant_response(
    *,
    phase: str,
    intake: dict[str, Any],
    assistant_text: str,
    intake_user_turns: int,
) -> tuple[str, dict[str, Any], str]:
    """
    Agent 回复后：合并 intake 块、推断 phase 切换、返回清洗后的展示文本。
    """
    display_text = strip_travel_intake_block(assistant_text)
    block = parse_travel_intake_block(assistant_text)
    if block:
        intake = merge_intake(intake, block)

    new_phase = phase
    missing = compute_missing_fields(intake)

    if phase == PHASE_POI_SELECTION and not looks_like_travel_plan(display_text):
        new_phase = PHASE_POI_SELECTION

    if (
        phase == PHASE_INTAKE_1
        and len(missing) >= 3
        and intake_user_turns >= 1
        and not looks_like_travel_plan(display_text)
        and ("？" in display_text or "?" in display_text)
    ):
        new_phase = PHASE_INTAKE_2

    if looks_like_travel_plan(display_text):
        new_phase = PHASE_REVISION
        return new_phase, intake, display_text

    return new_phase, intake, display_text


_SECTION_EMOJI_PREFIX = re.compile(
    r"^(##+)\s*(?:📋|🌤️|🗺️|🚌|🍜|💰|🧩|🧳)\s*",
    re.MULTILINE,
)
_SYSTEM_APPENDIX_MARKER = "## 数据依据（系统预取"


def split_travel_plan_and_appendix(text: str) -> tuple[str, str]:
    """拆分攻略正文与系统附录（导出检测用）。"""
    if _SYSTEM_APPENDIX_MARKER in text:
        idx = text.find(_SYSTEM_APPENDIX_MARKER)
        return text[:idx].rstrip(), text[idx:].lstrip()
    return (text or "").strip(), ""


def _strip_section_emojis(text: str) -> str:
    return _SECTION_EMOJI_PREFIX.sub(r"\1 ", text or "")


def canonical_plan_text_for_detection(text: str) -> str:
    """检测用：去附录、去章节 emoji、去 intake 确认前缀。"""
    plan, _ = split_travel_plan_and_appendix(text)
    plan = _strip_section_emojis(plan)
    return normalize_travel_plan_body(plan)


def looks_like_travel_plan(text: str) -> bool:
    cleaned = canonical_plan_text_for_detection(text)
    if len(cleaned) < 400:
        return False
    markers = ("## 行程总览", "## 逐日详情", "## 天气与穿搭", "## 行程地图参考")
    marker_hits = sum(1 for m in markers if m in cleaned)
    if marker_hits >= 2:
        return True
    if marker_hits >= 1 and re.search(
        r"^##\s+Day\s+\d+", cleaned, re.MULTILINE | re.IGNORECASE
    ):
        return True
    if marker_hits >= 1 and re.search(r"^##\s+第\d+天", cleaned, re.MULTILINE):
        return True
    return False


def normalize_travel_plan_body(text: str) -> str:
    """去掉 intake 确认话术等前缀，保留攻略正文（导出与后处理用）。"""
    cleaned = strip_travel_intake_block(text).strip()
    if not cleaned:
        return ""
    if "## 行程总览" in cleaned:
        ov_idx = cleaned.find("## 行程总览")
        segment = cleaned[:ov_idx]
        headings = list(re.finditer(r"^#\s+.+$", segment, re.MULTILINE))
        if headings:
            return cleaned[headings[-1].start() :].strip()
    if "\n---\n" in cleaned:
        head, tail = cleaned.split("\n---\n", 1)
        tail = tail.strip()
        if "## 行程总览" in tail and len(head) < 600:
            return tail if tail.startswith("#") else cleaned
    return cleaned


def _apply_user_preferences_to_intake(intake: dict[str, Any]) -> dict[str, Any]:
    """P1：空字段填入用户默认偏好（不覆盖已有值）。"""
    import streamlit as st

    prefs = st.session_state.get("user_preferences") or {}
    mapping = {
        "budget": prefs.get("default_budget"),
        "transport": prefs.get("default_transport"),
        "companions": prefs.get("default_companions"),
    }
    out = dict(intake)
    for field, pref_val in mapping.items():
        if not is_field_filled(out.get(field)) and is_field_filled(pref_val):
            out[field] = str(pref_val).strip()
    return out


def advance_travel_turn(
    user_query: str,
    *,
    phase: str,
    intake: dict[str, Any],
    intake_user_turns: int,
    last_travel_plan_md: str,
) -> tuple[str, int, dict[str, Any]]:
    """合并 intake、推进 phase（不构建 Agent 消息，便于预取后再包装）。"""
    extracted = extract_intake_from_user_message(user_query)
    intake = merge_intake_and_track_destination(intake, extracted)
    intake = _apply_user_preferences_to_intake(intake)
    new_phase, new_turns, intake = prepare_phase_before_agent(
        phase=phase,
        intake=intake,
        intake_user_turns=intake_user_turns,
        last_travel_plan_md=last_travel_plan_md,
        user_query=user_query,
    )
    return new_phase, new_turns, intake


def compose_travel_agent_query(
    user_query: str,
    *,
    phase: str,
    intake: dict[str, Any],
    intake_user_turns: int,
    last_travel_plan_md: str,
) -> str:
    """在 phase/intake 已定且 travel_facts 已预取后，构建发给 Agent 的完整文本。"""
    missing = compute_missing_fields(intake)
    ctx = build_travel_context(
        phase=phase,
        intake=intake,
        missing=missing,
        intake_user_turns=intake_user_turns,
    )
    parts = [ctx]
    if phase == PHASE_REVISION:
        import streamlit as st

        plan_body, plan_src = resolve_revision_plan_body(
            last_travel_plan_md=last_travel_plan_md,
            last_export_path=st.session_state.get("last_export_path", ""),
        )
        if plan_body:
            parts.append(
                f"[PREVIOUS_PLAN source={plan_src}]\n{plan_body}\n[/PREVIOUS_PLAN]"
            )
    parts.append(f"---\n\n用户消息：\n{user_query}")
    return "\n\n".join(parts)


def wrap_user_query_for_agent(
    user_query: str,
    *,
    app_mode: str,
    phase: str,
    intake: dict[str, Any],
    intake_user_turns: int,
    last_travel_plan_md: str,
) -> tuple[str, str, int, dict[str, Any]]:
    """
    处理用户消息：合并 intake、推进 phase、生成发送给 Agent 的完整文本。

    返回: (wrapped_query, new_phase, new_user_turns, merged_intake)
    """
    if app_mode != APP_MODE_TRAVEL:
        return user_query, phase, intake_user_turns, intake

    new_phase, new_turns, intake = advance_travel_turn(
        user_query,
        phase=phase,
        intake=intake,
        intake_user_turns=intake_user_turns,
        last_travel_plan_md=last_travel_plan_md,
    )
    wrapped = compose_travel_agent_query(
        user_query,
        phase=new_phase,
        intake=intake,
        intake_user_turns=new_turns,
        last_travel_plan_md=last_travel_plan_md,
    )
    return wrapped, new_phase, new_turns, intake


def check_travel_delivery(
    *,
    phase_before: str,
    final_text: str,
    export_paths: list[str],
) -> str | None:
    """生成/改稿后校验交付物，返回警告文案或 None。"""
    if phase_before not in (PHASE_GENERATING, PHASE_REVISION):
        return None
    cleaned = strip_travel_intake_block(final_text).strip()
    if export_paths:
        return None
    if not looks_like_travel_plan(cleaned) and len(cleaned) < 300:
        return (
            "本次回复可能未包含完整攻略。请发送："
            "「请按旅行规划模板输出完整 Markdown 攻略」。"
        )
    if looks_like_travel_plan(cleaned) and not export_paths:
        return (
            "攻略正文已在对话中，但自动保存文件失败。"
            "请重试生成或检查 data/outputs/ 目录权限。"
        )
    return None


def reset_travel_session() -> None:
    """重置旅行模式对话状态（保留 app_mode）。"""
    import streamlit as st

    from travel_facts import clear_travel_facts
    from travel_tool_memory import clear_travel_tool_memory

    clear_travel_tool_memory()
    clear_travel_facts()
    st.session_state.travel_phase = PHASE_INTAKE_1
    st.session_state.travel_intake = empty_intake()
    st.session_state.travel_intake_user_turns = 0
    st.session_state.travel_intake_round = 0
    st.session_state.last_travel_plan_md = ""
    st.session_state.last_export_path = ""
    reset_poi_selection_state()


def finalize_assistant_turn(
    *,
    phase: str,
    intake: dict[str, Any],
    assistant_text: str,
    intake_user_turns: int,
) -> tuple[str, str, dict[str, Any], str]:
    """
    返回: (display_text, new_phase, intake, last_plan_md_if_any)
    """
    new_phase, intake, display_text = after_assistant_response(
        phase=phase,
        intake=intake,
        assistant_text=assistant_text,
        intake_user_turns=intake_user_turns,
    )
    last_plan = ""
    if looks_like_travel_plan(display_text):
        last_plan = display_text
        new_phase = PHASE_REVISION
    return display_text, new_phase, intake, last_plan


def load_plan_from_export_paths(export_paths: list[str], *, app_dir: str) -> str:
    """从最新导出的 Markdown 读取攻略全文（摘要模式下改稿基准）。"""
    if not export_paths:
        return ""
    rel = export_paths[-1].strip().replace("\\", "/")
    if os.path.isabs(rel):
        abs_path = rel
    elif rel.startswith("data/outputs/"):
        abs_path = os.path.join(app_dir, rel)
    else:
        abs_path = os.path.join(app_dir, "data", "outputs", os.path.basename(rel))
    try:
        with open(abs_path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""
