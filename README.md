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

![功能演示 1](rag-server/assets/image-1.png)
![功能演示 5](rag-server/assets/image-5.png)
![功能演示 2](rag-server/assets/image-2.png)
![功能演示 3](rag-server/assets/image-3.png)
![功能演示 4](rag-server/assets/image-4.png)
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

> 注意：请勿将真实密钥提交到 Git。

## 开发与文档资源 📚

<!-- WIKI-DOC-LIST:START -->
> 项目知识库已重构为 **wiki**（一页一主题、可交叉链接、可溯源到代码）。
> 人类入口 [`wiki/README.md`](wiki/README.md) · LLM 入口 [`wiki/llms.txt`](wiki/llms.txt) · 可视化站点 `wiki/index.html`（浏览器打开，含侧栏与搜索）。
>
> 下方清单由 `python3 wiki/scripts/build_index.py` 自动生成，**请勿手动编辑本区块**。

- **00-overview · Overview 全局**（项目定位、术语表、仓库地图）
  - [`wiki/00-overview/glossary.md`](wiki/00-overview/glossary.md) — 术语表
  - [`wiki/00-overview/project.md`](wiki/00-overview/project.md) — 项目定位与架构总览
  - [`wiki/00-overview/repo-map.md`](wiki/00-overview/repo-map.md) — 仓库结构与模块地图
- **10-host · Host (agents-master)**（Host 域：架构 / 中间件 / ReAct / MCP / 模式 / Prompt / 记忆 / 旅行）
  - [`wiki/10-host/index.md`](wiki/10-host/index.md) — Host 域索引（agents-master）
  - [`wiki/10-host/architecture.md`](wiki/10-host/architecture.md) — Host 架构与 app.py 拆分
  - [`wiki/10-host/mcp-client.md`](wiki/10-host/mcp-client.md) — MCP 客户端与配置管理
  - [`wiki/10-host/memory.md`](wiki/10-host/memory.md) — 对话记忆系统
  - [`wiki/10-host/middleware.md`](wiki/10-host/middleware.md) — 中间件化改造方案
  - [`wiki/10-host/modes.md`](wiki/10-host/modes.md) — 多模式 Agent 架构选型
  - [`wiki/10-host/prompts.md`](wiki/10-host/prompts.md) — Prompt 分层
  - [`wiki/10-host/react-agent.md`](wiki/10-host/react-agent.md) — ReAct Agent 与运行方式
  - [`wiki/10-host/travel-impl.md`](wiki/10-host/travel-impl.md) — 旅行规划 · 职责分层与步骤依据（实现）
  - [`wiki/10-host/travel-product.md`](wiki/10-host/travel-product.md) — 旅行规划 · 需求与架构（产品）
- **20-rag · RAG (rag-server)**（RAG 域：架构 / 需求 / 流程 / MCP Server / 评估 / 控制台）
  - [`wiki/20-rag/index.md`](wiki/20-rag/index.md) — RAG 域索引（rag-server）
  - [`wiki/20-rag/architecture.md`](wiki/20-rag/architecture.md) — RAG 系统架构与模块选型
  - [`wiki/20-rag/evaluation.md`](wiki/20-rag/evaluation.md) — 评估体系设计
  - [`wiki/20-rag/flow.md`](wiki/20-rag/flow.md) — 整体设计与流程
  - [`wiki/20-rag/mcp-server.md`](wiki/20-rag/mcp-server.md) — 外接集成与 MCP Server
  - [`wiki/20-rag/observability.md`](wiki/20-rag/observability.md) — RAG 控制台（Dashboard）指南
  - [`wiki/20-rag/requirements.md`](wiki/20-rag/requirements.md) — RAG 需求目标与模块设计
- **30-integration · Integration 跨子系统**（跨子系统：端到端链路、配置密钥、生命周期、排障）
  - [`wiki/30-integration/index.md`](wiki/30-integration/index.md) — 跨子系统集成（域索引）
  - [`wiki/30-integration/config-and-keys.md`](wiki/30-integration/config-and-keys.md) — 配置与密钥分工
  - [`wiki/30-integration/end-to-end.md`](wiki/30-integration/end-to-end.md) — 端到端主链路
  - [`wiki/30-integration/mcp-lifecycle.md`](wiki/30-integration/mcp-lifecycle.md) — MCP 子进程生命周期与重连
  - [`wiki/30-integration/troubleshooting.md`](wiki/30-integration/troubleshooting.md) — 常见故障排查
- **40-decisions · Decisions 架构决策**（ADR 架构决策记录）
  - [`wiki/40-decisions/index.md`](wiki/40-decisions/index.md) — 架构决策记录（域索引）
  - [`wiki/40-decisions/0001-monorepo-split.md`](wiki/40-decisions/0001-monorepo-split.md) — ADR-0001 monorepo 双项目不合并
  - [`wiki/40-decisions/0002-dual-venv.md`](wiki/40-decisions/0002-dual-venv.md) — ADR-0002 双 venv 隔离依赖
  - [`wiki/40-decisions/0003-mcp-stdio.md`](wiki/40-decisions/0003-mcp-stdio.md) — ADR-0003 MCP 选 stdio 而非 HTTP
  - [`wiki/40-decisions/0004-state-machine-outside-graph.md`](wiki/40-decisions/0004-state-machine-outside-graph.md) — ADR-0004 旅行状态机放在 LangGraph 之外
- **50-analysis · Analysis 测试与优化**（测试与优化分析）
  - [`wiki/50-analysis/index.md`](wiki/50-analysis/index.md) — 测试与优化分析（域索引）
  - [`wiki/50-analysis/display-optimization.md`](wiki/50-analysis/display-optimization.md) — 旅行模式 MCP 与 RAG 能力展示优化建议
  - [`wiki/50-analysis/github-push-mode.md`](wiki/50-analysis/github-push-mode.md) — GitHub 推送模式目标分析
  - [`wiki/50-analysis/mcp-init-performance.md`](wiki/50-analysis/mcp-init-performance.md) — MCP 初始化性能分析与优化
  - [`wiki/50-analysis/rag-e2e-performance.md`](wiki/50-analysis/rag-e2e-performance.md) — RAG 端到端性能测试
  - [`wiki/50-analysis/rag-evaluation-tuning.md`](wiki/50-analysis/rag-evaluation-tuning.md) — RAG 评估调优专题
  - [`wiki/50-analysis/rag-issues.md`](wiki/50-analysis/rag-issues.md) — RAG 测试问题与优化记录
  - [`wiki/50-analysis/test-summary.md`](wiki/50-analysis/test-summary.md) — 旅行模式测试问题与优化总结（2026-06）
  - [`wiki/50-analysis/token-optimization.md`](wiki/50-analysis/token-optimization.md) — 旅行模式 Token 消耗分析与优化
  - [`wiki/50-analysis/tool-failures.md`](wiki/50-analysis/tool-failures.md) — 工具调用失败案例与处理准则
<!-- WIKI-DOC-LIST:END -->

- `.cursor/skills/` 项目级 Skills（Agent 对话中自然语言触发）：
  - `.cursor/skills/README.md` — Skills 一览与维护入口
  - `.cursor/skills/agent-development/` — Agent 开发规范与方法论（设计/Tool/State/Prompt/评估）
