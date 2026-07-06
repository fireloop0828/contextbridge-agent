# Fast QA — 快速通读（Fast 轨）

> 记录 Bridge Learn **Fast** 段末问答与标准答案。  
> 题目见 `.cursor/skills/bridge-learn/references/knowledge-fast.md` 各段「段末问答」。  
> 每段问答结束（含简单追问）后由 Agent **追加**；用户说「跳过记录」时不写。

### 标准答案撰写准则

- **叙述优先**：用连贯完整句讲清「是什么 → 为什么 → 怎么做」，读者不查代码也能跟上逻辑。
- **一问多问须编号**：题目含多个子问题时，标准答案用 **1. 2. 3.** 分条作答，每条对应一问，子问标题可简短加粗（如 `1. **模式包是什么`**）。
- **路径/函数作锚点**：仅在关键落点顺带提及；括号内用白话注明作用，例如 `rebuild_agent_only()`（切模式时只重建 Agent，不重新 spawn MCP）。
- **忌堆砌**：不把函数名、文件名串成列表当作正文；**参考路径**单独一节，供深入阅读。

### 记录结构（Part II）

- 每个 Part II 块**只有一个**二级标题：`## Fast-5A` / `## Fast-5B` / `## Fast-5C`。
- 每学完一个专题/环节，在其下**追加**三级标题：`### 专题 N` 或 `### 环节 N`（含主题目 + 简单追问）；**不要**重复创建 `## Fast-5X`。

## 目录

- [Fast-0 全局主链路](#fast-0-全局主链路)
- [Fast-C C 轨串联](#fast-c-c-轨串联)
- [Fast-A A 轨 Host](#fast-a-a-轨-host)
- [Fast-B B 轨 RAG](#fast-b-b-轨-rag)
- [Fast-4 串讲与实操](#fast-4-串讲与实操)
- [Fast-5A Agent 亮点](#fast-5a-agent-亮点)（Part II · 5A 已完成）
- [Fast-5B RAG 检索亮点](#fast-5b-rag-检索亮点)（Part II · 环节 1–2 已完成）
- [Fast-5C 工程化亮点](#fast-5c-工程化亮点)（Part II，待学后追加）

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

## Fast-5A Agent 亮点

### 专题 1 · 三模式编排

**综合评分**：8/10

#### 主题目 1 · 三模式编排

**问**：用你自己的话说明：什么是「模式包」？为什么切模式用 `rebuild_agent_only` 而不是每次都重连 MCP？知识库和旅行分别靠什么机制约束 Agent——各对应哪个文件？

**标准答案**：

1. **模式包是什么**：本项目把通用、知识库、旅行三种场景的差异，各自收进 `modes/<name>/` 文件夹（模式包），像装插件——里面有该模式的进出场逻辑和专用提示词。所有模式对外遵守同一套约定（`AgentMode` 协议，定义在 `types.py`），再通过注册表 `registry.py` 集中登记；加第四种模式只需新文件夹加一行注册，不必在 `app.py` 里到处写分支。
2. **为什么切模式用 `rebuild_agent_only`**：切换侧边栏模式时，走 `rebuild_agent_only()`（只换 Agent 的 Prompt 和推理图），而不是每次 `reconnect_agent()`（重新 spawn MCP 子进程并拉工具列表）。因为拉起 rag-server 等子进程很慢、界面会白屏；三种模式本来就可以共用同一批已连上的 MCP 工具，没必要重复连接。
3. **知识库与旅行各靠什么约束、对应哪个文件**：知识库主要靠 `modes/knowledge_qa/system.md` 里的专用系统提示词做**软约束**——告诉 LLM 优先按「列库 → 检索 → 摘要」走 RAG，禁止编造；代码里并没有删掉地图、导出工具，工具仍全挂着，靠 Prompt 引导行为。旅行是多步、强顺序流程，光靠叮嘱不够，所以用 `state_machine.py` 规定阶段只能按顺序推进，再由 `handler.py` 在每次调用 LangGraph **之前**介入，决定本轮能给 Agent 什么输入——这是**硬编排**。注册表管的是「切换到哪个模式」，不管旅行内部的步骤顺序。

**参考路径**：`modes/types.py`、`modes/registry.py`、`app.py`（`rebuild_agent_only`）、`modes/knowledge_qa/system.md`、`modes/travel/state_machine.py`、`modes/travel/handler.py`

---

#### 简单追问 · 知识库约束

**问**：知识库模式现在有没有在代码里删掉地图/导出工具？实际靠什么让 Agent 优先走 RAG？若以后要更硬隔离，文档建议怎么做？

**标准答案**：

1. **有没有删掉地图/导出工具**：**没有**。知识库模式并未在代码里物理删掉地图、导出等工具，Agent 仍能看到全部 MCP 工具。
2. **实际靠什么优先走 RAG**：靠 `system.md` 的 Prompt 引导 LLM 优先使用 RAG 三工具（列库、检索、摘要），属于软约束，而非硬裁剪工具列表。
3. **更硬隔离时文档建议**：按模式过滤工具列表，只把 RAG 相关工具传给知识库模式；或升级为多个 Agent，各自绑定不同工具子集。

**参考路径**：`modes/knowledge_qa/system.md`、`docs/project-design/多模式Agent架构选型.md` §工具硬隔离

---

### 专题 2 · AgentMode + registry

**综合评分**：7/10

#### 主题目 2 · registry 与切换

**问**：`AgentMode` 协议和 `registry` 分别解决什么麻烦？「换侧边栏模式」和「改 config.json 里的 MCP」在代码里走哪两个不同函数？意图路由为什么只在通用模式跑？

**标准答案**：

1. **AgentMode 协议解决什么**：每种模式都要做侧边栏文案、占位符、Prompt、进出场、意图检测等「外壳能力」，但实现细节不同。`AgentMode` 协议（`types.py`）用接口约定统一这些能力，各模式包独立实现即可，无需继承基类——加新模式时避免在 `app.py` 里复制粘贴、漏改某处。
2. **registry 解决什么**：若 UI 切换、自动意图路由、拼 Prompt 各写一套 `if mode == "travel"`，一定乱。注册表 `registry.py` 是所有「找模式、切模式、拼 Prompt」的**唯一入口**：`_MODE_MODULES` 集中登记，`get_mode` / `enter_mode` / `build_system_prompt` / `route_by_intent` 都走这里；注册顺序还表达优先级（旅行意图扫描排在知识库前）。
3. **换模式 vs 改 MCP 走哪两个函数**：换侧边栏模式走 `rebuild_agent_only()`（只重建 Agent 的 Prompt 和推理图，复用已缓存的 `mcp_tools`）；改 `config.json` 里的 MCP 配置走 `reconnect_agent(reload_mcp=True)`（重新 `initialize_session`、spawn 子进程、拉工具列表）。`on_enter` 返回是否需要重建 Agent，侧边栏据此选 rebuild 还是 reconnect。
4. **意图路由为什么只在通用模式跑**：`route_by_intent` 仅在 `current_mode_id == general` 时扫描其他模式的 `detect_intent()`。通用模式是「还没选定场景」的入口——用户说「帮我规划北京三日游」应自动进旅行。若用户已在旅行或知识库流程中，不应再被自动切走（尤其旅行有多步状态）；专用模式内由该模式自己的逻辑接管。

**参考路径**：`modes/types.py`、`modes/registry.py`（`route_by_intent`、`enter_mode`）、`app.py`（`rebuild_agent_only`、`reconnect_agent`）、`ui/chat.py`、`ui/sidebar.py`

---

#### 简单追问 · 意图与手动同路径

**问**：`route_by_intent` 在通用模式里扫到「旅行」意图后，和用户点侧边栏切到旅行模式，后续是不是走同一套切换逻辑？为什么这样设计？

**标准答案**：

1. **是不是同一套**：是。意图命中后调用 `enter_mode()`，再根据返回值走 `rebuild_agent_only()`（或首次未初始化时 `reconnect_agent()`）；侧边栏手动切换同样经 `enter_mode` + rebuild/reconnect，无单独分支。
2. **为什么这样设计**：自动路由和手动切换行为一致，避免「点侧边栏能进旅行、打字触发却走另一套逻辑」的 bug；也保证 Prompt、模式状态、Agent 重建规则统一，符合注册表「唯一入口」的设计。

**参考路径**：`ui/chat.py`（`route_by_intent` → `enter_mode` → `rebuild_agent_only`）、`ui/sidebar.py`（`_apply_pending_mode_switch`）

---

### 专题 3 · 旅行模式亮点

**综合评分**：7.5/10

#### 主题目 3 · 旅行工程化

**问**：旅行模式「状态机」和「handler/pipeline」各管什么？`facts`、`export_service` 分别解决 Token/流程里的什么问题？为什么这套逻辑放在 LangGraph 外面？

**标准答案**：

1. **状态机 vs handler/pipeline 各管什么**：`state_machine.py` 管**阶段与规则**——定义 POI 选择 → 需求采集 → 生成 → 改稿等阶段、合法跳转，以及 intake 字段合并与阶段推进逻辑。`handler.py` 是**回合编排入口**——在 `ui/chat.py` 里于 LangGraph 调用**前后**介入：`prepare_before_agent()` 推进 phase、决定本轮给 Agent 的 query；`process_after_agent()` 清洗回复、判定是否成稿、组装导出正文。`pipeline.py` 管**阶段内 MCP 预取**——按当前 phase 异步调 RAG、高德等，解析结果写入 `facts`，在生成/交付前补齐数据。
2. **facts 与 export_service 各解决什么**：`facts.py` 从对话抽出结构化 intake（目的地、天数、预算等），驱动阶段门禁与预取，比纯聊天记录可靠；配合 `tool_memory.py` 缓存工具结论摘要、在工具回合后裁剪 checkpoint，减轻多轮 ReAct 的上下文膨胀。`export_service` 解决的是**导出环节 Token**：LLM 已在聊天区输出完整攻略一次，检测到 `plan_ready` 后由服务端把正文**复制写盘**（可附加 facts 附录），**0 额外 LLM Token**，避免再调 `write_markdown_document` 让模型传第二遍全文。
3. **为什么放在 LangGraph 外面**：旅行要强顺序、要先预取再生成、成稿后要自动写盘——这些用 Python 编排比堆 LangGraph 节点更清晰；图内仍保持**单个 ReAct Agent**，复杂度外置而不改图结构。

**参考路径**：`modes/travel/state_machine.py`、`handler.py`、`pipeline.py`、`facts.py`、`tool_memory.py`、`export_service.py`、`ui/chat.py`、`ui/travel_evidence.py`

---

#### 简单追问 · 成稿与写盘

**问**：成稿后用户在聊天区能看到什么？`travel_evidence` 展示的是什么？`export_service` 省的是哪一步的 Token？

**标准答案**：

1. **聊天区看到什么**：用户仍能在聊天区看到 LLM 输出的**完整攻略正文**（可能经 `format_travel_plan_display` 增强展示），不是只看摘要。
2. **travel_evidence 展示什么**：外置的是**工具依据**——RAG 命中片段、天气、POI 卡片等预取/工具结果，方便用户核对「数据从哪来」，不是把成稿移出聊天。
3. **export_service 省哪步 Token**：省的是**第二遍输出**——不再让 LLM 通过 MCP `write_markdown_document` 把同样 Markdown 再传一次；写文件由服务端复制 `export_body` 完成（见 `Token消耗分析与优化.md` §2.3 O5）。

**参考路径**：`agents-master/README.md`（旅行导出）、`docs/test-analysis/Token消耗分析与优化.md` §2.3、`modes/travel/handler.py`（`export_body`）、`ui/travel_evidence.py`

---

### 专题 4 · Agent 工程化亮点

**综合评分**：8/10

#### 主题目 4 · MCP / 工具 Token 治理 / 记忆分源

**问**：monorepo 下 `resolve_mcp_config` 解决什么配置难题？超大工具返回如何治理 Token（当前落地做法）？用户记忆和公司文档检索为什么必须分源？

**标准答案**：

1. **`resolve_mcp_config` 解决什么**：`config.json` 只写声明式「意图」（相对路径、通用 `python` 命令、`${ENV}` 占位符），换机器或 monorepo 布局一变就容易 spawn 失败，密钥也不宜明文进 Git。解析层 `resolve_mcp_config()`（`config/mcp_config.py`）在运行时把配置变成可执行形态：相对 `cwd` → 基于 Host 目录的绝对路径；`python` 命令 → 当前解释器或 rag-server 子项目 `.venv` 里的 Python；`env` / `args` 里的 `${VAR}` → 从 `.env`/环境变量注入真实 Key——一层解析即可稳定拉起各 MCP 子进程。
2. **工具结果 Token 如何治理（当前落地）**：地图、RAG 等一次返回可达上万字，ReAct 每轮把 tool result 塞进 checkpoint messages，上下文迅速膨胀；各 MCP 自行控长难以统一，治理应在 **Host 侧**做，但不等于「统一硬截断」。
  - **O6 未启用**：`tool_truncation.py` 的 `wrap_tools_with_output_limit()` **保留代码、未接入** `app.py`（`_build_agent_from_tools` 直接把原始 MCP 工具交给 `ToolNode`）。当轮硬截断易丢尾部关键字段，影响同轮推理。
  - **旅行模式分层做法**（见 `docs/test-analysis/Token消耗分析与优化.md`）：
    - **当轮 ReAct**：ToolMessage **全量**保留，保证本轮工具链推理完整。
    - **编排层预取**（`pipeline.py` + `facts.py`）：POI/生成阶段在调 LangGraph **之前**由 Host 调 MCP，解析为结构化 `travel_facts`（如 RAG excerpt≤400 字、POI 关键字段），注入 `[TRAVEL_FACTS]`，并配合 checklist 约束 Agent 少重复调工具。
    - **跨回合 O7**（`tool_memory.py`）：回合结束 `ingest_tool_round_memory()` 写工具结论摘要 → `trim_checkpoint_after_tool_ingest()` **换 `thread_id` 清 checkpoint**；下轮靠 `[TRAVEL_CONTEXT]` 注入摘要，而非 L1 扛全量 ToolMessage 历史。
    - **辅以 O2/O8**：POI 结束进 intake/generating 时换 thread；按阶段收紧 `recursion_limit`。
  - **原则**：优先**结构化提取 + 跨回合摘要 + checkpoint 重置**；`tool_truncation` 是可复用的备选方案，非当前主路径。
3. **用户记忆与文档检索为何分源**：「用户喜欢川菜」是**主观画像**，「公司年假制度」是**客观文档知识**——语义、更新频率、权限模型都不同。实现上用户记忆走 Host 本地 `memory_store.py` + `memory_recall.py`（embedding 画像，对话前召回）；公司文档走 rag-server 的 chromadb，经 MCP `query_knowledge_hub` 按需检索。存储、触发点、数据源三者分离，避免混库、也便于面试讲清边界。

**参考路径**：`config/mcp_config.py`、`modes/travel/pipeline.py`、`modes/travel/facts.py`、`modes/travel/tool_memory.py`、`tool_truncation.py`（未启用）、`memory_store.py`、`memory_recall.py`、`docs/test-analysis/Token消耗分析与优化.md`

---

#### 简单追问 · resolve 解析什么

**问**：`resolve_mcp_config` 读入 `config.json` 后，具体会解析/transform 哪三类东西，才交给 MCP Client 去 spawn 子进程？

**标准答案**：

1. **工作目录（cwd）**：相对路径规范化为基于 `agents-master` 的**绝对路径**，保证子进程在正确目录启动（如 rag-server 根目录）。
2. **启动命令（command/args）**：`python`/`python3` 解析为实际解释器——rag-server 优先用其 `.venv/bin/python`，其他脚本用当前 Host 解释器；`args` 中的 `${VAR}` 占位符替换为环境变量；高德等还可解析为本地 `npx` 缓存二进制以减少冷启动。
3. **子进程环境（env）**：将 `config.json` 里 `env` 字段的 `${API_KEY}` 等占位符替换为 `.env` 中的真实密钥（如 `AMAP_MAPS_API_KEY`），再交给 `MultiServerMCPClient` spawn stdio 子进程。

**参考路径**：`config/mcp_config.py`（`resolve_mcp_config`、`_interpolate_env_vars`、`_resolve_rag_server_python`）

---

## Fast-5B RAG 检索亮点

### 环节 1 · 查询预处理

**综合评分**：8/10

#### 主题目 1 · 预处理

**问**：为什么 `QueryProcessor` 用规则而不是 LLM 改写？它输出什么结构？Dense 和 Sparse 分别用里面的哪个字段？

**标准答案**：

1. **为什么用规则而不是 LLM 改写**：用户问句口语化、带停用词，直接检索 BM25 噪声大；LLM 改写虽灵活但慢、有随机性、难单测。`QueryProcessor` 用 jieba 分词 + 停用词表 + 正则解析等**确定性规则**——快、稳定、零额外 Token，可写 unit test。
2. **输出什么结构**：统一对象 `ProcessedQuery`，一次预处理、两路复用。里面同时带好 `original`（归一化后的原句）、`keywords`（去停用词后的关键词列表）、`filters`（从 query 语法解析出的筛选条件）。
3. **Dense 和 Sparse 各用哪个字段**：`DenseRetriever` 用 `original` 做 embedding（保留完整语义）；`SparseRetriever` 用 `keywords` 做 BM25（关键词匹配更准）。  
  
**检索前的"清洗工"**：
  - **jieba 分词**：把中文拆成词。
  - **停用词表**：去掉无意义的词。
  - **正则解析**：提取版本号、日期、邮箱等固定格式信息。
  - **确定性规则**：统一大小写、同义词、格式等。

**参考路径**：`rag-server/src/core/query_engine/query_processor.py`

---

#### 简单追问 · filters

**问**：`ProcessedQuery` 里的 `filters` 是干什么用的？能从用户 query 里解析出什么例子？

**标准答案**：

1. **干什么用**：把用户写在问句里的**结构化筛选意图**抽出来，供检索层直接筛库/筛文档，不必让 Host LLM 另猜 collection 名或元数据条件。
2. **解析例子**：`QueryProcessor._extract_filters()` 用 `key:value` 语法从 query 中提取，并从剩余文本里剥掉这些片段再分词。例如 `collection:hr_docs 年假制度` → `filters={"collection": "hr_docs"}`，剩余文本用于 `keywords`；还支持 `doc_type:`、`source_path:`、`tag:` 等。

**参考路径**：`rag-server/src/core/query_engine/query_processor.py`（`_extract_filters`）

---

### 环节 2 · 混合检索

**综合评分**：8/10

#### 主题目 2 · 混合检索

**问**：`HybridSearch` 在整条链里扮演什么角色（「不算分」意味着什么）？一路检索失败时系统怎么处理？Top-K 参数从哪读？

**标准答案**：

1. **HybridSearch 扮演什么角色**：它是**编排器**——负责 `QueryProcessor` 预处理 → 调 Dense/Sparse 两路召回 → 把结果交给 `RRFFusion` 融合，再送精排。「不算分」意味着它**不自己算 query 与 chunk 的相似度**，打分逻辑分别在 `DenseRetriever`（向量余弦）和 `SparseRetriever`（BM25）里，换一路检索不必改 `HybridSearch` 核心编排。

2. **一路失败怎么处理**：`_run_parallel_retrievals()` 用 `ThreadPoolExecutor` 并行跑两路；任一路异常时不抛到 MCP 层，而是 **Graceful Degradation**——标记 `used_fallback=True`，用另一路仍成功的结果继续后续融合与精排，查询不白屏。

3. **Top-K 从哪读**：`dense_top_k`、`fusion_top_k` 等从 `settings.yaml` 加载，经 `Settings` 注入 `HybridSearch.__init__()`——调召回宽度只改配置，不改 Python 代码。

**参考路径**：`rag-server/src/core/query_engine/hybrid_search.py`、`dense_retriever.py`、`sparse_retriever.py`、`config/settings.yaml`

---

#### 简单追问 · 并行与降级标记

**问**：Dense 和 Sparse 两路是串行还是并行跑？一路失败时，`used_fallback` 标记有什么用？

**标准答案**：

1. **串行还是并行**：**并行**。`ThreadPoolExecutor(max_workers=2)` 同时跑 Dense 与 Sparse，总延迟大约等于两路中较慢那路（≈max(两路)），而不是相加。

2. **`used_fallback` 有什么用**：标记本次查询走了**降级路径**（某一路检索失败，只用了另一路结果）。它会写入检索 Trace/响应元数据，便于排查「结果是单路召回还是双路融合」，也能区分「没召回」和「一路挂了但另一路顶上」。

**参考路径**：`rag-server/src/core/query_engine/hybrid_search.py`（`_run_parallel_retrievals`、`used_fallback`）

---

