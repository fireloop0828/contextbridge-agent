# LangGraph + MCP 智能体（Streamlit）

ContextBridge Agent monorepo 的**主应用**（`agents-master/`）：「**MCP 宿主（Host）+ MCP 客户端（Client）+ ReAct Agent**」工作台，通过 MCP 动态接入外部工具，在网页中与智能体对话并实时查看工具调用。顶层联调说明见 [../README.md](../README.md)。

## 这个项目能做什么

- **网页聊天界面（Streamlit）**：与 LangGraph `ReAct Agent` 对话，流式展示回答与工具调用详情
- **三种对话模式**（侧边栏切换）：
  - **通用模式**：开放问答，按需调用已连接的全部 MCP 工具
  - **旅行规划**：结合高德地图、RAG 知识库、时间工具生成可下载行程攻略
  - **知识库问答**：聚焦 `list_collections` / `query_knowledge_hub` / `get_document_summary`
- **MCP 工具管理**：在侧边栏添加/删除/配置 MCP Server（支持 Smithery JSON），无需改核心代码
- **会话与记忆**：对话归档与恢复、跨会话长期记忆画像（侧边栏「记忆面板」）

## MCP 基本概念（面试可用）

- **MCP Host**：承载智能体的应用（本项目 `app.py` / Cursor / Claude Desktop 都属于 Host）
- **MCP Client**：连接 MCP Server 并加载工具（本项目使用 `MultiServerMCPClient`）
- **MCP Server**：对外暴露工具（tools）的服务（例如 `mcp_server_time.py`、`mcp_server_export.py`，以及同级目录 `../rag-server` 的生产级 RAG MCP）

## 运行方式一：本地运行（推荐）

### 依赖

- Python **≥ 3.12**

### 1) 创建虚拟环境并安装依赖

在 `agents-master/` 目录执行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> macOS 若 `pip install` 报 SSL 证书错误，可执行一次：
>
> ```bash
> /Applications/Python\ 3.12/Install\ Certificates.command
> ```

### 2) 配置环境变量（.env）

复制并编辑 `.env`：

```bash
cp .env.example .env
```

至少配置一种模型的 Key（推荐国内使用百炼）：

- **阿里云百炼（OpenAI 兼容模式）**：
  - `DASHSCOPE_API_KEY=...`
  - `DASHSCOPE_BASE_URL=...`（默认北京：`https://dashscope.aliyuncs.com/compatible-mode/v1`）
- **旅行模式高德地图**：`AMAP_MAPS_API_KEY=...`（见下方第 3 步）
- 可选：`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`LANGSMITH_*`

登录开关（可选）：

```bash
USE_LOGIN=false
```

### 3) 高德地图 MCP（旅行模式需要）

```bash
npm install   # 安装 @amap/amap-maps-mcp-server，避免 npx 冷启动
```

`config.json` 已注册 `amap-maps`；`resolve_mcp_config()` 会解析 `node_modules/.bin/mcp-amap`，并将 `.env` 中的 `AMAP_MAPS_API_KEY` 注入子进程。

### 4) 启动

```bash
streamlit run app.py
```

默认访问：`http://localhost:8501`

### 5) 初始化（自动）

首次打开页面时会**自动连接** MCP Server 并创建 Agent（无需手动点击按钮）。若连接失败，请检查 `config.json`、`.env` 中的 API 密钥，以及 `rag-server` 是否已安装依赖（见下文 RAG 流程）。

## 运行方式二：Docker（精简，可选）

> **注意**：`dockers/config.json` 仅注册 `get_current_time`，**不含** `rag-server` / 高德 / 文档导出；且仓库内无 `Dockerfile`，compose 依赖外部镜像 `teddylee777/langgraph-mcp-agents:0.2.1`。**完整功能（旅行 + RAG）请用本地运行。**

Docker 运行时，`.env` 位于 `dockers/` 目录（与 compose 文件同级）：

```bash
cd dockers
cp .env.example .env
docker compose -f docker-compose-mac.yaml up -d   # Apple Silicon
# 或 docker compose -f docker-compose.yaml up -d   # x86_64
```

访问：`http://localhost:8585`

## MCP 工具配置（config.json）

默认注册 **4 个** MCP Server：`get_current_time`、`document-export`、`rag-server`、`amap-maps`（见 `config.json`）。传输方式为 **stdio**，由应用启动时自动拉起子进程并拉取工具列表。

字段含义、`resolve_mcp_config()` 解析规则、重连策略、模式与 MCP 关系、stdio 与 HTTP/SSE 对比等设计说明，见 **[wiki/10-host/mcp-client.md](wiki/10-host/mcp-client.md)**。

侧边栏可粘贴 Smithery JSON 增删 MCP（立即重连）。切换 LLM 模型时点 **「应用模型」**（不重连 MCP）。

## 完整 RAG 流程（rag-server + agents-master）

### 架构

```
用户提问 → Streamlit (agents-master)
         → LangGraph ReAct Agent
         → MCP Client 调用 rag-server 工具
              ├── list_collections
              ├── query_knowledge_hub  ← 混合检索（Dense + BM25 + RRF）
              └── get_document_summary
         → 百炼 LLM 生成回答
```

### 第一步：安装 rag-server 依赖

在 `rag-server/` 目录执行：

```bash
cd ../rag-server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

> rag-server 需要独立虚拟环境（含 chromadb、mcp 等），与 agents-master 的 venv 分开。

### 第二步：配置 rag-server（百炼）

```bash
cp config/settings.dashscope.example.yaml config/settings.yaml
```

编辑 `config/settings.yaml`，将 `llm` / `embedding` 的 `api_key` 填为你的百炼 Key（与 `agents-master/.env` 中 `DASHSCOPE_API_KEY` 相同）。

### 第三步：导入文档（Ingest）

```bash
# 仍在 rag-server 目录，venv 已激活

# 试跑：使用仓库内示例文本
python scripts/ingest.py \
  --path tests/fixtures/sample_documents/sample.txt \
  --collection travel_plan

# 正式数据：将 PDF/TXT/MD/DOCX 放到 data/sources/<collection>/（该目录默认不入 Git）
python scripts/ingest.py \
  --path data/sources/travel_plan \
  --collection travel_plan \
  --force
```

成功后会写入 `data/db/chroma/`。新 collection 建议在 `config/collections.yaml` 注册说明，便于 `list_collections` 展示给 Agent。亦可在 RAG 控制台（`streamlit run dashboard.py`）的「文档入库」页面上传。详见 `wiki/20-rag/observability.md`。

### 第四步：启动 agents-master 并初始化

```bash
cd ../agents-master
source .venv/bin/activate
streamlit run app.py
```

1. 打开 `http://localhost:8501`
2. 等待页面自动初始化完成（侧边栏应显示 **4 个** MCP：时间、文档导出、rag-server、高德）
3. 侧边栏选择模式后提问，例如：
  - **知识库问答**：「知识库里有哪些 collection？」「在 travel_plan 里检索关于签证的内容」
  - **旅行规划**：「帮我规划 5 天东京自由行，偏好美食」
  - **通用模式**：开放问答或文档导出

### 常见问题


| 现象                               | 处理                                                      |
| -------------------------------- | ------------------------------------------------------- |
| 初始化失败 `No module named chromadb` | 在 rag-server 目录创建 `.venv` 并 `pip install -e ".[dev]"`   |
| 检索无结果                            | 确认已执行 ingest，且 collection 名称与 query 时一致                 |
| Embedding 报错                     | 检查 `settings.yaml` 中 `embedding.model` 与百炼控制台已开通的模型一致（示例配置为 `qwen3.6-flash-2026-04-16`） |
| 高德工具不可用                         | 在 `agents-master/` 执行 `npm install`，并配置 `AMAP_MAPS_API_KEY` |
| rag-server 路径不对                  | 修改 `config.json` 中 `cwd` 为 rag-server 的绝对路径             |


## 示例 MCP Server

- `mcp_server_time.py`：查询指定时区当前时间（依赖 `pytz`）
- `mcp_server_export.py`：将成品写入 `data/outputs/*.md`，页面提供下载按钮
- `../rag-server`：**生产级 RAG**（Hybrid Search + Chroma + MCP 工具），推荐用于面试演示
- `mcp_server_rag.py`：教学级简易 RAG（单 PDF），已被 rag-server 替代

### 导出可下载 Markdown

- **旅行规划模式**：攻略生成后由 `export_service` **服务端自动写盘**（`data/outputs/`），聊天区与侧边栏出现下载按钮；**无需** Agent 再调 `write_markdown_document`（避免重复输出与 Token 浪费）。
- **通用模式**：`config.json` 已注册 `document-export` MCP；对话中说明需求后，Agent 可调用 `write_markdown_document` 写入 `data/outputs/*.md`，页面提供下载按钮。

## 开发文档

- [wiki/10-host/mcp-client.md](wiki/10-host/mcp-client.md) — **MCP 设计、注册表与配置（权威）**
- `wiki/10-host/` — 多模式架构、旅行规划设计、app 拆分建议、MCP 客户端等
- `wiki/50-analysis/` — Token、记忆、MCP 性能分析与优化记录
- `../rag-server/README.md` — RAG 子项目说明

## 兼容性说明（重要）

本项目使用的 `langchain-mcp-adapters` 新版本 **不再支持** 将 `MultiServerMCPClient` 当作 async context manager（即不能 `async with client` / `await client.__aenter__()`）。当前实现采用：

- `tools = await client.get_tools()`

## 教程

- `MCP-HandsOn-ENG.ipynb`：MCP + LangGraph 动手教程（中文，API 已与当前 `langchain-mcp-adapters` 对齐）

