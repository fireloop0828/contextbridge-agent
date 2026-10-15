"""联网搜索 MCP 服务（博查 Web Search API）。

以 stdio 方式对外暴露两个工具，供 ReAct Agent 调用：
- web_search：全网检索，返回标题 / URL / 来源 / 时间 / 摘要
- web_fetch：抓取指定 URL 的正文，用于读取搜索结果的详细内容

环境变量（agents-master/.env）：
    BOCHA_API_KEY           博查 API Key（必填，https://open.bochaai.com 申请）
    BOCHA_SEARCH_ENDPOINT   可选，默认 https://api.bochaai.com/v1/web-search
    WEB_FETCH_MODE          可选，direct（默认，直接抓原站）/ jina（经 r.jina.ai 提取正文）
"""

from __future__ import annotations

import html
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# stdio 子进程由 MCP Client 拉起，环境可能与父进程不同，这里显式加载 .env
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

DEFAULT_ENDPOINT = "https://api.bochaai.com/v1/web-search"
DEFAULT_JINA_ENDPOINT = "https://r.jina.ai/"

# 博查 freshness 支持的枚举值（另支持 YYYY-MM-DD..YYYY-MM-DD 自定义区间）
FRESHNESS_CHOICES = {
    "nolimit": "noLimit",
    "oneday": "oneDay",
    "oneweek": "oneWeek",
    "onemonth": "oneMonth",
    "oneyear": "oneYear",
}
FRESHNESS_ALIASES = {
    "不限": "noLimit",
    "一天内": "oneDay",
    "一周内": "oneWeek",
    "一月内": "oneMonth",
    "一年内": "oneYear",
}
DATE_RANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}$")

MAX_COUNT = 10
MAX_SNIPPET_CHARS = 500
MAX_FETCH_CHARS = 6000
SEARCH_TIMEOUT = 20.0
FETCH_TIMEOUT = 30.0
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

mcp = FastMCP(
    "WebSearchService",
    instructions=(
        "你是联网搜索助手，可检索全网信息并抓取网页正文。"
        "用户询问时事、新闻、最新资料、价格、股价、天气、版本更新等实时信息时，"
        "先用 web_search 检索，需要详情时再用 web_fetch 打开具体 URL，"
        "回答须基于搜索结果并附上来源链接，不要编造。"
    ),
    host="0.0.0.0",  # SSE 模式用，stdio 下无效
    port=8006,
)


def _api_key() -> str:
    key = os.getenv("BOCHA_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "未配置 BOCHA_API_KEY：请在 agents-master/.env 填入博查 API Key 后重启应用。"
        )
    return key


def _normalize_freshness(value: str) -> str:
    """把 freshness 归一化为博查支持的取值；无法识别时抛错。"""
    raw = (value or "noLimit").strip()
    if raw in FRESHNESS_ALIASES:
        return FRESHNESS_ALIASES[raw]
    lowered = raw.lower()
    if lowered in FRESHNESS_CHOICES:
        return FRESHNESS_CHOICES[lowered]
    if DATE_RANGE_RE.match(raw):
        return raw
    raise ValueError(
        f"freshness 取值无效：{raw}。可选 "
        f"{sorted(set(FRESHNESS_CHOICES.values()))}、YYYY-MM-DD..YYYY-MM-DD 或 {list(FRESHNESS_ALIASES)}"
    )


def _clip(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def _extract_results(payload: Any) -> list[dict]:
    """兼容 data.webPages.value 与 webPages.value 两种返回结构。"""
    if not isinstance(payload, dict):
        return []
    node = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    web_pages = node.get("webPages")
    if not isinstance(web_pages, dict):
        return []
    value = web_pages.get("value")
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _format_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"未检索到与「{query}」相关的结果，请更换关键词重试。"

    lines = [f"搜索「{query}」共 {len(results)} 条结果：", ""]
    for idx, item in enumerate(results, start=1):
        title = _clip(str(item.get("name") or item.get("title") or "(无标题)"), 120)
        url = str(item.get("url") or item.get("displayUrl") or "").strip()
        site = str(item.get("siteName") or "").strip()
        date = str(item.get("datePublished") or item.get("dateLastCrawled") or "").strip()
        body = str(item.get("summary") or item.get("snippet") or "").strip()

        lines.append(f"[{idx}] {title}")
        lines.append(f"URL: {url}" if url else "URL: (缺失)")
        meta = " | ".join([x for x in (f"来源：{site}" if site else "", f"时间：{date[:10]}" if date else "") if x])
        if meta:
            lines.append(meta)
        lines.append(f"摘要：{_clip(body, MAX_SNIPPET_CHARS) if body else '(无摘要)'}")
        lines.append("")

    lines.append("如需详情，可对具体 URL 调用 web_fetch。")
    return "\n".join(lines)


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


@mcp.tool()
async def web_search(
    query: str,
    count: int = 5,
    freshness: str = "noLimit",
) -> str:
    """
    联网搜索网页信息，返回标题、链接、来源站点、发布时间与摘要。

    参数:
        query: 搜索关键词，建议简洁并聚焦核心实体
        count: 返回结果条数，1-10，默认 5
        freshness: 时效过滤，可选 noLimit / oneDay / oneWeek / oneMonth / oneYear
                   / YYYY-MM-DD..YYYY-MM-DD / 不限 / 一天内 / 一周内 / 一月内 / 一年内

    返回:
        结构化搜索结果文本；未配置 Key 或调用失败时返回可读的错误说明
    """
    query = (query or "").strip()
    if not query:
        return "错误：query 不能为空。"

    try:
        api_key = _api_key()
        freshness_value = _normalize_freshness(freshness)
    except (RuntimeError, ValueError) as e:
        return f"错误：{e}"

    try:
        count = max(1, min(int(count), MAX_COUNT))
    except (TypeError, ValueError):
        count = 5

    payload = {
        "query": query,
        "count": count,
        "summary": True,
        "freshness": freshness_value,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            resp = await client.post(
                os.getenv("BOCHA_SEARCH_ENDPOINT") or DEFAULT_ENDPOINT,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return "错误：搜索请求超时，请稍后重试或简化关键词。"
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        hint = {
            401: "API Key 无效或已过期",
            403: "API Key 无权限或额度已用尽",
            429: "请求过于频繁，已被限流",
        }.get(status, f"服务端返回 {status}")
        return f"错误：博查搜索失败（{hint}）。"
    except Exception as e:
        return f"错误：搜索请求异常：{e}"

    return _format_results(query, _extract_results(data))


@mcp.tool()
async def web_fetch(url: str, max_chars: int = MAX_FETCH_CHARS) -> str:
    """
    抓取指定 URL 的网页正文，用于查看搜索结果的详细内容。

    参数:
        url: 完整网页地址（需以 http:// 或 https:// 开头）
        max_chars: 正文最大字符数，默认 6000

    返回:
        网页正文文本；失败时返回可读的错误说明
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return "错误：url 需以 http:// 或 https:// 开头。"

    try:
        max_chars = max(500, min(int(max_chars), 20000))
    except (TypeError, ValueError):
        max_chars = MAX_FETCH_CHARS

    use_jina = os.getenv("WEB_FETCH_MODE", "direct").strip().lower() == "jina"
    target = f"{DEFAULT_JINA_ENDPOINT}{url}" if use_jina else url

    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": BROWSER_UA},
        ) as client:
            resp = await client.get(target)
            resp.raise_for_status()
            raw = resp.text
    except httpx.TimeoutException:
        return "错误：抓取超时，该网页响应过慢，可换个来源。"
    except httpx.HTTPStatusError as e:
        return f"错误：抓取失败，服务端返回 {e.response.status_code}。"
    except Exception as e:
        return f"错误：抓取异常：{e}"

    text = raw if use_jina else _strip_html(raw)
    if not text:
        return "错误：未能从该页面提取到正文内容。"

    clipped = _clip(text, max_chars)
    omitted = len(text) - len(clipped)
    suffix = f"\n\n...[正文已截断，省略约 {omitted} 字符]" if omitted > 0 else ""
    return f"URL: {url}\n\n正文：\n{clipped}{suffix}"


if __name__ == "__main__":
    # stdio 通过标准输入/输出与 Client 通信，与 config.json 中的 transport 保持一致
    mcp.run(transport="stdio")
