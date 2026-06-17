# LangGraph + MCP 智能体（Streamlit）

这是一个最小可用的「**MCP 宿主（Host）+ MCP 客户端（Client）+ ReAct Agent**」示例项目：通过 MCP 动态接入外部工具（本地子进程或远程服务），在网页里与智能体对话，并实时查看工具调用过程。

project demo

## 这个项目能做什么

- **网页聊天界面（Streamlit）**：与 LangGraph `ReAct Agent` 对话
- **MCP 工具管理**：在侧边栏添加/删除/配置 MCP Server（支持 Smithery 的 JSON 格式），无需改核心代码
- **流式输出**：实时展示回答与工具调用详情
- **对话历史**：保留消息与工具调用记录

## MCP 基本概念（面试可用）

- **MCP Host**：承载智能体的应用（本项目 `app.py` / Cursor / Claude Desktop 都属于 Host）
- **MCP Client**：连接 MCP Server 并加载工具（本项目使用 `MultiServerMCPClient`）
- **MCP Server**：对外暴露工具（tools）的服务（例如本项目的 `mcp_server_time.py`、`mcp_server_rag.py`）

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
- 可选：`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`

登录开关（可选）：

```bash
USE_LOGIN=false
```

### 3) 启动

```bash
streamlit run app.py
```

默认访问：`http://localhost:8501`

### 4) 初始化（自动）

首次打开页面时会**自动连接** MCP Server 并创建 Agent（无需手动点击按钮）。若连接失败，请检查 `config.json` 与 `.env` 中的 API 密钥。

## 运行方式二：Docker

> Docker 运行时，`.env` 通常位于 `dockers/` 目录（与 compose 文件同级），请按 compose 文件说明配置。

```bash
cd dockers
cp .env.example .env
docker compose -f docker-compose-mac.yaml up -d   # Apple Silicon
```

访问：`http://localhost:8585`

## MCP 工具配置（config.json）

项目会从 `config.json` 加载 MCP Server 配置。默认注册「时间工具」与 **rag-server 知识库**：

```json
{
  "get_current_time": {
    "command": "python",
    "args": ["./mcp_server_time.py"],
    "transport": "stdio"
  },
  "rag-server": {
    "command": "python",
    "args": ["-m", "src.mcp_server.server"],
    "cwd": "../rag-server",
    "transport": "stdio"
  }
}
```

`cwd` 指向同级目录下的 `rag-server` 工程；`resolve_mcp_config()` 会自动：

- 将相对路径转为绝对路径
- 优先使用 `rag-server/.venv/bin/python`

rag-server 的 API Key 在 `rag-server/config/settings.yaml` 的 `api_key` 字段中直接配置（与百炼 Key 相同）。

### 在 UI 添加工具

侧边栏的「添加 MCP 工具」支持直接粘贴 Smithery 提供的 JSON 配置。**添加或删除后立即生效**（自动重连 MCP）。

切换 LLM 模型时，在模型下拉框下方点击 **「应用模型」** 生效。

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
mkdir -p data/documents
# 复制你的 PDF/文档到 data/documents/，或使用示例：
python scripts/ingest.py \
  --path tests/fixtures/sample_documents/simple.pdf \
  --collection travel_plan

# 批量导入 data/documents 下所有 PDF/TXT
python scripts/ingest.py \
  --path data/documents \
  --collection travel_plan \
  --force
```

成功后会写入 `data/db/chroma/`。可用 `--collection 自定义名称` 创建多个知识库。

### 第四步：启动 agents-master 并初始化

```bash
cd ../agents-master
source .venv/bin/activate
streamlit run app.py
```

1. 打开 `http://localhost:8501`
2. 等待页面自动初始化完成（侧边栏应显示 MCP 工具数量 ≥ 4：time + RAG + 导出等）
3. 在聊天框提问，例如：
  - 「知识库里有哪些 collection？」
  - 「在 travel_plan 里检索关于 XXX 的内容」

### 常见问题


| 现象                               | 处理                                                      |
| -------------------------------- | ------------------------------------------------------- |
| 初始化失败 `No module named chromadb` | 在 rag-server 目录创建 `.venv` 并 `pip install -e ".[dev]"`   |
| 检索无结果                            | 确认已执行 ingest，且 collection 名称与 query 时一致                 |
| Embedding 报错                     | 检查百炼控制台是否开通 `text-embedding-v3`；或改用 `text-embedding-v2` |
| rag-server 路径不对                  | 修改 `config.json` 中 `cwd` 为 rag-server 的绝对路径             |


## 示例 MCP Server

- `mcp_server_time.py`：查询指定时区当前时间（依赖 `pytz`）
- `mcp_server_export.py`：将成品写入 `data/outputs/*.md`，页面提供下载按钮
- `../rag-server`：**生产级 RAG**（Hybrid Search + Chroma + MCP 工具），推荐用于面试演示
- `mcp_server_rag.py`：教学级简易 RAG（单 PDF），已被 rag-server 替代

### 导出可下载 Markdown

1. `config.json` 中已注册 `document-export`（或在侧边栏添加后自动生效）
2. 对话中说明需求，例如：「把这份旅行规划导出成 md 文档」
3. Agent 调用 `write_markdown_document` 后，助手消息下方与侧边栏会出现 **下载 Markdown** 按钮
4. 文件保存在 `agents-master/data/outputs/`

## 兼容性说明（重要）

本项目使用的 `langchain-mcp-adapters` 新版本 **不再支持** 将 `MultiServerMCPClient` 当作 async context manager（即不能 `async with client` / `await client.__aenter__()`）。当前实现采用：

- `tools = await client.get_tools()`

## 教程

- `MCP-HandsOn-ENG.ipynb`：MCP + LangGraph 动手教程（中文，API 已与当前 `langchain-mcp-adapters` 对齐）

