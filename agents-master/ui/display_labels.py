"""侧边栏等 UI 用的中文展示名（内部标识仍保留英文 key）。"""

from __future__ import annotations

MCP_SERVER_LABELS: dict[str, str] = {
    "get_current_time": "当前时间",
    "document-export": "文档导出",
    "rag-server": "知识库检索",
    "amap-maps": "高德地图",
    "github": "GitHub 仓库",
    "weather": "天气查询",
    "brave-search": "网页搜索",
    "filesystem": "本地文件",
}


def format_mcp_server_label(server_id: str) -> str:
    if server_id in MCP_SERVER_LABELS:
        return MCP_SERVER_LABELS[server_id]
    lowered = server_id.lower()
    if "amap" in lowered or lowered.endswith("-maps"):
        return "地图服务"
    if "rag" in lowered or "knowledge" in lowered:
        return "知识库检索"
    if "export" in lowered or "document" in lowered:
        return "文档导出"
    if "time" in lowered:
        return "时间服务"
    if "weather" in lowered:
        return "天气查询"
    return server_id.replace("-", " ").replace("_", " ")
