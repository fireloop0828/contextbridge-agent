"""旅行模式 P0：编排层 MCP 预取（POI / 生成阶段）。"""

from __future__ import annotations

import logging
from typing import Any

from . import state_machine as tm
from .facts import (
    TravelFacts,
    empty_travel_facts,
    finalize_facts,
    parse_amap_pois,
    parse_amap_route,
    parse_amap_weather,
    parse_geo_location,
    parse_rag_results,
    pick_rag_collection,
    prioritize_rag_by_destination,
    set_travel_facts,
    tool_result_to_text,
)
from .tool_memory import get_cached_rag_collections, try_cache_rag_collections_from_tool_output

logger = logging.getLogger(__name__)

MAX_ROUTES = 3
MAX_GEO_CALLS = 4


def _tools_by_name(tools: list[Any]) -> dict[str, Any]:
    return {getattr(t, "name", ""): t for t in tools if getattr(t, "name", None)}


async def _call_tool(tools_map: dict[str, Any], name: str, args: dict[str, Any]) -> Any:
    tool = tools_map.get(name)
    if not tool:
        raise RuntimeError(f"工具未连接：{name}")
    return await tool.ainvoke(args)


async def _fetch_rag(
    tools_map: dict[str, Any],
    *,
    query: str,
    top_k: int = 5,
    collection: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    args: dict[str, Any] = {"query": query, "top_k": top_k}
    if collection:
        args["collection"] = collection
    raw = await _call_tool(tools_map, "query_knowledge_hub", args)
    items, meta = parse_rag_results(raw, query=query, collection=collection)
    return items, meta


async def _ensure_collections(tools_map: dict[str, Any]) -> list[str]:
    cached = get_cached_rag_collections()
    if cached:
        return cached
    if "list_collections" not in tools_map:
        return []
    try:
        raw = await _call_tool(tools_map, "list_collections", {"include_stats": True})
        try_cache_rag_collections_from_tool_output(tool_result_to_text(raw))
    except Exception as exc:
        logger.warning("list_collections failed: %s", exc)
    return get_cached_rag_collections()


def _route_tool_name(transport: str) -> str:
    t = (transport or "").strip()
    if "自驾" in t or "开车" in t:
        return "maps_direction_driving"
    if "公交" in t or "地铁" in t or "公共交通" in t:
        return "maps_direction_transit_integrated"
    return "maps_direction_driving"


async def _geo_location(
    tools_map: dict[str, Any],
    *,
    address: str,
    city: str,
) -> str | None:
    if "maps_geo" not in tools_map:
        return None
    query_address = address.strip()
    if city and city not in query_address:
        query_address = f"{city}{query_address}"
    args: dict[str, Any] = {"address": query_address}
    if city:
        args["city"] = city
    raw = await _call_tool(tools_map, "maps_geo", args)
    return parse_geo_location(raw)


async def _fetch_routes(
    tools_map: dict[str, Any],
    *,
    poi_names: list[str],
    city: str,
    transport: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    route_tool = _route_tool_name(transport)
    if route_tool not in tools_map:
        errors.append(f"路线工具不可用：{route_tool}")
        return []

    names = [n.strip() for n in poi_names if n and n.strip()]
    if len(names) < 2:
        return []

    coords: list[tuple[str, str]] = []
    for name in names[: MAX_GEO_CALLS + 1]:
        try:
            loc = await _geo_location(tools_map, address=name, city=city)
            if loc:
                coords.append((name, loc))
        except Exception as exc:
            errors.append(f"地理编码失败({name})：{exc}")

    routes: list[dict[str, Any]] = []
    pairs = list(zip(coords, coords[1:]))[:MAX_ROUTES]
    for idx, ((origin_name, origin_loc), (dest_name, dest_loc)) in enumerate(
        pairs, start=1
    ):
        try:
            raw = await _call_tool(
                tools_map,
                route_tool,
                {"origin": origin_loc, "destination": dest_loc},
            )
            route = parse_amap_route(
                raw,
                route_id=f"AMAP-R{idx}",
                mode=route_tool.replace("maps_direction_", ""),
                origin_name=origin_name,
                dest_name=dest_name,
                origin_loc=origin_loc,
                dest_loc=dest_loc,
            )
            if route:
                routes.append(route)
        except Exception as exc:
            errors.append(f"路线规划失败({origin_name}→{dest_name})：{exc}")
    return routes


async def fetch_facts_for_poi_selection(
    intake: dict[str, Any],
    tools: list[Any],
) -> TravelFacts:
    dest = (intake.get("destination") or "").strip()
    facts = empty_travel_facts(phase=tm.PHASE_POI_SELECTION, destination=dest)
    if not dest:
        facts["errors"] = ["缺少目的地，跳过预取"]
        return finalize_facts(facts)

    tools_map = _tools_by_name(tools)
    errors: list[str] = facts.setdefault("errors", [])

    collections = await _ensure_collections(tools_map)
    collection = pick_rag_collection(collections)

    try:
        rag, rag_meta = await _fetch_rag(
            tools_map,
            query=f"{dest} 旅游 必玩 景点 攻略",
            top_k=5,
            collection=collection,
        )
        if not rag:
            rag, rag_meta = await _fetch_rag(
                tools_map,
                query=f"{dest} 经典线路 注意事项",
                top_k=4,
                collection=collection,
            )
        facts["rag"] = prioritize_rag_by_destination(rag, dest)
        facts["rag_meta"] = rag_meta
    except Exception as exc:
        errors.append(f"RAG 预取失败：{exc}")

    try:
        raw = await _call_tool(
            tools_map,
            "maps_text_search",
            {"keywords": f"{dest} 必玩 景点", "city": dest},
        )
        facts.setdefault("amap", {})["pois"] = parse_amap_pois(raw)
    except Exception as exc:
        errors.append(f"高德 POI 检索失败：{exc}")

    return finalize_facts(facts)


async def fetch_facts_for_generating(
    intake: dict[str, Any],
    tools: list[Any],
) -> TravelFacts:
    dest = (intake.get("destination") or "").strip()
    days = intake.get("duration_days")
    facts = empty_travel_facts(phase=tm.PHASE_GENERATING, destination=dest)
    if not dest:
        facts["errors"] = ["缺少目的地，跳过预取"]
        return finalize_facts(facts)

    tools_map = _tools_by_name(tools)
    errors: list[str] = facts.setdefault("errors", [])
    amap: dict[str, Any] = facts.setdefault("amap", {"weather": None, "pois": [], "routes": []})

    collections = await _ensure_collections(tools_map)
    collection = pick_rag_collection(collections)
    days_hint = f"{days}日" if days else ""

    try:
        rag, rag_meta = await _fetch_rag(
            tools_map,
            query=f"{dest} {days_hint} 攻略 行程 必玩".strip(),
            top_k=6,
            collection=collection,
        )
        facts["rag"] = prioritize_rag_by_destination(rag, dest)
        facts["rag_meta"] = rag_meta
    except Exception as exc:
        errors.append(f"RAG 预取失败：{exc}")

    try:
        raw = await _call_tool(tools_map, "maps_weather", {"city": dest})
        amap["weather"] = parse_amap_weather(raw)
    except Exception as exc:
        errors.append(f"天气查询失败：{exc}")

    poi_names: list[str] = []
    must_visit = (intake.get("must_visit") or "").strip()
    if must_visit and must_visit not in ("无", "由规划师根据推荐景点安排"):
        poi_names.extend(re_split_poi_names(must_visit)[:4])

    try:
        raw = await _call_tool(
            tools_map,
            "maps_text_search",
            {"keywords": f"{dest} 景点", "city": dest},
        )
        pois = parse_amap_pois(raw)
        amap["pois"] = pois
        for p in pois[:3]:
            name = p.get("name") or ""
            if name and name not in poi_names:
                poi_names.append(name)
    except Exception as exc:
        errors.append(f"高德 POI 检索失败：{exc}")

    transport = (intake.get("transport") or "").strip()
    if len(poi_names) >= 2:
        routes = await _fetch_routes(
            tools_map,
            poi_names=poi_names,
            city=dest,
            transport=transport,
            errors=errors,
        )
        amap["routes"] = routes
    else:
        errors.append("POI 不足，跳过路线预取")

    return finalize_facts(facts)


def re_split_poi_names(text: str) -> list[str]:
    import re

    parts = re.split(r"[、,，/;；\n]+", text)
    return [p.strip() for p in parts if p.strip()]


async def ensure_generating_facts_for_delivery(
    intake: dict[str, Any],
    tools: list[Any],
) -> TravelFacts | None:
    """
    攻略交付前确保 travel_facts 含 generating 阶段的天气/路线（改稿或 POI 阶段 facts 可能过旧）。
    """
    from .facts import get_travel_facts

    facts = get_travel_facts()
    amap = (facts or {}).get("amap") or {}
    if (
        facts
        and facts.get("phase") == tm.PHASE_GENERATING
        and amap.get("weather")
        and amap.get("routes")
    ):
        return facts
    new_facts = await fetch_facts_for_generating(intake, tools)
    set_travel_facts(new_facts)
    return new_facts


async def prefetch_travel_facts(
    *,
    phase: str,
    intake: dict[str, Any],
    tools: list[Any] | None,
) -> TravelFacts | None:
    """
    按阶段预取 MCP 数据并写入 session_state.travel_facts。
    返回 None 表示本阶段无需预取或工具未就绪。
    """
    if not tools:
        return None
    if phase == tm.PHASE_POI_SELECTION:
        facts = await fetch_facts_for_poi_selection(intake, tools)
    elif phase == tm.PHASE_GENERATING:
        facts = await fetch_facts_for_generating(intake, tools)
    elif phase == tm.PHASE_REVISION:
        facts = await ensure_generating_facts_for_delivery(intake, tools)
        return facts
    else:
        return None
    set_travel_facts(facts)
    return facts
