"""MCP Server：将 Agent 生成的 Markdown 成品写入 data/outputs/ 供下载。"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "data" / "outputs"

mcp = FastMCP(
    "DocumentExport",
    instructions=(
        "将用户需要的报告、方案、清单等成品写入 Markdown 文件。"
        "长文、旅行规划、调研总结等适合导出时，在回答完成后调用 write_markdown_document。"
    ),
    host="0.0.0.0",
    port=8006,
)


def _safe_filename(name: str) -> str:
    """生成安全的 .md 文件名（不含路径）。"""
    name = (name or "document").strip()
    name = os.path.basename(name.replace("\\", "/"))
    if not name.lower().endswith(".md"):
        name = f"{name}.md"
    stem, ext = os.path.splitext(name)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
    stem = re.sub(r"\s+", "_", stem).strip("._") or "document"
    return f"{stem}{ext}"


def _build_markdown(title: str, content: str) -> str:
    title = (title or "未命名文档").strip()
    body = (content or "").strip()
    if body.startswith("#"):
        return body + "\n"
    return f"# {title}\n\n{body}\n"


@mcp.tool()
async def write_markdown_document(
    title: str,
    content: str,
    filename: Optional[str] = None,
) -> str:
    """
    将 Markdown 正文写入项目 data/outputs/ 目录，供用户在网页上下载。

    参数:
        title: 文档标题（若 content 未以 # 开头，会自动作为一级标题）
        content: 完整 Markdown 正文（可含表格、列表、二级标题等）
        filename: 可选文件名（如 travel-plan.md）；不传则根据标题与时间自动生成

    返回:
        JSON 字符串，含 ok、path（相对路径）、filename、bytes
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if filename:
        safe_name = _safe_filename(filename)
    else:
        slug = re.sub(r"\s+", "_", (title or "document").strip())[:40]
        slug = re.sub(r'[<>:"/\\|?*]', "_", slug) or "document"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = _safe_filename(f"{ts}_{slug}")

    target = OUTPUT_DIR / safe_name
    if target.exists():
        stem, ext = os.path.splitext(safe_name)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = f"{stem}_{ts}{ext}"
        target = OUTPUT_DIR / safe_name

    markdown = _build_markdown(title, content)
    target.write_text(markdown, encoding="utf-8")

    rel_path = f"data/outputs/{safe_name}"
    return json.dumps(
        {
            "ok": True,
            "path": rel_path,
            "filename": safe_name,
            "bytes": target.stat().st_size,
            "message": f"已保存 Markdown：{rel_path}，请告知用户可在页面点击下载。",
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def list_markdown_exports(limit: int = 10) -> str:
    """
    列出 data/outputs/ 下最近生成的 .md 文件（按修改时间倒序）。

    参数:
        limit: 最多返回条数，默认 10
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        OUTPUT_DIR.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, min(limit, 50))]

    items = [
        {
            "filename": p.name,
            "path": f"data/outputs/{p.name}",
            "size_bytes": p.stat().st_size,
        }
        for p in files
    ]
    return json.dumps({"ok": True, "files": items, "count": len(items)}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
