#!/usr/bin/env python3
"""扫描 wiki/ 下的 frontmatter，产出三类产物并校验链接。

用法：
    python3 wiki/scripts/build_index.py             # 生成 llms.txt + index.html + 同步 README 清单 + 校验
    python3 wiki/scripts/build_index.py --check     # 仅校验，不写任何文件
    python3 wiki/scripts/build_index.py --no-html   # 跳过 HTML 站点生成
    python3 wiki/scripts/build_index.py --open      # 生成后用浏览器打开 index.html

产物：
    1. wiki/llms.txt        —— LLM 导航清单（按域分组，含每页 id）
    2. wiki/index.html      —— 单文件可视化站点（零依赖，双击即看；含搜索与 [[id]] 跳转）
    3. 根 README.md 中 <!-- WIKI-DOC-LIST --> 标记区块 —— 文档清单，消除手动同步的静默失效

校验：
    - [[id]] 死链
    - markdown 相对链接（含锚点）失效

仅依赖标准库，无需安装第三方包。
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import webbrowser
from pathlib import Path

WIKI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = WIKI_DIR.parent
OUTPUT = WIKI_DIR / "llms.txt"
HTML_OUTPUT = WIKI_DIR / "index.html"
README = REPO_ROOT / "README.md"

DOC_LIST_START = "<!-- WIKI-DOC-LIST:START -->"
DOC_LIST_END = "<!-- WIKI-DOC-LIST:END -->"

DOMAIN_TITLES = {
    "00-overview": "Overview 全局",
    "10-host": "Host (agents-master)",
    "20-rag": "RAG (rag-server)",
    "30-integration": "Integration 跨子系统",
    "40-decisions": "Decisions 架构决策",
    "50-analysis": "Analysis 测试与优化",
}

DOMAIN_READMES = {
    "00-overview": "项目定位、术语表、仓库地图",
    "10-host": "Host 域：架构 / 中间件 / ReAct / MCP / 模式 / Prompt / 记忆 / 旅行",
    "20-rag": "RAG 域：架构 / 需求 / 流程 / MCP Server / 评估 / 控制台",
    "30-integration": "跨子系统：端到端链路、配置密钥、生命周期、排障",
    "40-decisions": "ADR 架构决策记录",
    "50-analysis": "测试与优化分析",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
REL_LINK_RE = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)")
SKIP_NAMES = {"README.md", "llms.txt"}

# 静态入口，始终置于 llms.txt 顶部
ENTRY_PAGES = [
    ("总索引与使用约定", "wiki/README.md", "从人读视角进入 wiki"),
    ("可视化站点", "wiki/index.html", "浏览器打开，带侧栏与搜索"),
    ("页面模板", "wiki/_templates/page.md", "新建页面的骨架"),
]


# --------------------------------------------------------------------------- #
# frontmatter 与页面收集
# --------------------------------------------------------------------------- #
def parse_frontmatter(text: str) -> dict:
    """极简 frontmatter 解析：只取顶层标量与列表，够本 wiki 用。"""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict = {}
    key = None
    for raw in match.group(1).splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("- ") and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(raw.lstrip()[2:].strip().strip("'\""))
            continue
        if ":" in raw:
            key, _, val = raw.partition(":")
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                data[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            elif val:
                data[key] = val.strip("'\"")
            else:
                data[key] = []
    return data


def _sort_key(path: Path):
    """域内让 index.md 排首位，其余按文件名。"""
    rel = path.relative_to(WIKI_DIR)
    return (str(rel.parent), 0 if path.name == "index.md" else 1, path.name)


def collect_pages() -> list[dict]:
    pages = []
    for path in sorted(WIKI_DIR.rglob("*.md"), key=_sort_key):
        if "_templates" in path.parts or path.name in SKIP_NAMES:
            continue
        rel = path.relative_to(WIKI_DIR)
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm:
            # 无 frontmatter 的文件（如域索引在补元数据前）暂不收录
            continue
        pages.append(
            {
                "id": fm.get("id") or str(rel.with_suffix("")),
                "title": fm.get("title") or path.stem,
                "path": f"wiki/{rel}",
                "domain": rel.parts[0] if len(rel.parts) > 1 else "",
                "updated": fm.get("updated", ""),
                "body": FRONTMATTER_RE.sub("", text, count=1),
            }
        )
    return pages


def group_by_domain(pages: list[dict]) -> list[tuple[str, str, list[dict]]]:
    """返回 [(域目录名, 域标题, 页面列表)]，跳过空域。"""
    out = []
    for domain, title in DOMAIN_TITLES.items():
        group = [p for p in pages if p["domain"] == domain]
        if group:
            out.append((domain, title, group))
    return out


# --------------------------------------------------------------------------- #
# llms.txt
# --------------------------------------------------------------------------- #
def build_llms_txt(pages: list[dict]) -> str:
    lines = [
        "# ContextBridge Agent — LLM Wiki",
        "",
        "> monorepo 项目知识库：agents-master (Host) + rag-server (RAG)，按原子化页面组织，便于 LLM 检索。",
        "> 用法：读本清单拿到「标题 + id + 路径」，判断相关页后直接读该文件；正文内 [[id]] 可交叉跳转。",
        "",
        "## 入口",
        "",
    ]
    for title, path, desc in ENTRY_PAGES:
        lines.append(f"- [{title}]({path}): {desc}")
    lines.append("")
    for _, title, group in group_by_domain(pages):
        lines.append(f"## {title}")
        for page in group:
            lines.append(f"- [{page['title']}]({page['path']}): id={page['id']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# README 文档清单（标记区块自动同步）
# --------------------------------------------------------------------------- #
def build_doc_list(pages: list[dict]) -> str:
    lines = [
        "> 项目知识库已重构为 **wiki**（一页一主题、可交叉链接、可溯源到代码）。",
        "> 人类入口 [`wiki/README.md`](wiki/README.md) · LLM 入口 [`wiki/llms.txt`](wiki/llms.txt) · 可视化站点 `wiki/index.html`（浏览器打开，含侧栏与搜索）。",
        ">",
        "> 下方清单由 `python3 wiki/scripts/build_index.py` 自动生成，**请勿手动编辑本区块**。",
        "",
    ]
    for domain, title, group in group_by_domain(pages):
        lines.append(f"- **{domain} · {title}**（{DOMAIN_READMES.get(domain, '')}）")
        for page in group:
            lines.append(f"  - [`{page['path']}`]({page['path']}) — {page['title']}")
    return "\n".join(lines)


def sync_readme(pages: list[dict]) -> str | None:
    """把自动清单写入 README 标记区块。返回写入的相对路径，未变动或无标记则返回 None。"""
    if not README.exists():
        return None
    text = README.read_text(encoding="utf-8")
    if DOC_LIST_START not in text or DOC_LIST_END not in text:
        return None
    pattern = re.escape(DOC_LIST_START) + r".*?" + re.escape(DOC_LIST_END)
    block = f"{DOC_LIST_START}\n{build_doc_list(pages)}\n{DOC_LIST_END}"
    new_text = re.sub(pattern, lambda _m: block, text, flags=re.DOTALL)
    if new_text == text:
        return None
    README.write_text(new_text, encoding="utf-8")
    return str(README.relative_to(REPO_ROOT))


# --------------------------------------------------------------------------- #
# Markdown → HTML（零依赖轻量渲染，只覆盖本 wiki 用到的语法）
# --------------------------------------------------------------------------- #
def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _starts_block(lines: list[str], i: int) -> bool:
    line = lines[i]
    if line.startswith("```"):
        return True
    if re.match(r"^#{1,6}\s", line):
        return True
    if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", line):
        return True
    if line.lstrip().startswith((">", "|")):
        return True
    if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
        return True
    return False


def render_inline(text: str, id_to_path: dict) -> str:
    stash: list[str] = []

    def keep_code(m):
        stash.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(stash) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = html.escape(text, quote=False)

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img alt="\1" src="\2">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: _wikilink(m.group(1), id_to_path), text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


def _wikilink(target: str, id_to_path: dict) -> str:
    esc = html.escape(target, quote=True)
    if target not in id_to_path:
        return f'<span class="deadlink" title="未解析的 [[id]]">[[{html.escape(target)}]]</span>'
    return f'<a class="wikilink" href="#{esc}" data-target="{esc}">{html.escape(target)}</a>'


def _render_list(lines: list[str], i: int, id_to_path: dict) -> tuple[str, int]:
    n = len(lines)
    base_indent = len(lines[i]) - len(lines[i].lstrip())
    ordered = bool(re.match(r"^\s*\d+\.\s+", lines[i]))
    items: list[list] = []

    while i < n:
        line = lines[i]
        if not line.strip():
            nxt = lines[i + 1] if i + 1 < n else ""
            same_level = len(nxt) - len(nxt.lstrip()) == base_indent if nxt.strip() else False
            if same_level and re.match(r"^\s*([-*+]|\d+\.)\s+", nxt):
                i += 1
                continue
            break
        indent = len(line) - len(line.lstrip())
        if indent < base_indent:
            break
        m = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", line)
        if m and indent == base_indent:
            items.append([m.group(2), []])
            i += 1
        elif items and indent > base_indent:
            items[-1][1].append(line)
            i += 1
        else:
            break

    tag = "ol" if ordered else "ul"
    parts = [f"<{tag}>"]
    for text, sub in items:
        inner = render_inline(text, id_to_path)
        if sub:
            inner += render_markdown("\n".join(sub), id_to_path)
        parts.append(f"<li>{inner}</li>")
    parts.append(f"</{tag}>")
    return "\n".join(parts), i


def render_markdown(text: str, id_to_path: dict) -> str:
    lines = text.splitlines()
    n = len(lines)
    out: list[str] = []
    i = 0

    while i < n:
        line = lines[i]

        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结束围栏
            code = "\n".join(buf)
            if lang == "mermaid":
                out.append(f'<pre class="mermaid">{html.escape(code)}</pre>')
            else:
                cls = f' class="language-{html.escape(lang)}"' if lang else ""
                out.append(f"<pre><code{cls}>{html.escape(code)}</code></pre>")
            continue

        if not line.strip():
            i += 1
            continue

        if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", line):
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{render_inline(m.group(2), id_to_path)}</h{lvl}>")
            i += 1
            continue

        if line.lstrip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = _split_row(line)
            i += 2
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            thead = "".join(f"<th>{render_inline(c, id_to_path)}</th>" for c in header)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{render_inline(c, id_to_path)}</td>" for c in r) + "</tr>" for r in rows
            )
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>")
            continue

        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f'<blockquote>{render_markdown("\n".join(buf), id_to_path)}</blockquote>')
            continue

        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            block, i = _render_list(lines, i, id_to_path)
            out.append(block)
            continue

        buf = []
        while i < n and lines[i].strip() and not _starts_block(lines, i):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{render_inline(' '.join(buf), id_to_path)}</p>")

    return "\n".join(out)


# --------------------------------------------------------------------------- #
# 单文件 HTML 站点
# --------------------------------------------------------------------------- #
HTML_STYLE = """
:root{--bg:#fff;--fg:#1f2328;--muted:#656d76;--border:#d1d9e0;--accent:#0969da;--code:#f6f8fa;--side:#f6f8fa;--mark:#fff8c5}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--border:#30363d;--accent:#58a6ff;--code:#161b22;--side:#010409;--mark:#3b2300}}
*{box-sizing:border-box}
body{margin:0;display:flex;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--fg);line-height:1.75}
.sidebar{position:fixed;top:0;left:0;width:290px;height:100vh;overflow-y:auto;background:var(--side);border-right:1px solid var(--border);padding:14px 12px 40px}
.brand{font-weight:700;font-size:15px;padding:6px 8px 10px;border-bottom:1px solid var(--border);margin-bottom:10px}
.brand small{display:block;font-weight:400;color:var(--muted);font-size:12px;margin-top:2px}
#filter{width:100%;padding:7px 10px;margin-bottom:12px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--fg);font-size:13px}
.nav-title{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:12px 8px 5px}
.nav-item{display:block;padding:5px 8px;border-radius:6px;color:var(--fg);text-decoration:none;font-size:13.5px;line-height:1.45}
.nav-item:hover{background:var(--code)}
.nav-item.active{background:var(--accent);color:#fff}
.sidebar-foot{margin-top:20px;padding:8px;font-size:11.5px;color:var(--muted);border-top:1px solid var(--border)}
.content{margin-left:290px;padding:44px 52px 100px;max-width:920px}
.page{display:none}
.page.active{display:block}
h1,h2,h3,h4{line-height:1.3;margin:1.6em 0 .6em}
h1{font-size:1.9em;padding-bottom:.3em;border-bottom:1px solid var(--border);margin-top:0}
h2{font-size:1.4em;padding-bottom:.25em;border-bottom:1px solid var(--border)}
h3{font-size:1.15em}
a{color:var(--accent)}
code{background:var(--code);padding:.18em .4em;border-radius:5px;font-size:.88em;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--code);padding:14px 16px;border-radius:8px;overflow-x:auto;border:1px solid var(--border)}
pre code{background:none;padding:0;font-size:.85em;line-height:1.6}
pre.mermaid{background:var(--bg);text-align:center}
blockquote{margin:1em 0;padding:.5em 1em;border-left:3px solid var(--border);color:var(--muted);background:var(--code);border-radius:0 6px 6px 0}
blockquote p{margin:.35em 0}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14px;display:block;overflow-x:auto}
th,td{border:1px solid var(--border);padding:7px 11px;text-align:left;vertical-align:top}
th{background:var(--code);font-weight:600}
hr{border:0;border-top:1px solid var(--border);margin:2em 0}
img{max-width:100%}
ul,ol{padding-left:1.6em}
li{margin:.25em 0}
.wikilink{background:var(--code);padding:.1em .35em;border-radius:5px;text-decoration:none;font-size:.92em}
.wikilink:hover{background:var(--accent);color:#fff}
.deadlink{color:#cf222e;text-decoration:underline wavy}
@media(max-width:900px){
.sidebar{position:static;width:100%;height:auto;border-right:0;border-bottom:1px solid var(--border)}
body{display:block}.content{margin-left:0;padding:24px 18px 60px}
}
"""

HTML_SCRIPT = """
const pages=[...document.querySelectorAll('.page')];
const navItems=[...document.querySelectorAll('.nav-item')];
const rendered=new WeakSet();
function renderMermaid(scope){
  if(!window.mermaid)return;
  for(const el of scope.querySelectorAll('pre.mermaid')){
    if(rendered.has(el))continue;
    rendered.add(el);
    try{window.mermaid.run({nodes:[el]});}catch(e){}
  }
}
function show(id){
  let hit=false;
  for(const p of pages){const on=p.dataset.page===id;p.classList.toggle('active',on);if(on)hit=true;}
  if(!hit)return false;
  for(const a of navItems)a.classList.toggle('active',a.dataset.target===id);
  const active=document.querySelector('.nav-item.active');
  if(active)active.scrollIntoView({block:'nearest'});
  const page=document.querySelector('.page.active');
  if(page)renderMermaid(page);
  return true;
}
function route(){
  const id=decodeURIComponent(location.hash.slice(1));
  if(!id||!show(id)){if(pages.length)show(pages[0].dataset.page);}
  window.scrollTo(0,0);
}
document.addEventListener('click',e=>{
  const a=e.target.closest('a[data-target]');
  if(a){e.preventDefault();location.hash=a.dataset.target;}
});
window.addEventListener('hashchange',route);
window.addEventListener('mermaid-ready',()=>{const p=document.querySelector('.page.active');if(p)renderMermaid(p);});
const filter=document.getElementById('filter');
if(filter){
  filter.addEventListener('input',()=>{
    const q=filter.value.trim().toLowerCase();
    for(const a of navItems){
      const hit=!q||a.textContent.toLowerCase().includes(q)||a.dataset.target.toLowerCase().includes(q);
      a.style.display=hit?'':'none';
    }
    for(const g of document.querySelectorAll('.nav-group')){
      const any=[...g.querySelectorAll('.nav-item')].some(a=>a.style.display!=='none');
      g.style.display=any?'':'none';
    }
  });
}
route();
"""


def build_html(pages: list[dict], id_to_path: dict) -> str:
    nav = []
    for _, title, group in group_by_domain(pages):
        items = "".join(
            '<a class="nav-item" href="#{i}" data-target="{i}">{t}</a>'.format(
                i=html.escape(p["id"], quote=True), t=html.escape(p["title"])
            )
            for p in group
        )
        nav.append(f'<div class="nav-group"><div class="nav-title">{html.escape(title)}</div>{items}</div>')

    articles = "".join(
        '<article class="page" data-page="{i}">{body}</article>'.format(
            i=html.escape(p["id"], quote=True), body=render_markdown(p["body"], id_to_path)
        )
        for p in pages
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ContextBridge Agent · Wiki</title>
<style>{HTML_STYLE}</style>
</head>
<body>
<aside class="sidebar">
<div class="brand">ContextBridge Agent · Wiki<small>{len(pages)} 页 · 由 build_index.py 生成</small></div>
<input type="search" id="filter" placeholder="筛选页面…" autocomplete="off">
<nav>{''.join(nav)}</nav>
<div class="sidebar-foot">改完 .md 后重跑 <code>python3 wiki/scripts/build_index.py</code> 即可刷新本站点。</div>
</aside>
<main class="content">{articles}</main>
<script type="module">
try{{
  const m=await import('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs');
  window.mermaid=m.default;
  window.mermaid.initialize({{startOnLoad:false,securityLevel:'loose'}});
  window.dispatchEvent(new Event('mermaid-ready'));
}}catch(e){{/* 离线：mermaid 源码原样显示，其余功能不受影响 */}}
</script>
<script>{HTML_SCRIPT}</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# 链接校验
# --------------------------------------------------------------------------- #
def check_links(pages: list[dict]) -> list[str]:
    """返回 [[id]] 死链列表。"""
    ids = {page["id"] for page in pages}
    dead = []
    for page in pages:
        for target in LINK_RE.findall(page["body"]):
            if target not in ids:
                dead.append(f"{page['path']}: 死链 [[{target}]]")
    return dead


def check_relative_links() -> list[str]:
    """校验 markdown 相对链接（含锚点）指向的文件确实存在。

    先按「相对当前文件目录」解析，再退回「相对仓库根」解析；两者都不存在才算失效。
    """
    broken = []
    root = WIKI_DIR.parent
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if "_templates" in path.parts:
            continue
        for target in REL_LINK_RE.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if (path.parent / target).resolve().exists():
                continue
            if (root / target).resolve().exists():
                continue
            broken.append(f"{path.relative_to(root)}: 相对链接失效 -> {target}")
    return broken


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="生成 wiki 索引、HTML 站点并校验链接")
    parser.add_argument("--check", action="store_true", help="仅校验，不写任何文件")
    parser.add_argument("--no-html", action="store_true", help="跳过 HTML 站点生成")
    parser.add_argument("--open", action="store_true", help="生成后用浏览器打开 index.html")
    args = parser.parse_args()

    pages = collect_pages()
    id_to_path = {p["id"]: p["path"] for p in pages}

    if not args.check:
        OUTPUT.write_text(build_llms_txt(pages), encoding="utf-8")
        print(f"已生成 {OUTPUT.relative_to(REPO_ROOT)}（{len(pages)} 页）")

        if not args.no_html:
            HTML_OUTPUT.write_text(build_html(pages, id_to_path), encoding="utf-8")
            size_kb = HTML_OUTPUT.stat().st_size / 1024
            print(f"已生成 {HTML_OUTPUT.relative_to(REPO_ROOT)}（{len(pages)} 页，{size_kb:.0f} KB）")

        synced = sync_readme(pages)
        if synced:
            print(f"已同步文档清单 -> {synced}")
        else:
            print(f"文档清单无变化（或 README 缺少 {DOC_LIST_START} 标记）")

    dead = check_links(pages)
    broken = check_relative_links()

    if broken:
        print(f"\n发现失效的相对链接 {len(broken)} 条：")
        for item in broken:
            print("  -", item)

    if dead:
        print("\n发现死链：")
        for item in dead:
            print("  -", item)

    if dead or broken:
        return 1

    print("链接校验通过（[[id]] 与相对链接均无死链）。")

    if args.open and not args.check and HTML_OUTPUT.exists():
        webbrowser.open(HTML_OUTPUT.resolve().as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
