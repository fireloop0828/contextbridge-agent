"""旅行模式 P0：结构化工具事实（travel_facts）与 MCP 响应解析。"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Any, TypedDict

FACTS_VERSION = 1
EXCERPT_MAX = 400
CONTEXT_EXCERPT_MAX = 220
RAG_MIN_SCORE_PERCENT = 3.5


class RagFact(TypedDict, total=False):
    id: str
    collection: str
    query: str
    excerpt: str
    source_doc: str
    score: str


class PoiFact(TypedDict, total=False):
    id: str
    name: str
    address: str
    amap_id: str
    location: str  # "lon,lat" (gcj02)


class RouteFact(TypedDict, total=False):
    id: str
    mode: str
    origin_name: str
    dest_name: str
    origin_loc: str  # "lon,lat" (gcj02)
    dest_loc: str  # "lon,lat" (gcj02)
    distance_km: float | None
    duration_min: int | None
    summary: str


class WeatherFact(TypedDict, total=False):
    id: str
    city: str
    forecasts: list[dict[str, Any]]


class CoverageFact(TypedDict, total=False):
    rag_hits: int
    amap_hits: int
    unverified: int


class RagMeta(TypedDict, total=False):
    query: str
    collection: str
    raw_count: int
    passed_count: int
    threshold_percent: float
    notice: str


class TravelFacts(TypedDict, total=False):
    version: int
    phase: str
    destination: str
    fetched_at: str
    rag: list[RagFact]
    rag_meta: RagMeta
    amap: dict[str, Any]
    coverage: CoverageFact
    errors: list[str]


def empty_travel_facts(*, phase: str = "", destination: str = "") -> TravelFacts:
    return {
        "version": FACTS_VERSION,
        "phase": phase,
        "destination": destination,
        "fetched_at": "",
        "rag": [],
        "amap": {"weather": None, "pois": [], "routes": []},
        "coverage": {"rag_hits": 0, "amap_hits": 0, "unverified": 0},
        "errors": [],
    }


def init_travel_facts_state() -> None:
    import streamlit as st

    if "travel_facts" not in st.session_state:
        st.session_state.travel_facts = None


def get_travel_facts() -> TravelFacts | None:
    import streamlit as st

    init_travel_facts_state()
    raw = st.session_state.get("travel_facts")
    if isinstance(raw, dict) and raw.get("version"):
        return raw
    return None


def set_travel_facts(facts: TravelFacts | None) -> None:
    import streamlit as st

    st.session_state.travel_facts = facts


def clear_travel_facts() -> None:
    set_travel_facts(None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def tool_result_to_text(result: Any) -> str:
    """将 LangChain/MCP 工具返回值统一为文本。"""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _try_parse_json(text: str) -> Any | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def parse_amap_pois(raw: Any) -> list[PoiFact]:
    text = tool_result_to_text(raw)
    data = _try_parse_json(text)
    if not isinstance(data, dict):
        return []
    pois = data.get("pois") or []
    out: list[PoiFact] = []
    for idx, poi in enumerate(pois[:12], start=1):
        if not isinstance(poi, dict):
            continue
        name = (poi.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "id": f"AMAP-P{idx}",
                "name": name,
                "address": (poi.get("address") or "").strip(),
                "amap_id": (poi.get("id") or "").strip(),
                "location": (poi.get("location") or "").strip(),
            }
        )
    return out


def parse_amap_weather(raw: Any) -> WeatherFact | None:
    text = tool_result_to_text(raw)
    data = _try_parse_json(text)
    if not isinstance(data, dict):
        return None
    city = (data.get("city") or "").strip()
    forecasts = data.get("forecasts") or []
    if not city and not forecasts:
        return None
    return {
        "id": "AMAP-W",
        "city": city,
        "forecasts": forecasts if isinstance(forecasts, list) else [],
    }


def _meters_to_km(value: Any) -> float | None:
    try:
        return round(float(value) / 1000.0, 1)
    except (TypeError, ValueError):
        return None


def _seconds_to_min(value: Any) -> int | None:
    try:
        return max(1, int(round(float(value) / 60.0)))
    except (TypeError, ValueError):
        return None


def parse_amap_route(
    raw: Any,
    *,
    route_id: str,
    mode: str,
    origin_name: str,
    dest_name: str,
    origin_loc: str = "",
    dest_loc: str = "",
) -> RouteFact | None:
    text = tool_result_to_text(raw)
    data = _try_parse_json(text)
    if not isinstance(data, dict):
        return None
    route = data.get("route") or data
    paths = route.get("paths") if isinstance(route, dict) else None
    if not paths or not isinstance(paths, list):
        return None
    path0 = paths[0] if paths else {}
    if not isinstance(path0, dict):
        return None
    dist_km = _meters_to_km(path0.get("distance"))
    dur_min = _seconds_to_min(path0.get("duration"))
    summary = f"{origin_name}→{dest_name}"
    if dist_km is not None and dur_min is not None:
        summary += f" · 约{dist_km}km/{dur_min}分钟"
    return {
        "id": route_id,
        "mode": mode,
        "origin_name": origin_name,
        "dest_name": dest_name,
        "origin_loc": origin_loc,
        "dest_loc": dest_loc,
        "distance_km": dist_km,
        "duration_min": dur_min,
        "summary": summary,
    }


def parse_geo_location(raw: Any) -> str | None:
    text = tool_result_to_text(raw)
    data = _try_parse_json(text)
    if not isinstance(data, dict):
        return None
    items = data.get("return") or data.get("geocodes") or []
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            loc = (first.get("location") or "").strip()
            if loc and "," in loc:
                return loc
    m = re.search(r'"location"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _basename(path: str) -> str:
    return os.path.basename(path.replace("\\", "/"))


def _parse_score_percent(text: str) -> float | None:
    """
    rag-server 常见格式：`2.98%` 或 `相关度: 2.98%`。
    返回百分比数值（如 2.98），无法解析则 None。
    """
    s = (text or "").strip()
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def rag_passes_threshold(item: RagFact) -> bool:
    """过滤相似度过低的 RAG 片段（score 为空则不过滤）。"""
    score = _parse_score_percent(str(item.get("score") or ""))
    if score is None:
        return True
    return score >= RAG_MIN_SCORE_PERCENT


def _is_rag_boilerplate(excerpt: str) -> bool:
    """跳过检索头、引用列表等非正文片段。"""
    s = (excerpt or "").strip()
    if not s or len(s) < 20:
        return True
    if re.match(r"^#+\s*检索结果", s):
        return True
    if "针对查询" in s and "找到" in s and "条相关结果" in s:
        return True
    if s.startswith("## 引用来源") or s.startswith("引用来源"):
        return True
    return False


def _iter_rag_content_blocks(text: str) -> list[str]:
    """按 `### [N]` 切分 RAG 正文块，跳过顶部的检索摘要头。"""
    parts = re.split(r"###\s*\[\d+\]", text)
    if len(parts) > 1:
        return [p for p in parts[1:] if p.strip()]
    return []


def build_rag_meta(
    *,
    query: str,
    collection: str,
    raw_count: int,
    passed_count: int,
) -> RagMeta:
    meta: RagMeta = {
        "query": query,
        "collection": collection,
        "raw_count": raw_count,
        "passed_count": passed_count,
        "threshold_percent": RAG_MIN_SCORE_PERCENT,
    }
    if raw_count == 0:
        meta["notice"] = "未找到与查询相关的知识库内容。"
    elif passed_count == 0:
        meta["notice"] = (
            f"针对查询「{query}」检索到 {raw_count} 条，"
            f"但相关度≥{RAG_MIN_SCORE_PERCENT}% 的为 0 条（相关性较低，未展示）。"
        )
    return meta


def parse_rag_results(
    raw: Any, *, query: str, collection: str = ""
) -> tuple[list[RagFact], RagMeta]:
    text = tool_result_to_text(raw)
    if "未找到相关结果" in text or "未找到与查询相关" in text:
        return [], build_rag_meta(
            query=query, collection=collection, raw_count=0, passed_count=0
        )

    out: list[RagFact] = []
    blocks = _iter_rag_content_blocks(text)

    for block in blocks:
        if not block.strip():
            continue
        source_m = re.search(r"\*\*来源:\*\*\s*`?([^`\n]+)`?", block)
        score_m = re.search(r"\*\*相关度:\*\*\s*([^\n]+)", block)
        quote_m = re.search(r">\s*(.+?)(?:\n\n|\n###|\Z)", block, re.DOTALL)
        excerpt = (quote_m.group(1) if quote_m else "").strip()
        if not excerpt:
            continue
        excerpt = re.sub(r"\s+", " ", excerpt)
        if len(excerpt) > EXCERPT_MAX:
            excerpt = excerpt[:EXCERPT_MAX] + "…"
        if _is_rag_boilerplate(excerpt):
            continue
        source_doc = _basename(source_m.group(1).strip()) if source_m else ""
        out.append(
            {
                "id": f"RAG-{len(out) + 1}",
                "collection": collection,
                "query": query,
                "excerpt": excerpt,
                "source_doc": source_doc,
                "score": (score_m.group(1).strip() if score_m else ""),
            }
        )

    if not out:
        cit_data = _try_parse_json(text)
        if isinstance(cit_data, dict):
            citations = cit_data.get("citations") or []
            if isinstance(citations, list):
                for item in citations:
                    if not isinstance(item, dict):
                        continue
                    excerpt = (item.get("content") or item.get("excerpt") or "").strip()
                    if not excerpt or _is_rag_boilerplate(excerpt):
                        continue
                    out.append(
                        {
                            "id": f"RAG-{len(out) + 1}",
                            "collection": collection,
                            "query": query,
                            "excerpt": excerpt[:EXCERPT_MAX],
                            "source_doc": _basename(
                                str(item.get("source") or item.get("file") or "")
                            ),
                            "score": str(item.get("score") or ""),
                        }
                    )
    raw_count = len(out)
    filtered = [x for x in out if rag_passes_threshold(x)]
    meta = build_rag_meta(
        query=query,
        collection=collection,
        raw_count=raw_count,
        passed_count=len(filtered),
    )
    return filtered, meta


def pick_rag_collection(cached: list[str]) -> str:
    if not cached:
        return "travel_plan"
    for preferred in ("travel_plan", "travel", "default"):
        if preferred in cached:
            return preferred
    return cached[0]


def update_coverage(facts: TravelFacts) -> None:
    rag = facts.get("rag") or []
    amap = facts.get("amap") or {}
    weather = amap.get("weather")
    pois = amap.get("pois") or []
    routes = amap.get("routes") or []
    amap_hits = (1 if weather else 0) + len(pois) + len(routes)
    errors = facts.get("errors") or []
    unverified = len(errors)
    if not rag:
        unverified += 1
    if not weather:
        unverified += 1
    facts["coverage"] = {
        "rag_hits": len(rag),
        "amap_hits": amap_hits,
        "unverified": unverified,
    }


def finalize_facts(facts: TravelFacts) -> TravelFacts:
    facts["fetched_at"] = _now_iso()
    facts["version"] = FACTS_VERSION
    update_coverage(facts)
    return facts


def facts_for_context(facts: TravelFacts | None) -> dict[str, Any]:
    """注入 [TRAVEL_CONTEXT] 的精简版，控制 Token。"""
    if not facts:
        return {}
    rag_ctx = []
    for item in facts.get("rag") or []:
        rag_ctx.append(
            {
                "id": item.get("id"),
                "collection": item.get("collection"),
                "source_doc": item.get("source_doc"),
                "excerpt": (item.get("excerpt") or "")[:CONTEXT_EXCERPT_MAX],
            }
        )
    amap = facts.get("amap") or {}
    weather = amap.get("weather")
    weather_ctx = None
    if isinstance(weather, dict):
        forecasts = weather.get("forecasts") or []
        weather_ctx = {
            "id": weather.get("id", "AMAP-W"),
            "city": weather.get("city"),
            "forecasts": forecasts[:4],
        }
    routes_ctx = []
    for r in amap.get("routes") or []:
        routes_ctx.append(
            {
                "id": r.get("id"),
                "summary": r.get("summary"),
                "mode": r.get("mode"),
            }
        )
    pois_ctx = [
        {"id": p.get("id"), "name": p.get("name"), "address": p.get("address")}
        for p in (amap.get("pois") or [])[:10]
    ]
    return {
        "phase": facts.get("phase"),
        "destination": facts.get("destination"),
        "fetched_at": facts.get("fetched_at"),
        "rag": rag_ctx,
        "amap": {
            "weather": weather_ctx,
            "pois": pois_ctx,
            "routes": routes_ctx,
        },
        "coverage": facts.get("coverage"),
        "citation_guide": (
            "正文引用须使用角标：RAG 用 [RAG-N]，天气用 [AMAP-W]，"
            "路线用 [AMAP-RN]，POI 用 [AMAP-PN]（N 与 travel_facts 中 id 一致）。"
        ),
    }


def format_travel_facts_block(facts: TravelFacts | None) -> str:
    if not facts:
        return ""
    payload = facts_for_context(facts)
    return (
        "[TRAVEL_FACTS]\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n[/TRAVEL_FACTS]"
    )


def prioritize_rag_by_destination(rag: list[RagFact], destination: str) -> list[RagFact]:
    """目的地关键词命中的片段排在前面，提升 RAG 与行程的相关性感知。"""
    dest = (destination or "").strip()
    if not dest or len(dest) < 2:
        return rag

    def _score(item: RagFact) -> tuple[int, str]:
        text = f"{item.get('excerpt', '')} {item.get('source_doc', '')}"
        hit = 1 if dest in text else 0
        return (-hit, item.get("id", ""))

    return sorted(rag, key=_score)


def _rag_snippet_for_poi(rag: list[RagFact], poi_name: str) -> str:
    name = (poi_name or "").strip()
    if not name:
        return ""
    for item in rag:
        excerpt = item.get("excerpt") or ""
        if name in excerpt or name[:2] in excerpt:
            rid = item.get("id", "RAG")
            doc = item.get("source_doc") or ""
            return f"{rid}" + (f"（{doc}）" if doc else "")
    return ""


def build_dual_source_rows(facts: TravelFacts) -> list[dict[str, str]]:
    """POI 阶段：高德 POI × 知识库命中对照行。"""
    amap = facts.get("amap") or {}
    pois = amap.get("pois") or []
    rag = facts.get("rag") or []
    rows: list[dict[str, str]] = []
    for p in pois[:10]:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        rows.append(
            {
                "景点": name,
                "高德": "✓",
                "知识库": _rag_snippet_for_poi(rag, name) or "—",
                "地址": (p.get("address") or "")[:40],
            }
        )
    if not rows and rag:
        for item in rag[:6]:
            rows.append(
                {
                    "景点": "（知识库提及）",
                    "高德": "—",
                    "知识库": f"{item.get('id', '')} {item.get('source_doc', '')}",
                    "地址": (item.get("excerpt") or "")[:36] + "…",
                }
            )
    return rows


def format_provenance_summary(facts: TravelFacts) -> str:
    """一行摘要，用于横幅。"""
    cov = facts.get("coverage") or {}
    dest = facts.get("destination") or "目的地"
    rag_n = cov.get("rag_hits", 0)
    amap_n = cov.get("amap_hits", 0)
    parts = [f"**{dest}**"]
    if rag_n:
        parts.append(f"知识库 **{rag_n}** 条")
    amap = facts.get("amap") or {}
    if amap.get("weather"):
        parts.append("高德天气")
    pois = amap.get("pois") or []
    if pois:
        parts.append(f"POI **{len(pois)}** 个")
    routes = amap.get("routes") or []
    if routes:
        parts.append(f"路线 **{len(routes)}** 段")
    if amap_n and not (amap.get("weather") or pois or routes):
        parts.append(f"高德 **{amap_n}** 项")
    parts.append("（编排层 MCP 预取，非模型编造）")
    return " · ".join(parts)


def format_facts_markdown_appendix(facts: TravelFacts) -> str:
    """
    系统生成的数据依据附录（导出与对照用）。
    与 LLM 正文分离，直接体现 MCP/RAG 原始能力。
    """
    if not facts:
        return ""
    lines = [
        "---",
        "",
        "## 数据依据（系统预取 · 非模型编造）",
        "",
        f"> 预取时间：{facts.get('fetched_at', '')} · "
        f"阶段：{facts.get('phase', '')} · {format_provenance_summary(facts)}",
        "",
    ]

    amap = facts.get("amap") or {}
    weather = amap.get("weather")
    if isinstance(weather, dict) and weather.get("forecasts"):
        city = weather.get("city") or facts.get("destination") or ""
        lines.append(f"### 天气 [{weather.get('id', 'AMAP-W')}] · {city}")
        lines.append("")
        lines.append("| 日期 | 白天 | 夜间 | 气温 |")
        lines.append("|------|------|------|------|")
        for fc in weather.get("forecasts") or []:
            if not isinstance(fc, dict):
                continue
            lines.append(
                f"| {fc.get('date', '')} | {fc.get('dayweather', '')} | "
                f"{fc.get('nightweather', '')} | "
                f"{fc.get('daytemp', '')}°C / {fc.get('nighttemp', '')}°C |"
            )
        lines.append("")

    routes = amap.get("routes") or []
    if routes:
        lines.append("### 路线（高德 MCP）")
        lines.append("")
        for r in routes:
            if isinstance(r, dict):
                origin = str(r.get("origin_name") or "").strip()
                dest = str(r.get("dest_name") or "").strip()
                q = quote(f"{origin} {dest}".strip())
                link = f"https://www.amap.com/search?query={q}" if q else ""
                suffix = f"（[在高德查看]({link})）" if link else ""
                lines.append(
                    f"- **[{r.get('id', 'AMAP-R')}]** {r.get('summary', '')}{suffix}"
                )
        lines.append("")

    pois = amap.get("pois") or []
    if pois:
        lines.append("### 景点 POI（高德 MCP）")
        lines.append("")
        for p in pois[:12]:
            if isinstance(p, dict):
                lines.append(
                    f"- **[{p.get('id', 'AMAP-P')}]** {p.get('name', '')} · "
                    f"{p.get('address', '') or '（无地址）'}"
                )
        lines.append("")

    rag = facts.get("rag") or []
    rag_meta = facts.get("rag_meta") or {}
    if rag:
        lines.append("### 知识库检索（RAG MCP）")
        lines.append("")
        for item in rag:
            if not isinstance(item, dict):
                continue
            head = f"#### [{item.get('id', 'RAG')}]"
            if item.get("source_doc"):
                head += f" {item['source_doc']}"
            if item.get("score"):
                head += f" · 相关度 {item['score']}"
            lines.append(head)
            if item.get("collection"):
                lines.append(f"- 集合：`{item['collection']}` · 检索词：{item.get('query', '')}")
            lines.append(f"> {item.get('excerpt', '')}")
            lines.append("")
    elif isinstance(rag_meta, dict) and rag_meta.get("notice"):
        lines.append("### 知识库检索（RAG MCP）")
        lines.append("")
        lines.append(f"> {rag_meta['notice']}")
        lines.append("")

    rows = build_dual_source_rows(facts)
    if rows and facts.get("phase") == "poi_selection":
        lines.append("### 双源对照（高德 × 知识库）")
        lines.append("")
        lines.append("| 景点 | 高德 | 知识库 | 地址 |")
        lines.append("|------|------|--------|------|")
        for row in rows:
            lines.append(
                f"| {row.get('景点', '')} | {row.get('高德', '')} | "
                f"{row.get('知识库', '')} | {row.get('地址', '')} |"
            )
        lines.append("")

    errors = facts.get("errors") or []
    if errors:
        lines.append("### 预取提示")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)


def _has_heading(md: str, heading: str) -> bool:
    return bool(md and heading and f"## {heading}" in md)


# 目的地关键词 → (诗句, 作者)；匹配到则用诗句 + 一句祝福
_POETRY_BY_KEYWORD: list[tuple[tuple[str, ...], str, str]] = [
    (("洛阳", "龙门", "老君山"), "欲知千古兴衰事，请君只看洛阳城。", "邵雍"),
    (("杭州", "西湖"), "欲把西湖比西子，淡妆浓抹总相宜。", "苏轼"),
    (("桂林", "阳朔"), "桂林山水甲天下，玉碧罗青万点山。", "黄庭坚"),
    (("大理", "苍山", "洱海"), "风花雪月大理城，苍山洱海入画屏。", ""),  # 化用，非严格古诗
    (("丽江",), "玉龙雪岭接云天，古城灯火照千年。", ""),
    (("西安", "长安"), "春风得意马蹄疾，一日看尽长安花。", "孟郊"),
    (("成都",), "晓看红湿处，花重锦官城。", "杜甫"),
    (("南京",), "六朝旧事随流水，但寒烟衰草凝绿。", "王安石"),
    (("苏州",), "姑苏城外寒山寺，夜半钟声到客船。", "张继"),
    (("厦门",), "鼓浪潮声连碧海，鹭岛花开满城春。", ""),
]


def _opening_lines_for_destination(destination: str) -> list[str]:
    dest = (destination or "").strip() or "此行"
    for keys, poem, author in _POETRY_BY_KEYWORD:
        if any(k in dest for k in keys):
            cite = f" ——{author}" if author else ""
            return [
                f"> 「{poem}」{cite}",
                f"> 祝你在 **{dest}** 一路顺遂，所见皆风景。",
                "",
            ]
    return [
        f"> 祝你在 **{dest}** 的每一步都走得从容，所见皆风景。",
        "> 行程不必赶满，留一点空白给惊喜与好天气。",
        "",
    ]


def add_friendly_intro(md: str, *, destination: str) -> str:
    """
    在标题后插入开场：有匹配古诗则「诗句 + 祝福」，否则用通用祝福句。
    仅应在完整攻略正文上调用（generating/revision）。
    """
    text = (md or "").lstrip()
    if not text.startswith("#"):
        return md
    lines = text.splitlines()
    if not lines:
        return md
    # 已有引用块/开场文案则不重复插入（模型可能已按规范写了祝福/氛围句）
    head = "\n".join(lines[:18])
    if re.search(r"^>\s*", head, flags=re.MULTILINE):
        # 只要开头已有引用块，就认为用户已看到开场，不再二次插入
        return md
    if any(k in head for k in ("祝你在", "愿你在", "所见皆风景", "行程不必赶满")):
        return md
    dest = (destination or "").strip() or "这座城市"
    intro = _opening_lines_for_destination(dest)
    return "\n".join([lines[0], ""] + intro + lines[1:]).rstrip() + "\n"


def format_travel_plan_display(
    md: str,
    facts: TravelFacts | None,
    *,
    destination: str = "",
) -> str:
    """
    攻略交付后处理：仅做依赖 MCP 数据的增强（地图链接/路线表、可信度标注）与开场祝福。
    章节 emoji 由生成阶段 prompt 固定，不在此替换。
    """
    import travel_mode as tm

    raw = (md or "").strip()
    if not raw or not tm.looks_like_travel_plan(raw):
        return md
    text = tm.normalize_travel_plan_body(raw)
    if not text:
        text = raw
    dest = destination or (facts or {}).get("destination", "") if isinstance(facts, dict) else destination
    text = add_friendly_intro(text, destination=str(dest or ""))
    text = augment_map_and_daily_routes(text, facts)
    text = apply_confidence_annotations(text, facts)
    return text


# 保留供旧导出/测试兼容；新生成应走 prompt 固定 emoji
def add_soft_emojis(md: str) -> str:
    return md or ""


def _amap_nav_link(origin: str, dest: str = "") -> str:
    """
    生成「起点 → 终点」的高德导航链接（不再把两地拼成搜索词）。

    说明：使用 `uri.amap.com/navigation`，允许 from/to 传入地点名称；
    若缺失终点，则回退为单点搜索页。
    """
    # 该函数仅用于兜底（名称搜索 / marker）。真正导航优先用经纬度版本（见 _amap_nav_link_with_loc）。
    o = (origin or "").strip()
    d = (dest or "").strip()
    if not o and not d:
        return ""
    if d:
        return f"https://www.amap.com/search?query={quote(d)}"
    return f"https://www.amap.com/search?query={quote(o)}"


def _amap_nav_link_with_loc(*, origin: str, origin_loc: str, dest: str, dest_loc: str) -> str:
    """
    高德 URI 路径规划：from/to 需要 lon,lat[,name]。
    文档：https://developer.amap.com/api/uri-api/guide/travel/route
    """
    o = (origin or "").strip()
    d = (dest or "").strip()
    ol = (origin_loc or "").strip()
    dl = (dest_loc or "").strip()
    if not (o and d and ol and dl):
        return ""
    # 规范化 "lon,lat"
    if "," not in ol or "," not in dl:
        return ""
    from_pos = quote(f"{ol},{o}")
    to_pos = quote(f"{dl},{d}")
    return (
        "https://uri.amap.com/navigation?"
        f"from={from_pos}&to={to_pos}&coordinate=gaode&mode=car&policy=1&callnative=0"
    )


def _amap_marker_link(*, name: str, loc: str) -> str:
    n = (name or "").strip()
    l = (loc or "").strip()
    if not n and not l:
        return ""
    if l and "," in l:
        return f"https://uri.amap.com/marker?position={quote(l)}&name={quote(n or '目的地')}&coordinate=gaode&callnative=0"
    return f"https://www.amap.com/search?query={quote(n)}" if n else ""


def _format_daily_route_table(route: RouteFact) -> str:
    origin = str(route.get("origin_name") or "").strip()
    dest = str(route.get("dest_name") or "").strip()
    link = (
        _amap_nav_link_with_loc(
            origin=origin,
            origin_loc=str(route.get("origin_loc") or ""),
            dest=dest,
            dest_loc=str(route.get("dest_loc") or ""),
        )
        or _amap_nav_link(origin, dest)
    )
    dist = route.get("distance_km")
    dur = route.get("duration_min")
    nav = f"[在高德查看]({link})" if link else "—"
    rid = route.get("id", "AMAP-R")
    header = f"**本日路线参考**（🟢 MCP 依据：高德路线 [{rid}]）\n\n"
    # 若距离/时长缺失，不展示该列，避免一排 “— / —” 降低观感
    if dist is None or dur is None:
        return (
            header
            + "| 路段 | 导航 |\n"
            + "|------|------|\n"
            + f"| {origin} → {dest} | {nav} |\n"
        )
    dist_str = f"约{dist}km"
    dur_str = f"{dur}分钟"
    return (
        header
        + "| 路段 | 距离/时长 | 导航 |\n"
        + "|------|----------|------|\n"
        + f"| {origin} → {dest} | {dist_str} / {dur_str} | {nav} |\n"
    )


_DAY_HEADING_RE = re.compile(
    r"^## (?:Day\s+(\d+)|第(\d+)天)[^\n]*",
    re.MULTILINE | re.IGNORECASE,
)
_MAP_HEADINGS = ("## 🗺️ 行程地图参考", "## 行程地图参考")


def _effective_routes(facts: TravelFacts | None) -> list[RouteFact]:
    """优先用高德路线；无路线时用 POI 串联生成可点导航链接。"""
    if not facts:
        return []
    routes = list((facts.get("amap") or {}).get("routes") or [])
    if routes:
        return [r for r in routes if isinstance(r, dict)]
    pois = (facts.get("amap") or {}).get("pois") or []
    out: list[RouteFact] = []
    for i in range(min(len(pois) - 1, 3)):
        a, b = pois[i], pois[i + 1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        origin = str(a.get("name") or "").strip()
        dest = str(b.get("name") or "").strip()
        if not origin or not dest:
            continue
        out.append(
            {
                "id": f"AMAP-R{len(out) + 1}",
                "mode": "search",
                "origin_name": origin,
                "dest_name": dest,
                "distance_km": None,
                "duration_min": None,
                "summary": f"{origin}→{dest}",
            }
        )
    return out


def _poi_location_index(facts: TravelFacts | None) -> dict[str, str]:
    """name -> 'lon,lat'"""
    if not facts:
        return {}
    idx: dict[str, str] = {}
    for p in (facts.get("amap") or {}).get("pois") or []:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        loc = str(p.get("location") or "").strip()
        if name and loc and "," in loc and name not in idx:
            idx[name] = loc
    return idx


_MAP_DAY_LINE_RE = re.compile(
    r"^\s*-\s*\*\*\s*Day\s*(\d+)[^：:\n]*[：:]\s*\*\*\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def _strip_inline_refs(s: str) -> str:
    """去掉 [AMAP-PN] 之类的角标与括号备注，保留地点名。"""
    t = re.sub(r"\[[^\]]+\]", "", s or "")
    t = re.sub(r"（[^）]*）", "", t)
    t = re.sub(r"\([^)]*\)", "", t)
    return re.sub(r"\s+", " ", t).strip(" -·")


def _extract_day_waypoints_from_map_section(md: str) -> dict[int, list[str]]:
    """
    从「行程地图参考」章节提取每一天的动线站点列表。
    以正文为准，确保和每日行程对齐，而不是使用预取 routes 的任意顺序。
    """
    if not md:
        return {}
    heading = next((h for h in _MAP_HEADINGS if h in md), None)
    if not heading:
        return {}
    start = md.find(heading)
    rest = md[start + len(heading) :]
    next_sec = re.search(r"\n## ", rest)
    section = rest[: next_sec.start()] if next_sec else rest
    out: dict[int, list[str]] = {}
    for m in _MAP_DAY_LINE_RE.finditer(section):
        try:
            day = int(m.group(1))
        except ValueError:
            continue
        route_text = _strip_inline_refs(m.group(2))
        # 支持 "A → B → C" 或 "A->B->C"
        parts = [p.strip() for p in re.split(r"\s*(?:→|->)\s*", route_text) if p.strip()]
        if len(parts) < 2:
            continue
        out[day] = parts
    return out


def _looks_like_lodging(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return False
    return any(k in s for k in ("酒店", "住宿", "民宿", "客栈", "宾馆"))


def _format_daily_waypoint_table(*, day: int, waypoints: list[str], facts: TravelFacts | None) -> str:
    """
    每日“路线参考表”：按站点顺序给单点跳转（酒店/住宿等未知地址用占位符）。
    """
    loc_idx = _poi_location_index(facts)
    lines: list[str] = []
    lines.append("**本日路线参考（单点跳转）**")
    lines.append("")
    lines.append("| 顺序 | 站点 | 导航 |")
    lines.append("|------|------|------|")
    for i, name in enumerate(waypoints, start=1):
        n = (name or "").strip()
        if not n:
            continue
        if _looks_like_lodging(n):
            nav = "—"
        else:
            loc = loc_idx.get(n, "")
            link = _amap_marker_link(name=n, loc=loc) or _amap_nav_link(n, "")
            nav = f"[在高德查看]({link})" if link else "—"
        lines.append(f"| {i} | {n} | {nav} |")
    lines.append("")
    return "\n".join(lines)


def augment_map_and_daily_routes(md: str, facts: TravelFacts | None) -> str:
    """在地图章补充可点链接，并在每日行程标题下插入路线表。"""
    if not md:
        return md
    day_waypoints = _extract_day_waypoints_from_map_section(md)

    out = md

    # 每日行程：在 Day / 第N天 标题后插入路线参考表（按地图章站点顺序）
    matches = list(_DAY_HEADING_RE.finditer(out))
    if not matches:
        return out
    inserts: list[tuple[int, str]] = []
    for m in matches:
        day_raw = m.group(1) or m.group(2) or ""
        try:
            day_num = int(day_raw)
        except ValueError:
            continue
        waypoints = day_waypoints.get(day_num)
        if not waypoints:
            continue
        block = _format_daily_waypoint_table(day=day_num, waypoints=waypoints, facts=facts)
        lookahead = out[m.end() : m.end() + 80]
        if "本日路线参考" in lookahead:
            continue
        inserts.append((m.end(), "\n\n" + block))

    if not inserts:
        return out
    for pos, text in sorted(inserts, key=lambda x: x[0], reverse=True):
        out = out[:pos] + text + out[pos:]
    return out


_CONFIDENCE_LEGEND = """---
**可信度三色标说明**
- 🟢 **MCP 依据**：括号内标注数据来源，如「高德天气预报」「高德路线规划」。
- 🟡 **部分依据**：结合了 MCP 数据与模型整理，请对照文末「数据依据」附录。
- ⚪ **待核实**：系统未能从 MCP/RAG 获取该项，出行前请自行确认。
"""


def apply_confidence_annotations(md: str, facts: TravelFacts | None) -> str:
    """
    少量行内可信度说明 + 文末图例；不对整章标题打黄/白标。
    """
    if not md:
        return md

    out = re.sub(r"^## [🟢🟡⚪] ", "## ", md, flags=re.MULTILINE)

    if facts:
        amap = facts.get("amap") or {}
        weather = amap.get("weather")
        rag_meta = facts.get("rag_meta") or {}

        if isinstance(weather, dict) and weather.get("forecasts"):
            wid = weather.get("id", "AMAP-W")
            note = f"> （🟢 MCP 依据：高德天气预报 [{wid}]）\n"
            for h in ("## 🌤️ 天气与穿搭", "## 天气与穿搭"):
                if h in out and "MCP 依据：高德天气" not in out:
                    out = out.replace(h, h + "\n\n" + note, 1)
                    break
        elif "## 天气与穿搭" in out or "## 🌤️ 天气与穿搭" in out:
            note = "> （🟡 部分依据：天气为模型根据季节规律整理，请以高德实时预报为准）\n"
            for h in ("## 🌤️ 天气与穿搭", "## 天气与穿搭"):
                if h in out and "部分依据：天气" not in out:
                    out = out.replace(h, h + "\n\n" + note, 1)
                    break

        routes = _effective_routes(facts)
        if routes:
            note = "> （🟢 MCP 依据：高德 POI/坐标，用于生成单点跳转链接）\n"
            for h in _MAP_HEADINGS:
                if h in out and "MCP 依据：高德路线" not in out:
                    out = out.replace(h, h + "\n\n" + note, 1)
                    break

        if isinstance(rag_meta, dict) and rag_meta.get("passed_count", -1) == 0:
            notice = str(rag_meta.get("notice") or "").strip()
            if notice and len(notice) > 12:
                short = notice if len(notice) <= 56 else notice[:56] + "…"
                note = f"> （⚪ 待核实：知识库未命中高相关攻略 )\n"
                for h in ("## 🧩 实用提示", "## 实用提示"):
                    if h in out and "知识库未命中" not in out:
                        out = out.replace(h, h + "\n\n" + note, 1)
                        break

    if "可信度三色标说明" not in out:
        out = out.rstrip() + "\n\n" + _CONFIDENCE_LEGEND.strip() + "\n"
    return out


# 兼容旧名
apply_confidence_badges = apply_confidence_annotations
