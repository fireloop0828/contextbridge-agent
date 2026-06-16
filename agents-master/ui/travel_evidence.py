"""旅行模式：系统预取数据展示（与 LLM 正文分层，突出 MCP/RAG）。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from travel_facts import (
    TravelFacts,
    RAG_MIN_SCORE_PERCENT,
    build_dual_source_rows,
    format_provenance_summary,
)


def _fmt_forecast_line(fc: dict[str, Any]) -> str:
    date = fc.get("date", "")
    day_w = fc.get("dayweather", "")
    night_w = fc.get("nightweather", "")
    day_t = fc.get("daytemp", "")
    night_t = fc.get("nighttemp", "")
    return f"**{date}** {day_w} / {night_w} · {day_t}°C ~ {night_t}°C"


def render_provenance_banner(facts: TravelFacts) -> None:
    """顶部横幅：一眼看出本回合用了 MCP/RAG。"""
    st.success(f"🔗 系统预取数据 · {format_provenance_summary(facts)}")


def render_poi_dual_source_table(facts: TravelFacts) -> None:
    """POI 阶段：高德与知识库双源对照表。"""
    rows = build_dual_source_rows(facts)
    if not rows:
        return
    st.markdown("#### 🧭 双源对照（高德地图 × 知识库）")
    st.caption("左侧为高德 POI 检索，右侧为知识库是否提及该景点（非 LLM 推断）。")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_weather_strip(facts: TravelFacts) -> None:
    amap = facts.get("amap") or {}
    weather = amap.get("weather")
    if not isinstance(weather, dict) or not weather.get("forecasts"):
        return
    city = weather.get("city") or facts.get("destination") or ""
    st.markdown(f"#### 🌤️ 天气 [`{weather.get('id', 'AMAP-W')}`] · {city}（高德 MCP）")
    forecasts = [fc for fc in (weather.get("forecasts") or [])[:4] if isinstance(fc, dict)]
    if not forecasts:
        return
    cols = st.columns(len(forecasts))
    for i, fc in enumerate(forecasts):
        with cols[i]:
            st.metric(
                label=str(fc.get("date", "")),
                value=f"{fc.get('daytemp', '?')}°C",
                delta=str(fc.get("dayweather", "")),
            )
            st.caption(f"夜间 {fc.get('nighttemp', '?')}°C · {fc.get('nightweather', '')}")


def render_routes_strip(facts: TravelFacts) -> None:
    routes = (facts.get("amap") or {}).get("routes") or []
    if not routes:
        return
    st.markdown("#### 🛣️ 代表路线（高德 MCP）")
    for r in routes:
        if isinstance(r, dict):
            st.info(f"**[{r.get('id', 'AMAP-R')}]** {r.get('summary', '')}")


def render_rag_strip(facts: TravelFacts) -> None:
    rag = facts.get("rag") or []
    rag_meta = facts.get("rag_meta") or {}
    if not rag:
        if isinstance(rag_meta, dict) and rag_meta.get("notice"):
            st.warning(rag_meta["notice"])
        elif isinstance(rag_meta, dict) and rag_meta.get("raw_count", 0) > 0:
            raw_n = rag_meta.get("raw_count", 0)
            thr = rag_meta.get("threshold_percent", RAG_MIN_SCORE_PERCENT)
            st.warning(
                f"知识库检索到 **{raw_n}** 条，但相关度≥{thr}% 的为 **0** 条，"
                f"已隐藏低相关片段。"
            )
            if rag_meta.get("query"):
                st.caption(f"检索词：{rag_meta['query']}")
        else:
            st.warning("知识库本轮未命中相关内容（RAG 返回为空或无关）。")
        return
    st.markdown(f"#### 📚 知识库检索（RAG MCP · {len(rag)} 条）")
    st.caption("以下为 query_knowledge_hub 返回的原文摘要，可直接核对是否与目的地相关。")
    for item in rag:
        if not isinstance(item, dict):
            continue
        rid = item.get("id", "RAG")
        title = f"**[{rid}]**"
        if item.get("source_doc"):
            title += f" `{item['source_doc']}`"
        if item.get("score"):
            title += f" · 相关度 {item['score']}"
        st.markdown(title)
        meta = []
        if item.get("collection"):
            meta.append(f"集合 `{item['collection']}`")
        if item.get("query"):
            meta.append(f"检索词：{item['query']}")
        if meta:
            st.caption(" · ".join(meta))
        st.markdown(f"> {item.get('excerpt', '')}")


def render_amap_poi_strip(facts: TravelFacts) -> None:
    pois = (facts.get("amap") or {}).get("pois") or []
    if not pois:
        return
    phase = facts.get("phase", "")
    if phase == "poi_selection":
        return  # 双源表已含 POI
    st.markdown(f"#### 📍 景点 POI（高德 MCP · {len(pois)} 个）")
    for p in pois[:8]:
        if isinstance(p, dict):
            st.markdown(
                f"- **[{p.get('id', 'AMAP-P')}]** {p.get('name', '')} · "
                f"{p.get('address', '') or '（无地址）'}"
            )


def render_fetch_errors(facts: TravelFacts) -> None:
    errors = facts.get("errors") or []
    if not errors:
        return
    for err in errors:
        st.caption(f"⚠️ {err}")


def render_ai_narrative_divider() -> None:
    """与系统预取数据区明确分层。"""
    st.divider()
    st.markdown("#### 📝 AI 行程建议")
    st.caption(
        "以下为模型根据上方**系统预取数据**撰写的行程叙述；"
        "天气、路线、知识库原文请以上方为准。"
    )


def render_travel_provenance(
    facts: TravelFacts | dict[str, Any] | None,
    *,
    key_prefix: str = "ev",
    show_divider: bool = True,
    expanded: bool = False,
) -> None:
    """
    渲染系统预取数据区（可折叠，默认收起以节省空间）。
    show_divider=True 时在数据区与 AI 正文之间插入分隔。
    """
    if not facts or not isinstance(facts, dict):
        return
    if not facts.get("rag") and not facts.get("amap"):
        return

    render_provenance_banner(facts)

    with st.expander("🗂️ 系统预取数据（MCP 直出）", expanded=expanded):
        with st.container(border=True):
            phase = facts.get("phase", "")
            if phase == "poi_selection":
                render_poi_dual_source_table(facts)
                render_rag_strip(facts)
            else:
                render_weather_strip(facts)
                render_routes_strip(facts)
                render_amap_poi_strip(facts)
                render_rag_strip(facts)
            render_fetch_errors(facts)

    if show_divider:
        render_ai_narrative_divider()


# 兼容旧调用
def render_travel_evidence(
    facts: TravelFacts | dict[str, Any] | None,
    *,
    key_prefix: str = "ev",
    show_summary: bool = True,
) -> None:
    render_travel_provenance(
        facts,
        key_prefix=key_prefix,
        show_divider=show_summary,
        expanded=False,
    )
