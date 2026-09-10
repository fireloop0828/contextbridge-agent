# ContextBridge Agent · LLM Wiki

> 面向 LLM 检索的项目知识库：**原子化、自足、可交叉链接、可溯源到代码**。
> 人类读者从这里进入，或直接打开可视化站点 `wiki/index.html`；LLM 读者优先读 [`llms.txt`](llms.txt)。

## 这是什么

本项目知识原先分散在根 `README`、两个子项目的 `docs/`、`rag-server/DEV_SPEC.md`、`QA/`、`.cursor/skills/*/references/` 等处，同一主题重复出现且互不引用。本 wiki 将其重构为**一页一主题**的知识网，供人与 Agent 精准检索。

## 使用约定

| 约定 | 规则 |
| --- | --- |
| 一页一主题 | 每页只讲一个概念，标题即答案 |
| 自足 | 页首必须有 `> TL;DR` 一句话摘要，脱离其它页也能读懂 |
| 元数据 | 每页 frontmatter 含 `id` / `title` / `tags` / `sources` / `related` / `updated` |
| 交叉链接 | 正文用 `[[id]]`，页尾「关联」区维护上下游 |
| 溯源 | `sources` 填真实代码路径，答案可回指代码 |
| 命名 | `kebab-case.md`；域目录用 `NN-` 前缀控制排序 |
| 小节结构 | 新写页面用「是什么 / 为什么这样设计 / 怎么实现 / 关键代码锚点 / 关联」；**迁移页保留原有小节编号** |

## 知识域

| 域 | 范围 | 页面 |
| --- | --- | --- |
| 00-overview | 项目定位、术语表、仓库地图 | [project](00-overview/project.md) · [glossary](00-overview/glossary.md) · [repo-map](00-overview/repo-map.md) |
| [10-host](10-host/index.md) | agents-master：架构 / 中间件 / ReAct / MCP / 模式 / Prompt / 记忆 / 旅行 | 9 页 |
| [20-rag](20-rag/index.md) | rag-server：架构 / 需求 / 流程 / MCP Server / 评估 / 控制台 | 6 页 |
| [30-integration](30-integration/index.md) | 跨子系统：端到端链路、配置密钥、生命周期、排障 | 4 页 |
| [40-decisions](40-decisions/index.md) | ADR 架构决策记录 | 4 页 |
| [50-analysis](50-analysis/index.md) | 测试与优化分析 | 9 页 |

## 三种读法

| 读者 | 入口 | 说明 |
| --- | --- | --- |
| 人（浏览） | 浏览器打开 `wiki/index.html` | 单文件站点，左侧栏 + 搜索框，`[[id]]` 可点跳转 |
| 人（编辑） | 直接打开 `wiki/**/*.md` | 纯 Markdown，任意编辑器可改；推荐编辑器全局搜索 |
| LLM / Agent | 先读 [`llms.txt`](llms.txt) | 拿到全站「标题 + id + 路径」清单 → 判断相关页 → 直接读该文件 |

> 本 wiki **没有向量检索**。`llms.txt` 就是检索索引，「按标题命中 + 全文读取」是刻意取舍：零依赖、纯文本可 `git diff`、无索引服务要维护。
> 代价是：你的问题用词若和页面标题对不上，Agent 可能找不到——这正是要求「标题即答案」「每页必须有 TL;DR」的原因。

## 新增或修改页面

### 新增一页（5 步）

1. **复制模板**：`wiki/_templates/page.md` → `wiki/<域>/<kebab-case>.md`
2. **填 frontmatter**：
   - `id` 全局唯一，格式 `<域简写>/<文件名>`，如 `host/prompts`（**不是** `10-host/prompts`）
   - `title` 写「答案」而非「话题」（好：`MCP 客户端与配置管理`；坏：`关于 MCP`）
   - `sources` 填真实代码路径，供溯源；`related` 填关联页 id
3. **写正文**：页首必须有 `> **TL;DR**：…`（一句话自足），再按「是什么 / 为什么这样设计 / 怎么实现 / 关键代码锚点 / 关联」展开
4. **双向互链**：到相关页的 `related` 里补 `[[新id]]`，新页「关联」区写回上游/下游
5. **跑脚本**：`python3 wiki/scripts/build_index.py`

### 修改一页（3 步）

1. 直接改 `.md` 正文
2. 把 frontmatter 的 `updated` 改成当天日期
3. 跑 `python3 wiki/scripts/build_index.py`

### 删除一页（2 步）

1. 删掉 `.md` 文件
2. 搜索其它页里指向它的 `[[id]]` 并清理（脚本会报死链，但不会自动修）→ 跑脚本确认无死链

### 改了会怎样：4 个同步点，3 个自动

| 产物 | 自动？ | 不做的后果 |
| --- | --- | --- |
| `wiki/llms.txt` | ✅ 跑脚本重生成 | **不跑 → 新页不在 llms.txt 里，Agent 导航时完全看不到这页** |
| `wiki/index.html` | ✅ 跑脚本重生成 | 不跑 → 可视化站点看不到这页 |
| 根 `README.md` 文档清单 | ✅ 跑脚本重生成（标记区块内） | 不跑 → README 清单过期 |
| 域索引 `NN-xxx/index.md` | ❌ **手动** | 新页不进索引，人翻索引找不到 |

> 脚本自动处理前三项。**域索引的「页面」表格需要你手动补一行**——这是目前唯一的遗留手工点。

> ⚠️ 没有任何强制机制（无 CI、无 git hook）。漏跑脚本**不会报错，只会静默失效**：文档看起来更新了，实际 Agent 读不到。**改完就跑脚本。**

> ⚠️ `sources` 指向代码路径，但**改代码不会让 wiki 自动更新**。代码变了要手动同步对应页——这是文档-代码漂移，只能靠人。

## 可视化

`wiki/index.html` 由脚本生成（零依赖，双击即看）：

- 左侧栏按域分组，顶部**搜索框**按标题或 id 过滤
- `[[id]]` 渲染成可点链接，点击即跳转
- 表格、代码块、引用块、`mermaid` 流程图均已渲染
- 支持深色模式（跟随系统）
- `mermaid` 图需联网加载渲染库；**离线时降级为源码文本**，其余功能不受影响

## 工具

| 命令 | 作用 |
| --- | --- |
| `python3 wiki/scripts/build_index.py` | 生成 `llms.txt` + `index.html` + 同步 README 清单 + 校验链接 |
| `python3 wiki/scripts/build_index.py --check` | 仅校验，不写任何文件（适合提交前跑） |
| `python3 wiki/scripts/build_index.py --no-html` | 跳过 HTML 生成 |
| `python3 wiki/scripts/build_index.py --open` | 生成后用浏览器打开 `index.html` |

校验两类死链：`[[id]]` 与 markdown 相对链接（含锚点）。有死链时退出码非 0。
