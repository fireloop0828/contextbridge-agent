# ContextBridge Agent

**ContextBridge Agent** 是一个基于 **LangGraph + MCP** 的多模式智能体工作台，集成了 Streamlit 聊天界面、MCP 工具动态接入、RAG 检索与旅行规划能力。该仓库采用 monorepo 结构，包含主应用和 RAG 服务两个子项目。

## 目录

- [项目架构](#项目架构-🏗️)
- [项目亮点](#项目亮点)
- [核心能力](#核心能力)
- [仓库结构](#仓库结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [开发与文档资源](#开发与文档资源)

## 项目架构 🏗️

本项目由两大子系统构成：

- `agents-master/`：主应用负责 Agent 运行时、Streamlit UI、MCP 客户端管理与多模式调度。
- `rag-server/`：RAG 服务负责知识库摄取、向量检索、混合检索与评估，并通过 MCP 对外暴露工具。

两者通过 MCP 协议联动，形成一个既支持前端交互又支持后端检索的完整智能体体系。
![项目架构图](rag-server/assets/image.png)
## 项目亮点 🚀

- **Agent 编排与多模式工作台**：基于 LangGraph ReAct Agent 的调度引擎，支持通用聊天、旅行规划、知识库问答三种工作模式，并通过 `modes` 注册表实现可扩展模式插件。
- **MCP 全链路集成**：主应用支持 stdio MCP 客户端与服务器，自动发现工具、动态注册、热重连，并允许通过 Smithery JSON 直接接入外部 MCP 服务，形成开放工具生态。
- **会话与记忆体系**：内置会话归档、历史记忆面板、长期记忆 Embedding 与短期对话状态，增强连续性思路、上下文保持与历史内容复用。
- **可观测交互体验**：Streamlit UI 实时展示工具调用链路、模型响应、RAG 结果与导出内容，支持用户直观审查智能体决策过程。
- **RAG 模块化架构**：`rag-server` 采用 Factory + YAML 驱动设计，可插拔数据源、检索后端、评估组件与输出策略，适配多种业务场景与扩展需求。
- **混合检索能力**：支持 Dense Embedding + Sparse BM25 双路召回、RRF 融合以及可选 reranker 精排，兼顾语义理解与精确匹配，提升 Top-K 检索效果。
- **文档摄取与索引**：支持文档分块、Embedding 生成、Chroma 向量库管理与知识库 Collection 管理，适配多格式文档与知识库迭代。
- **评估与测试体系**：集成回归验证、Ragas 评估与效果监控流程，便于持续迭代、性能监控与质量保障。
- **旅行规划能力**：支持高德地图 POI 查询、路线规划、行程生成与 Markdown 导出，构建可执行的旅行方案交互体验。

## 核心能力 💡

| 核心能力 | 内容 | 体现 |
| --- | --- | --- |
| Agent 编排与多模式 | LangGraph ReAct Agent 提供智能调度与工具调用，支持通用聊天、旅行规划、知识库问答，且可通过 `modes` 注册表扩展业务模式 | 多模式切换、插件式模式扩展、统一对话入口 |
| MCP 工具联动 | 支持动态发现、加载与调用 MCP 工具，兼容 stdio 子进程与外部 MCP 集成 | 运行时自动注册、工具调用链可视化、热重连与扩展能力 |
| 记忆与会话管理 | 支持短期对话状态、历史会话归档、长期记忆 Embedding 与检索 | 连续对话衔接、历史上下文复用、跨会话知识保留 |
| 交互可视化 | Streamlit 界面实时展示对话、工具调用、模型响应与结果导出 | 流程透明、用户感知友好、操作即见效果 |
| 旅行规划能力 | 高德地图 MCP 与内置行程生成逻辑联合输出规划结果 | POI 搜索、景点推荐、行程导出与可视化支持 |
| 文档摄取 | 支持文档分块、Embedding 生成、向量入库与 collection 管理 | 多格式支持、自动 Chunk、知识库迭代管理 |
| 混合检索 | Dense Embedding + Sparse BM25 双路召回，支持 RRF 融合与 reranker 精排 | 提高检索覆盖、提升 Top-K 准确率、兼顾语义与精确匹配 |
| RAG 集成 | `rag-server` 采用 Factory + YAML 驱动，实现可插拔检索与评估组件、外部 MCP 暴露 | 灵活配置检索后端、快速切换模型、可扩展数据源 |
| 评估与监控 | 支持回归测试、Ragas 评估与效果监控，提供持续迭代能力 | 可量化质量变化、提升改动可控性、保障迭代效果 |

### 功能演示

| 演示 | 截图 |
| --- | --- |
| 界面演示 1 | ![功能演示 1](rag-server/assets/image-1.png) |
| 界面演示 2 | ![功能演示 2](rag-server/assets/image-6x.png) |
| 入库演示 | ![功能演示 3](rag-server/assets/image-2.png) |
| 评测演示 | ![功能演示 4](rag-server/assets/image-3.png) |
| trace可视化 | ![功能演示 5](rag-server/assets/image-4.png) |
| 导出文件 | ![功能演示 6](rag-server/assets/image-5a.png) |

## 仓库结构 📁

```
ContextBridge Agent/
├── agents-master/     # 主应用：Streamlit UI + Agent 运行时
│   ├── app.py          # 主入口
│   ├── config.json     # MCP 工具与模式配置
│   ├── .env.example    # 本地环境变量模板
│   ├── docs/           # 主应用设计与测试文档
│   ├── data/           # 运行时数据与输出
│   └── modes/          # Agent 模式注册表与扩展
├── rag-server/        # RAG 服务：知识摄取、检索、评估
│   ├── main.py         # RAG MCP Server 启动入口
│   ├── dashboard.py    # Streamlit 控制台入口
│   ├── config/         # RAG 模型与 collection 配置
│   ├── docs/           # RAG 设计与管理文档
│   └── src/            # RAG 服务核心实现代码
├── dockers/           # Docker 运行与配置（可选）
└── README.md          # 顶层项目说明
```

- `agents-master/`：主应用（Streamlit + LangGraph），负责前端界面、Agent 调度、MCP 工具接入与会话管理。
- `rag-server/`：RAG 服务，负责文档摄取、向量索引、混合检索、评估与 MCP 工具暴露。

## 快速开始 🚀

### 1. agents-master 本地运行

```bash
cd agents-master
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `agents-master/.env`，至少配置：

- `DASHSCOPE_API_KEY`
- `AMAP_MAPS_API_KEY`（旅行模式需要）

启动应用：

```bash
streamlit run app.py
```

默认访问：`http://localhost:8501`

### 2. rag-server 本地运行

```bash
cd rag-server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/settings.dashscope.example.yaml config/settings.yaml
```

编辑 `config/settings.yaml`，配置：

- `llm.api_key`
- `embedding.api_key`
- `llm.model`
- `embedding.model`

启动 RAG 控制台：

```bash
streamlit run dashboard.py
```

如需更换端口：

```bash
python scripts/start_dashboard.py --port 8502
```

### 3. 旅行模式 / 高德地图 MCP

在 `agents-master/` 执行：

```bash
npm install
```

确保 `.env` 中存在：

- `AMAP_MAPS_API_KEY`

`config.json` 已注册 `amap-maps` MCP，运行时会从环境变量注入密钥。

## 配置说明 ⚙️

### agents-master

- `agents-master/.env`：API Key、模型端点、环境变量配置
- `agents-master/config.json`：MCP 服务定义与工具注册
- `agents-master/data/`：运行时输出与会话数据

### rag-server

- `rag-server/config/settings.yaml`：RAG 服务模型与嵌入配置
- `rag-server/config/collections.yaml`：知识库 collection 定义
- `rag-server/data/`：向量数据库与中间数据

### 密钥关系

| 目的 | 配置位置 |
| ---- | ---- |
| 聊天模型 | `agents-master/.env` + `agents-master/config/models.py` |
| 长期记忆 Embedding | `agents-master/.env`（`DASHSCOPE_*`） |
| 知识库检索 | `rag-server/config/settings.yaml` |
| 旅行 POI / 地图 | `agents-master/.env`（`AMAP_MAPS_API_KEY`） |
| 联网搜索 | `agents-master/.env`（`BOCHA_API_KEY`） |

> 注意：请勿将真实密钥提交到 Git。

## 开发与文档资源 📚

<!-- WIKI-DOC-LIST:START -->
> 项目知识库已重构为 **wiki**（一页一主题、可交叉链接、可溯源到代码）。
> 人类入口 [`wiki/README.md`](wiki/README.md) · LLM 入口 [`wiki/llms.txt`](wiki/llms.txt) · 可视化站点 `wiki/index.html`（浏览器打开，含侧栏与搜索）。
>
> 下方内容由 `python3 wiki/scripts/build_index.py` 自动生成，**请勿手动编辑本区块**。
> 想加/删必读页：在对应 `wiki/**/*.md` 的 frontmatter `tags` 里加 `must-read` 再跑脚本。

### 先看这 5 篇 · 3 分钟建立全局认知

| # | 必读页 | 你会得到什么 |
| --- | --- | --- |
| 1 | [项目定位与架构总览](wiki/00-overview/project.md) | 项目定位与两个子系统的分工 |
| 2 | [长短期记忆设计](wiki/10-host/memory.md) | 短期状态 / 长期记忆如何协同 |
| 3 | [RAG 系统架构与模块选型](wiki/20-rag/architecture.md) | 分层结构与检索后端的选型依据 |
| 4 | [RAG 评估体系与回归验证](wiki/20-rag/evaluation.md) | 回归验证与 Ragas 评估怎么落地 |
| 5 | [Token 消耗分析与优化](wiki/50-analysis/token-optimization.md) | Token 消耗打点与优化手法 |

<details><summary><b>知识域地图</b>（点开看域关系与规模）</summary>

```mermaid
graph LR
  O["Overview"] --> H["Host"]
  O --> R["RAG"]
  H --> I["Integration"]
  R --> I
  H --> D["Decisions"]
  R --> A["Analysis"]
```

| 域 | 范围 | 页数 |
| --- | --- | --- |
| Overview | 项目定位、术语表、仓库地图 | 3 |
| Host | Host 域：架构 / 中间件 / ReAct / MCP / 模式 / Prompt / 记忆 / 旅行 | 10 |
| RAG | RAG 域：架构 / 需求 / 流程 / MCP Server / 评估 / 控制台 | 7 |
| Integration | 跨子系统：端到端链路、配置密钥、生命周期、排障 | 5 |
| Decisions | ADR 架构决策记录 | 5 |
| Analysis | 测试与优化分析 | 10 |

</details>

<details><summary><b>完整清单</b>（全部 40 页，按域折叠）</summary>

**Overview** · 3 页

- [术语表](wiki/00-overview/glossary.md) `overview` `glossary`
- [项目定位与架构总览](wiki/00-overview/project.md) `overview` `architecture` `monorepo` `must-read`
- [仓库结构与模块地图](wiki/00-overview/repo-map.md) `overview` `structure` `monorepo`

**Host** · 10 页

- [Host 域索引 · 主应用](wiki/10-host/index.md)
- [主应用架构与启动入口](wiki/10-host/architecture.md) `host` `architecture` `app`
- [MCP 客户端与配置解析](wiki/10-host/mcp-client.md) `host` `mcp` `config`
- [长短期记忆设计](wiki/10-host/memory.md) `host` `memory` `must-read`
- [中间件化改造（TurnMiddleware）](wiki/10-host/middleware.md) `host` `middleware` `architecture`
- [多模式调度与注册表选型](wiki/10-host/modes.md) `host` `modes` `registry`
- [Prompt 分层与动态上下文](wiki/10-host/prompts.md) `host` `prompt`
- [ReAct Agent 执行循环](wiki/10-host/react-agent.md) `host` `react` `langgraph` `run`
- [职责分层与步骤依据](wiki/10-host/travel-impl.md) `host` `travel` `impl`
- [需求与架构（智能行程规划）](wiki/10-host/travel-product.md) `host` `travel` `product`

**RAG** · 7 页

- [RAG 域索引 · 检索服务](wiki/20-rag/index.md)
- [RAG 系统架构与模块选型](wiki/20-rag/architecture.md) `rag` `architecture` `must-read`
- [RAG 评估体系与回归验证](wiki/20-rag/evaluation.md) `rag` `evaluation` `must-read`
- [RAG 检索流程与数据流](wiki/20-rag/flow.md) `rag` `flow`
- [RAG MCP Server 与外接集成](wiki/20-rag/mcp-server.md) `rag` `mcp` `integration`
- [RAG 控制台 Dashboard 指南](wiki/20-rag/observability.md) `rag` `observability` `dashboard`
- [RAG 需求目标与模块设计](wiki/20-rag/requirements.md) `rag` `requirements`

**Integration** · 5 页

- [跨子系统集成 · 域索引](wiki/30-integration/index.md)
- [配置与密钥边界](wiki/30-integration/config-and-keys.md) `integration` `config` `security`
- [端到端请求链路](wiki/30-integration/end-to-end.md) `integration` `end-to-end` `rag`
- [MCP 子进程生命周期与热重连](wiki/30-integration/mcp-lifecycle.md) `integration` `mcp` `lifecycle`
- [故障排查手册](wiki/30-integration/troubleshooting.md) `integration` `troubleshooting` `ops`

**Decisions** · 5 页

- [ADR 索引](wiki/40-decisions/index.md)
- [ADR-0001 双项目不合并](wiki/40-decisions/0001-monorepo-split.md) `adr` `monorepo` `architecture`
- [ADR-0002 双 venv 隔离依赖](wiki/40-decisions/0002-dual-venv.md) `adr` `venv` `dependencies` `monorepo`
- [ADR-0003 传输层选 stdio](wiki/40-decisions/0003-mcp-stdio.md) `adr` `mcp` `stdio` `transport`
- [ADR-0004 状态机置于图外](wiki/40-decisions/0004-state-machine-outside-graph.md) `adr` `travel` `state-machine` `langgraph`

**Analysis** · 10 页

- [测试与优化 · 域索引](wiki/50-analysis/index.md)
- [能力展示优化建议](wiki/50-analysis/display-optimization.md) `analysis` `travel` `product` `roadmap`
- [推送模式目标分析](wiki/50-analysis/github-push-mode.md) `analysis` `tooling` `git`
- [MCP 初始化性能分析](wiki/50-analysis/mcp-init-performance.md) `analysis` `mcp` `performance`
- [RAG 端到端性能测试](wiki/50-analysis/rag-e2e-performance.md) `analysis` `rag` `performance`
- [RAG 评估调优专题](wiki/50-analysis/rag-evaluation-tuning.md) `analysis` `rag` `evaluation`
- [RAG 测试问题与优化记录](wiki/50-analysis/rag-issues.md) `analysis` `rag` `retrieval` `troubleshooting`
- [测试问题与优化总结（2026-06）](wiki/50-analysis/test-summary.md) `analysis` `travel` `test`
- [Token 消耗分析与优化](wiki/50-analysis/token-optimization.md) `analysis` `token` `travel` `performance` `must-read`
- [工具调用失败与降级准则](wiki/50-analysis/tool-failures.md) `analysis` `tools` `failure`

</details>
<!-- WIKI-DOC-LIST:END -->

- `.cursor/skills/` 项目级 Skills（Agent 对话中自然语言触发）：
  - `.cursor/skills/README.md` — Skills 一览与维护入口
  - `.cursor/skills/agent-development/` — Agent 开发规范与方法论（设计/Tool/State/Prompt/评估）
