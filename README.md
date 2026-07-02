# ContextBridge Agent

基于 **LangGraph + MCP** 的多模式智能体工作台：Streamlit 聊天界面、**通用模式 / 旅行规划 / 知识库问答** 三种应用模式，以及 RAG 检索与工具编排。本仓库为 **monorepo**，包含主应用与 RAG 服务两个子项目。

## 仓库结构

```
ContextBridge Agent/
├── agents-master/     # 主应用（Streamlit + LangGraph ReAct Agent）
├── rag-server/        # 模块化 RAG MCP Server（被 agents-master 通过 config.json 引用）
└── README.md
```

主应用预置 MCP：`get_current_time`、`document-export`、`rag-server`、`amap-maps`（见 `agents-master/config.json`）。

## 快速开始

### 1. 主应用（agents-master）

```bash
cd agents-master
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # 填入 DASHSCOPE_API_KEY、AMAP_MAPS_API_KEY 等
streamlit run app.py
```

默认访问：[http://localhost:8501](http://localhost:8501)。侧边栏可切换 **通用模式 / 旅行规划 / 知识库问答**。

### 2. RAG 服务（rag-server，可选但推荐）

主应用 `config.json` 已配置 `rag-server` MCP（`python -m src.mcp_server.server`，`cwd` 指向 `../rag-server`）。`resolve_mcp_config()` 会优先使用 `rag-server/.venv` 中的 Python。

**手动配置：**

```bash
cd rag-server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/settings.dashscope.example.yaml config/settings.yaml
# 编辑 settings.yaml，将 api_key 改为你的百炼 Key（与 agents-master/.env 中 DASHSCOPE_API_KEY 一致）
```

**或使用 Setup Skill（推荐）**：在 Cursor 中打开 `rag-server/`，对 Agent 说 `setup`，按向导生成 `config/settings.yaml` 并安装依赖。详见 [rag-server/README.md](rag-server/README.md) 与 [rag-server/skills/README.md](rag-server/skills/README.md)。

启动 **RAG 控制台**（Streamlit 可视化管理面板：运行概览 / 知识浏览 / 文档入库 / 链路追踪 / 效果评测）：

```bash
# 默认 http://localhost:8501（与 agents-master 的 streamlit run app.py 对称）
streamlit run dashboard.py

# 与主应用同机时换端口
python scripts/start_dashboard.py --port 8502
```

主应用与 RAG 控制台默认均占用 `8501`，同时运行时请为 RAG 控制台指定其他端口。更多页面说明见 `rag-server/docs/管理面板指南.md`。

### 3. 高德地图 MCP（旅行模式）

```bash
cd agents-master
npm install   # 安装 @amap/amap-maps-mcp-server，避免 npx 冷启动
```

在 `.env` 中配置 `AMAP_MAPS_API_KEY`；`config.json` 不再存放密钥，启动时由 `resolve_mcp_config` 从环境变量注入。

## 密钥与配置约定


| 文件                                       | 是否入库 | 说明                                     |
| ---------------------------------------- | ---- | -------------------------------------- |
| `agents-master/.env`                     | ❌    | 从 `.env.example` 复制，本地填写               |
| `agents-master/config.json`              | ✅    | MCP 服务定义，不含 API Key                    |
| `rag-server/config/settings.yaml`        | ❌    | 从 `settings.dashscope.example.yaml` 复制 |
| `agents-master/data/`、`rag-server/logs/` | ❌    | 运行时数据                                  |


**切勿将真实 API Key 提交到 Git。**

### 两套主配置如何对应

主应用与 RAG 服务各自维护一份本地配置；百炼 Key 通常两处填**同一把**（`agents-master/.env` 的 `DASHSCOPE_API_KEY` 与 `rag-server/config/settings.yaml` 的 `api_key`）。

```
agents-master/.env
  DASHSCOPE_API_KEY   →  聊天模型（qwen3.7-plus、qwen-max、qwen-vl-plus 等，见 config/models.py）
  DASHSCOPE_BASE_URL  →  百炼 OpenAI 兼容端点
  DASHSCOPE_EMBEDDING_MODEL  →  长期记忆向量（可选，默认 text-embedding-v3，见 memory_store.py）
  AMAP_MAPS_API_KEY   →  旅行模式高德 MCP
  FEISHU_APP_ID / FEISHU_APP_SECRET  →  飞书文档 MCP（可选，侧边栏添加 feishu/lark MCP 时使用）
  ANTHROPIC_API_KEY / OPENAI_API_KEY  →  可选，启用对应 Claude / GPT 模型
  LANGSMITH_*         →  可选，LangSmith 追踪

rag-server/config/settings.yaml
  llm.api_key / llm.model           →  RAG 查询、分块精炼、元数据等 LLM
  embedding.api_key / embedding.model  →  向量入库与稠密检索
  vision_llm.*                      →  图像描述（默认 enabled: false）
  evaluation.llm_model              →  Ragas 评估专用模型（须非 thinking 模型）
  rerank.model                      →  重排序模型（启用 rerank 时）
```


| 用途               | 改哪里                                                    |
| ---------------- | ------------------------------------------------------ |
| 侧边栏聊天模型          | `agents-master/.env` + `config/models.py` 中的模型列表       |
| 长期记忆 Embedding   | `agents-master/.env`（`DASHSCOPE_*`）                    |
| 知识库检索与入库         | `rag-server/config/settings.yaml`（`llm` / `embedding`） |
| 旅行 POI / 天气 / 路线 | `agents-master/.env`（`AMAP_MAPS_API_KEY`）              |


## 开发文档

- `.cursor/skills/` — 项目级 Agent Skill（`bridge-learn` 学习、`bridge-resume` 简历、`create-skill` 建 skill）
- [agents-master/docs/project-design/MCP设计与管理.md](agents-master/docs/project-design/MCP设计与管理.md) — MCP 设计、注册表与配置
- `agents-master/docs/project-design/` — 主应用架构与设计
- `agents-master/docs/test-analysis/` — Token、记忆、MCP 性能等分析与优化记录
- `rag-server/README.md` — RAG 服务概述与使用策略
- `rag-server/DEV_SPEC.md` — RAG 模块规格与实现状态
- `rag-server/docs/` — 管理面板、集成设计等

## 许可证

个人学习/面试项目，按需自用。