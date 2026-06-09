"""将 Markdown 写入 data/outputs/（供 UI 自动导出，不消耗 LLM Token）。"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from config.paths import EXPORT_OUTPUT_DIR


def _safe_filename(name: str) -> str:
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


def save_markdown_export(
    content: str,
    *,
    title: str = "旅行攻略",
    filename: str | None = None,
    output_dir: Path | None = None,
) -> str | None:
    """
    写入 Markdown 文件。

    返回:
        相对路径，如 data/outputs/travel-plan-xian.md；失败返回 None。
    """
    body = (content or "").strip()
    if not body:
        return None

    out = output_dir or Path(EXPORT_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(filename) if filename else _safe_filename(title)
    target = out / safe_name
    if target.exists():
        stem, ext = os.path.splitext(safe_name)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = f"{stem}_{ts}{ext}"
        target = out / safe_name

    target.write_text(_build_markdown(title, body), encoding="utf-8")
    return f"data/outputs/{safe_name}"


def travel_export_filename(intake: dict) -> str:
    """根据 intake 目的地生成导出文件名。"""
    dest = (intake.get("destination") or "travel-plan").strip()
    slug = re.sub(r'[<>:"/\\|?*\s]', "_", dest)[:40].strip("_") or "travel-plan"
    return f"travel-plan-{slug}.md"
