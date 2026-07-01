# Integration QA — 全栈串联（C 轨）

> 记录 Bridge Learn C 轨学习过程的问答与标准答案。  
> 对应知识点见 `.cursor/skills/bridge-learn/references/knowledge-integration.md`。

---

## C1.1 monorepo 双项目职责划分

**综合评分**：8/10

### 主题目

**问**：根目录 `README.md` 把仓库拆成 `agents-master/` 与 `rag-server/` 两个子项目。请说明各自核心职责、连接方式、预置 MCP，以及演示「知识库问答」的最小配置。

**标准答案**：

1. **职责划分**
  - `agents-master/`：MCP **Host**。Streamlit UI + LangGraph ReAct Agent，负责对话、工具编排、多模式切换（通用 / 旅行 / 知识库问答）、会话与长期记忆。
  - `rag-server/`：模块化 **RAG MCP Server**。负责文档摄取（Ingest）、向量/BM25 混合检索、Chroma 存储，通过 MCP 暴露 `list_collections`、`query_knowledge_hub`、`get_document_summary` 等工具。
  - 二者**不直接 import** 对方 Python 包，通过 MCP 协议解耦。
2. **连接方式**
  - 协议：**MCP**（本项目主链路用 **stdio** 传输）。
  - 配置：`agents-master/config.json` 中 `rag-server` 条目指定 `command`、`args`、`cwd`、`transport`；启动时 `resolve_mcp_config()` 解析相对路径为绝对路径，并优先使用 `rag-server/.venv/bin/python`。
3. **预置 MCP（共 4 个）**

  | MCP 名              | 来源            | 作用                                     |
  | ------------------ | ------------- | -------------------------------------- |
  | `get_current_time` | agents-master | 查询指定时区当前时间                             |
  | `document-export`  | agents-master | 将 Agent 成品写入 `data/outputs/*.md`，供用户下载 |
  | `rag-server`       | rag-server    | 知识库列举、混合检索、文档摘要                        |
  | `amap-maps`        | 外部 npm 包      | 旅行模式 POI / 路线 / 天气                     |

4. **知识库问答最小配置**
  - 配置并启动 `**agents-master`**（`.env` 中 LLM Key，如 `DASHSCOPE_API_KEY`）。
  - `**rag-server` 装好依赖**（独立 `.venv`）和 `config/settings.yaml`（`llm` / `embedding` 的 `api_key`）；无需单独起 HTTP 服务，MCP Client 初始化时会 **spawn 子进程**。
  - **已 ingest 的 collection**（否则检索无内容）；RAG 控制台（`dashboard.py`）可选，用于可视化管理入库。
  - 侧边栏切到「知识库问答」模式提问。

**参考路径**：根 `README.md`、`agents-master/README.md`、`agents-master/config.json`

---

### 追问 1

**问**：`document-export` 解决什么问题？与 RAG ingest/检索有何不同？打开 `http://localhost:8501` 后，`rag-server` 是单独 Streamlit 启动还是随 Agent 初始化拉起？依据 `config.json` 哪些字段？

**标准答案**：

1. `**document-export`**：将 Agent **生成的成品**（如旅行攻略 Markdown）写入本地文件并提供下载，属于**输出链路**。
  - **RAG ingest**：把外部文档解析、分块、向量化后写入 Chroma，属于**知识入库**。
  - **RAG 检索**：Agent 通过 MCP 调用 `query_knowledge_hub` 等，从已有 collection **召回片段**，属于**读取链路**。三者职责不同，不可混用。
2. **启动方式**
  - 主应用 `streamlit run app.py`（8501）时，`rag-server` 作为 MCP **随 Agent 初始化由 Client 拉起**，不是必须先单独 `streamlit run`。
  - `rag-server/` 下的 `streamlit run dashboard.py` 是**独立的 RAG 管理控制台**（入库、评测等），与主应用并行可选。
  - 判断依据：`config.json` 中 `transport: "stdio"`（标准输入输出通信，spawn 子进程）+ `cwd: "../rag-server"` 与 `command`/`args`（在 rag-server 目录执行 `python -m src.mcp_server.server`）。

**参考路径**：`agents-master/mcp_server_export.py`、`agents-master/config.json`、`agents-master/config/mcp_config.py`

---

### 追问 2

**问**：`stdio` 与 `http` 传输在进程生命周期与部署上有何不同？知识库问答模式调用哪 3 个 rag-server 工具？

**标准答案**：

1. **stdio vs http**
  - **stdio**：Host 启动 MCP Client 时 **spawn 子进程**，通过 stdin/stdout 通信；Host 关闭则子进程随之结束。无需 Server 预先监听端口，适合本地单体联调。
  - **http**：Server 需**独立常驻**并监听 URL；Host 通过网络连接。Server 崩溃或不可达会导致 Host 连接失败，部署上需单独运维、健康检查与端口管理。
2. **知识库问答三工具**（见 `modes/knowledge_qa/system.md`）
  - `list_collections` — 列出知识库集合及文档数量
  - `query_knowledge_hub` — 在指定 `collection` 中做混合检索（Dense + BM25 + RRF）
  - `get_document_summary` — 按 `doc_id` 获取文档摘要与元数据

**推荐调用顺序**：先 `list_collections` 选库 → `query_knowledge_hub` 检索 → 必要时 `get_document_summary`。

**参考路径**：`agents-master/modes/knowledge_qa/system.md`、`agents-master/modes/knowledge_qa/mode.py`

---

