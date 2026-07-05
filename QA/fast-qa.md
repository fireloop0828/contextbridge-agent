# Fast QA — 快速通读（Fast 轨）

> 记录 Bridge Learn **Fast** 段末问答与标准答案。  
> 题目见 `.cursor/skills/bridge-learn/references/knowledge-fast.md` 各段「段末问答」。  
> 每段问答结束（含简单追问）后由 Agent **追加**；用户说「跳过记录」时不写。

## 目录

- [Fast-0 全局主链路](#fast-0-全局主链路)
- [Fast-C C 轨串联](#fast-c-c-轨串联)
- [Fast-A A 轨 Host](#fast-a-a-轨-host)
- [Fast-B B 轨 RAG](#fast-b-b-轨-rag)
- [Fast-4 串讲与实操](#fast-4-串讲与实操)

---

## Fast-0 全局主链路

**综合评分**：8/10

### 主题目 1 · 端到端主链路

**问**：用户在「知识库问答」模式问「公司年假制度是什么？」——请串出 Streamlit → ReAct → MCP → rag-server → 谁生成最终自然语言回答？（须点明检索与生成各在哪一侧）

**标准答案**：

1. Streamlit（agents-master Host）接收提问 → LangGraph ReAct Agent 决策是否调工具。
2. MCP Client（stdio 子进程）调用 rag-server 的 `query_knowledge_hub` 等工具。
3. rag-server 内部混合检索，返回带 Citation（引用来源）的**证据片段**（非最终长答案）。
4. 证据作为 tool result 回到 ReAct 上下文；**agents-master 的 Host LLM** 阅读证据并生成用户可见的自然语言回答。
5. **检索**在 rag-server；**生成**在 Host。

**参考路径**：根 `README.md`、`agents-master/README.md`「完整 RAG 流程」

---

### 主题目 2 · 三链路分离

**问**：「入库」「检索」「导出」三条链路各解决什么？为什么入库不能靠对话里调 MCP 完成？

**标准答案**：

1. **入库**：解析、切分、向量化后**写入** chromadb；入口如 `rag-server/scripts/ingest.py` 或 Dashboard。
2. **检索**：从已有 collection **读取**相关片段；入口为对话中 MCP 三工具（如 `query_knowledge_hub`）。
3. **导出**：将 Agent 成品（如旅行攻略）**写入磁盘**供下载；入口为 `document-export` MCP。
4. **不靠对话 MCP 入库**：入库是重型批处理流水线；MCP 仅暴露**读库**三工具，职责分离，避免 Agent 误触发写库与长时任务。

**参考路径**：`agents-master/mcp_server_export.py`、`QA/integration-qa.md` § C1.1

---

### 简单追问 · 检索结果形态

**问**：`query_knowledge_hub` 返回的是最终答案还是中间证据？Host 拿到后做什么？

**标准答案**：

- 返回的是**中间检索证据**（chunk、Citation 等），不是面向用户的完整自然语言长答案。
- Host 将 tool result 追加进 ReAct messages，由 **Host LLM** 归纳、组织语言后输出最终回复。

**参考路径**：`agents-master/README.md`「完整 RAG 流程」、`docs/project-design/MCP设计与管理.md` §1.5

---

## Fast-C C 轨串联

**综合评分**：8.5/10

### 主题目 1 · 职责、连接与 spawn

**问**：`agents-master` 与 `rag-server` 各自核心职责？如何连接（协议、配置文件、谁 spawn 子进程）？预置 MCP 有哪几个？

**标准答案**：

1. **agents-master**：MCP Host — Streamlit UI、LangGraph ReAct、多模式、会话/记忆、工具编排。
2. **rag-server**：RAG MCP Server — 文档入库、混合检索、chromadb；暴露 `list_collections` / `query_knowledge_hub` / `get_document_summary`。
3. **连接**：MCP 协议 + **stdio**；配置在 `agents-master/config.json`；经 `resolve_mcp_config()` 解析后，**MCP Client** 在 `initialize_session()` → `get_tools()` 时 spawn 子进程。
4. **预置 MCP（4 个）**：`get_current_time`、`document-export`、`rag-server`、`amap-maps`。

**参考路径**：根 `README.md`、`agents-master/config.json`、`config/mcp_config.py`

---

### 主题目 2 · 边界与向量库

**问**：chromadb（向量库）在哪一侧？Host 能否直接查向量库？「检索在 rag-server、生成在 Host」具体指什么？

**标准答案**：

1. **chromadb** 仅在 **rag-server** 进程内；Host **不能**直接访问，必须经 MCP 工具。
2. **rag-server**：召回片段 + Citation（引用来源），不生成面向用户的完整长答案。
3. **Host**：ReAct 编排 + **Host LLM** 读证据后生成自然语言回复。

**参考路径**：`docs/project-design/MCP设计与管理.md` §1.5

---

### 主题目 3 · 三链路与三模式

**问**：入库、检索、导出各举一个本项目入口。三种对话模式如何裁剪工具集？

**标准答案**：

1. **入库**：`rag-server/scripts/ingest.py` 或 Dashboard（`streamlit run dashboard.py`）。
2. **检索**：对话中 MCP → `query_knowledge_hub` 等（知识库模式）。
3. **导出**：`document-export` MCP → `data/outputs/*.md`。
4. **三模式**：通用=全量 MCP；知识库=RAG 三工具 + 专用 Prompt；旅行=高德+时间+RAG+导出 + 状态机强流程。

**参考路径**：`modes/knowledge_qa/system.md`、`docs/project-design/多模式Agent架构选型.md`

---

### 简单追问 · config.json 与 spawn 时机

**问**：`config.json` 里 rag-server 条目关键字段有哪些？Host 侧是谁、在什么时机拉起 stdio 子进程？

**标准答案**：

1. **rag-server 条目**：`command: "python"`，`args: ["-m", "src.mcp_server.server"]`，`cwd: "../rag-server"`，`transport: "stdio"`。
2. **调用链**：`load_config_from_json()` → `resolve_mcp_config()` → `MultiServerMCPClient` → `await client.get_tools()` 时 spawn 子进程。
3. **入口**：`app.py` → `initialize_session()`；首次打开页面由 `ensure_session_ready()` 触发。

**参考路径**：`agents-master/config.json`、`config/mcp_config.py`、`docs/project-design/MCP设计与管理.md` §1.2

---

## Fast-A A 轨 Host

**综合评分**：8.5/10

### 主题目 1 · ReAct 闭环

**问**：ReAct 一轮里 LLM 可能做哪两类决定？工具返回后 messages 怎么变？循环何时结束？

**标准答案**：

1. **两类决定**：① 调用某个 tool（含参数）；② 不再调工具，直接给出 final answer。
2. **messages 变化**：tool 执行结果作为 **tool message** 追加到 messages；下一轮 LLM 看到完整历史再决策。
3. **结束条件**：LLM 输出最终回答、不再发起 tool call，ReAct 图到达终止节点。

**参考路径**：`agents-master/app.py`

---

### 主题目 2 · resolve_mcp_config

**问**：`resolve_mcp_config()` 在 monorepo 下解决哪三个实际问题？对 rag-server 有何特殊处理？

**标准答案**：

1. **路径绝对化**：`cwd` 等相对路径 → 基于 `APP_DIR` 的绝对路径。
2. **venv 优先**：`command: "python"` → 优先 `rag-server/.venv/bin/python`。
3. **密钥注入**：`.env` 中 Key 通过 `${VAR}` 或 env 映射注入子进程。
4. **rag-server 识别**：name / cwd 目录名 / `args == ["-m", "src.mcp_server.server"]` 触发上述规则。

**参考路径**：`config/mcp_config.py`、`QA/integration-qa.md` § C1.4

---

### 主题目 3 · 三模式差异

**问**：通用 / 知识库 / 旅行在工具数量与流程控制上各有什么不同？知识库为何要裁工具？

**标准答案**：

1. **通用**：全量 MCP；纯 ReAct，LLM 自由选工具。
2. **知识库**：仅 RAG 三工具 + 专用 system Prompt；裁工具防误调、省 Token。
3. **旅行**：高德+时间+RAG+导出；叠加**五阶段状态机**强流程（查点→路线→天气→整合→导出）。
4. **切换机制**：`AgentMode` + `registry`；`on_enter`/`on_exit` 触发 Agent 重建。

**参考路径**：`modes/`、`docs/project-design/多模式Agent架构选型.md`

---

### 简单追问 · 旅行状态机

**问**：旅行模式为何在 ReAct 之上再加状态机，而不全靠 LLM 决定下一步？

**标准答案**：

- 旅行步骤多、**顺序敏感**（先 POI 再路线再天气再导出）；纯 ReAct 易跳步、漏步、重复调工具。
- 状态机固定阶段流水线，每阶段绑定工具与 handler，**可预期、可调试、可展示进度**；ReAct 仍负责阶段内工具调用与文案。

**参考路径**：`modes/travel/state_machine.py`

---

## Fast-B B 轨 RAG

**综合评分**：8/10

### 主题目 1 · 入库五阶段

**问**：Load / Split / Transform / Embed / Upsert 五阶段各解决什么问题？（各一句话）

**标准答案**：

1. **Load**：加载并解析源文件为 Document。
2. **Split**：切分为 Chunk，控制粒度与重叠。
3. **Transform**：增强 Chunk（重组、元数据、图片描述等）。
4. **Embed**：生成 Dense（语义向量）与 Sparse/BM25（关键词索引）。
5. **Upsert**：写入 chromadb 与 BM25 索引，持久化到 collection。

**参考路径**：`src/ingestion/pipeline.py`

---

### 主题目 2 · 检索四步链

**问**：一次 query 从用户问题到返回证据，依次经过哪四步？每步作用是什么？

**标准答案**：

1. **查询预处理**：整理/改写用户问题便于检索。
2. **双路召回**：Dense（语义）与 BM25（关键词）各 Top-K。
3. **RRF 融合**：合并两路排名，不依赖分数尺度对齐。
4. **Rerank 精排**：强模型重排；失败则 Fallback 回粗排结果。
5. **响应构建**：组装 Citation 证据返回。

**参考路径**：`src/core/query_engine/`、`hybrid_search.py`、`reranker.py`

---

### 主题目 3 · MCP 三工具

**问**：rag-server 对外 MCP 哪三个工具？各自用途？知识库模式推荐调用顺序？

**标准答案**：

1. **`list_collections`**：列出 collection 及文档数量，供选库。
2. **`query_knowledge_hub`**：指定 collection 混合检索，返回片段与 Citation。
3. **`get_document_summary`**：按 doc_id 获取文档级摘要。
4. **推荐顺序**：list → query →（必要时）summary。

**参考路径**：`src/mcp_server/tools/`、`modes/knowledge_qa/system.md`

---

### 简单追问 · 双路召回

**问**：为何 Dense（语义）与 BM25（关键词）两路一起用，而不是只留一路？

**标准答案**：

- **Dense** 擅长大意、同义表达（如「年假」≈「带薪休假」）；**BM25** 擅长精确词项、专有名词。
- 单一路易漏召回：纯语义可能漏术语；纯关键词可能漏 paraphrase。
- **RRF 融合**兼顾查准与查全，是生产 RAG 常见做法。

**参考路径**：`hybrid_search.py`

---

## Fast-4 串讲与实操

**综合评分**：7.5/10

### 主题目 1 · 60 秒口述

**问**：约 60 秒口述全栈主链路（须含双项目职责、MCP 连接、检索四步、谁生成答案、三模式）。

**标准答案**：

须覆盖以下要点（顺序可灵活，逻辑通顺即可）：

- monorepo：`agents-master` Host + `rag-server` RAG，MCP stdio 解耦、互不 import
- 用户提问 → ReAct → MCP → rag-server 三工具
- 检索链：预处理 → Dense+BM25 双路召回 → RRF → Rerank → Citation 证据
- **Host LLM 生成**最终答案；rag-server 不生成长回答
- 入库独立 ingest 五阶段；三模式裁剪工具集；旅行可选提状态机

**参考路径**：`knowledge-fast.md` §4 电梯陈述模板

---

### 主题目 2 · 全栈开场重亮点串讲

**问**：全栈岗面试开场，请按推荐讲述顺序口述约 9 条重亮点，每条用一句话说清**技术/design 要点**（不需背知识点 ID）。

**标准答案**：

按 `knowledge-fast.md`「推荐讲述顺序（全栈 90 秒）」：

1. monorepo 双项目：Host 编排对话与工具，rag-server 专责入库与检索，MCP stdio 解耦、互不 import。
2. 主链路：提问 → ReAct → MCP → 混合检索 → **Host LLM 生成**（rag-server 不生成）。
3. 边界：rag-server 只返回检索证据（含 Citation）；chromadb 仅 RAG 侧触及。
4. LangGraph ReAct：决策 → 调工具 → 结果回写上下文 → 再决策，直到可回答。
5. `resolve_mcp_config`：monorepo 路径解析、rag-server venv 优先、密钥环境变量注入。
6. 三模式按场景裁剪工具与 Prompt：通用全量 / 旅行强流程 / 知识库 RAG 专注。
7. Dense（语义）+ BM25（关键词）双路召回，RRF（合并两路结果）融合。
8. 粗排后 Rerank（强模型精排），失败自动 Fallback。
9. MCP 三工具：`list_collections` / `query_knowledge_hub` / `get_document_summary`。

**另 3 条重亮点**（按岗位加深，非开场必背）：旅行五阶段状态机；入库五阶段；工厂+YAML 可插拔。

**参考路径**：`knowledge-fast.md` §12 个必讲重亮点

---

### 主题目 3 · 联调排障

**问**：知识库问答检索无结果或工具失败，按什么顺序排查？至少 4 项。

**标准答案**：

1. **Key**：`agents-master/.env` 与 `rag-server/config/settings.yaml` 是否有效。
2. **双 venv**：rag-server 是否独立安装；`resolve_mcp_config` 是否用到正确 Python。
3. **是否已入库**：目标 collection 是否存在、是否有文档。
4. **collection 名称**是否选对。
5. **embedding 一致**：入库与检索是否同一 embedding 模型。
6. **（扩展）** MCP 子进程 spawn、cwd 路径、工具/LLM 报错信息。

**参考路径**：`agents-master/README.md` 常见问题

---

### 简单追问 · 为何 monorepo 不合并

**问**：「为什么不用一个 Python 项目搞定 Host + RAG」你怎么答？

**标准答案**：

1. **依赖隔离**：RAG 需 chromadb 等重型包，Host 重 UI/Agent；双 venv 避免冲突。
2. **职责边界**：RAG 可独立测试（`scripts/query.py`）、独立演进；Host 换框架不动 RAG。
3. **MCP 协议**：跨进程工具标准，stdio 解耦，可独立重启与版本。
4. **分工与扩展**：monorepo 便于联调，运行时仍两进程，符合微服务/MCP 思想。

**参考路径**：根 `README.md`、`docs/project-design/MCP设计与管理.md` §1.5

---

<!-- 追加格式（无用户回答摘要、无薄弱点）：

## Fast-X …

**综合评分**：X/10

### 主题目 N · 小标题

**问**：……

**标准答案**：

1. …

**参考路径**：……

-->
