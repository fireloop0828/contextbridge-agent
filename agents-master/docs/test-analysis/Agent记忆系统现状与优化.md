# Agent 对话记忆系统

> 文档版本：**v4.1**  
> 更新日期：2026-06-09  
> 范围：`agents-master` 全 Agent（通用 + 旅行）

**「记忆」定义：** 使用界面时产生的提问、回复、工具记录及从中提炼的状态。  
**不含：** RAG 知识库、System Prompt、MCP 工具定义（见 [附录 A](#附录-a-不属于对话记忆)）。

---

## 目录

1. [30 秒看懂](#1-30-秒看懂)
2. [四层记忆架构](#2-四层记忆架构)
3. [何时写入 / 何时读出](#3-何时写入--何时读出)
4. [存储一览](#4-存储一览)
5. [一轮对话全流程](#5-一轮对话全流程)
6. [L4 向量召回 vs RAG](#6-l4-向量召回-vs-rag)
7. [长期记忆（L4）](#7-长期记忆l4)
8. [设计与演进建议（技术 / 面试）](#8-设计与演进建议技术--面试)
9. [代码与数据路径](#9-代码与数据路径)

- [附录 A：不属于对话记忆](#附录-a-不属于对话记忆)
- [附录 B：修订记录](#附录-b-修订记录)

---

## 1. 30 秒看懂

```text
┌─────────────────────────────────────────────────────────────────┐
│  L1 短期推理   checkpoint（MemorySaver + thread_id）             │
│              → AI 当页连续推理；刷新 / 换 thread 即失              │
├─────────────────────────────────────────────────────────────────┤
│  L2 界面展示   history（聊天气泡）                                │
│              → 给人看；不自动进 LLM                               │
├─────────────────────────────────────────────────────────────────┤
│  L3 会话快照   latest.json / archives/*.json                     │
│              → 恢复 UI + 旅行进度；latest=当前场，archives=历史场   │
├─────────────────────────────────────────────────────────────────┤
│  L4 长期记忆   profile.json + 本地 Chroma（user_memory）          │
│              → 跨会话偏好 / 任务 / 会话摘要；与 RAG 分离             │
└─────────────────────────────────────────────────────────────────┘
```


| #   | 规则                                              |
| --- | ----------------------------------------------- |
| 1   | AI **当页接着聊** → L1 checkpoint（**不是** L2 history） |
| 2   | **刷新后**气泡和旅行进度回来 → L3（checkpoint **回不来**）       |
| 3   | **跨会话**还记得偏好 / 做过什么 → L4（须归档 / 导出 / 显式记住触发写入）   |


**latest 与 archives：** 快照 **内容结构相同**（≤40 条 history + travel 块等）。`latest` = 当前这一场、覆盖写；`archives` = 点「新对话（归档）」时封存已结束的那一场，并可从侧边栏恢复。

---

## 2. 四层记忆架构


| 层      | 名称   | 位置                          | 持久         | 消费者         | 典型内容                                  |
| ------ | ---- | --------------------------- | ---------- | ----------- | ------------------------------------- |
| **L1** | 短期推理 | `MemorySaver` + `thread_id` | ❌          | AI          | 本 thread 内 user / assistant / tool 消息 |
| **L2** | 界面历史 | `st.session_state.history`  | ❌；L3 可恢复部分 | 人           | 聊天气泡                                  |
| **L3** | 会话快照 | `data/sessions/`            | ✅          | 人恢复 UI      | history≤40、intake、工具摘要、偏好             |
| **L4** | 长期记忆 | `data/memory/`              | ✅          | AI 注入 + 侧边栏 | profile 结构化字段 + 会话摘要向量                |


**旅行模式额外（会话内提炼，进 L3 / 下轮 prompt，非独立层）：** `travel_intake`、`travel_tool_memory`（最近 6 回合）、`data/outputs/*.md`（正文在磁盘，记忆层只存路径）。

---

## 3. 何时写入 / 何时读出

### 3.1 写入


| 事件          | L1          | L2  | L3                  | L4                      | 入口                        |
| ----------- | ----------- | --- | ------------------- | ----------------------- | ------------------------- |
| 每轮对话成功      | ✅           | ✅   | ✅ latest            | —                       | `ui/chat.py`              |
| **新对话（归档）** | 🔄 新 thread | 清空  | ✅ archives，删 latest | ✅ pipeline              | `archive_current_session` |
| **重置对话**    | 🔄          | 清空  | ❌ 删 latest          | —                       | `sidebar`                 |
| 刷新页面        | ❌ 内存丢失      | ❌   | 磁盘仍在                | 仍在                      | —                         |
| 恢复快照 / 归档   | 仍空          | ✅   | 读入                  | —                       | `apply_snapshot`          |
| **旅行导出成功**  | —           | ✅   | ✅                   | ✅ pipeline              | `ui/chat.py`              |
| **显式「记住…」** | —           | ✅   | ✅                   | ✅ pipeline              | `ui/chat.py`              |
| App 启动      | —           | —   | —                   | 📖 profile → session 偏好 | `app.py`                  |


L3 自动保存条件：已有 history，或旅行模式已有目的地 / 工具摘要。

### 3.2 读出（AI 侧）


| 场景          | 数据源                  | 注入方式                                           |
| ----------- | -------------------- | ---------------------------------------------- |
| 每轮发消息       | L4 profile           | `[USER_MEMORY]` 块（`memory_recall.py`）          |
| query ≥ 4 字 | L4 本地 Chroma         | 同上，Top-3 相关摘要（**不走 RAG**，见 §6）                 |
| 同页连续聊       | L1 checkpoint        | LangGraph 按 `thread_id` 自动加载                   |
| 旅行每轮        | intake + tool_memory | `[TRAVEL_CONTEXT]` 包装用户消息                      |
| 旅行改稿        | 导出 md / 内存正文         | `[PREVIOUS_PLAN]`                              |
| 领域知识        | RAG（rag-server）      | ReAct **工具** `query_knowledge_hub`（当轮 tool 消息） |


---

## 4. 存储一览

```text
agents-master/data/
├── sessions/
│   ├── latest.json           # L3 当前场（1 份，覆盖）
│   └── archives/*.json       # L3 历史场（归档产生，结构同 latest）
├── memory/
│   ├── profile.json          # L4 结构化
│   └── chroma/               # L4 向量（collection: user_memory）
└── outputs/*.md              # 成品；L4 只存路径指针
```


| 项目                   | 限制           |
| -------------------- | ------------ |
| 快照 history           | 40 条         |
| tool_memory          | 6 回合         |
| profile recent_tasks | 20 条         |
| 向量摘要                 | ~200 条，滚动删最旧 |


**L3 与 L4 区别：** archives 是 **整包快照**（可恢复 UI）；Chroma 是 **一句摘要向量**（供语义检索，不可恢复聊天气泡）。

---

## 5. 一轮对话全流程

本节回答：**用户点发送后，数据往哪走、Agent 实际看到什么。**

### 5.1 三个面：各写各的

同一轮用户消息会同时触及三条链路，**互不替代**：


| 面                           | 存什么                                | 本轮是否写入                    |
| --------------------------- | ---------------------------------- | ------------------------- |
| **给人看（L2）**                 | 界面气泡原文                             | 回复成功后 append history      |
| **给 AI 推理（L1 + prompt 包装）** | checkpoint + 本条 HumanMessage 里的包装块 | 请求时读旧 checkpoint；成功后追加新消息 |
| **给将来恢复（L3 / L4）**          | 磁盘快照 / 长期库                         | 成功后写 latest；满足条件时写 L4     |


### 5.3 时序（按时间顺序）

**阶段 A — 发消息前（`ui/chat.py`）**


| 步骤  | 动作                                                                          | 层        |
| --- | --------------------------------------------------------------------------- | -------- |
| A1  | 用户输入 `user_query`（界面将展示原文）                                                  | —        |
| A2  | [旅行] `handle_travel_user_message`：合并 intake、算 phase，拼 `[TRAVEL_CONTEXT]`    | 会话内提炼    |
| A3  | [旅行] 若 POI→intake 切换：`reset_agent_thread_o9()` **换 thread_id**              | L1 下轮起为空 |
| A4  | `wrap_query_with_user_memory`：读 L4 profile + 本地 Chroma 检索 → `[USER_MEMORY]` | L4 读     |
| A5  | 调用 `process_query(agent_query, …)`                                          | —        |


**阶段 B — Agent 运行中（`app.py`）**


| 步骤  | 动作                                                        | 层        |
| --- | --------------------------------------------------------- | -------- |
| B1  | LangGraph ReAct：读 checkpoint + 本轮 HumanMessage，多步 tool 调用 | L1 读 + 写 |
| B2  | [旅行] 工具可能调 RAG MCP → 结果进 **ToolMessage**（非 L4）            | RAG 当轮   |
| B3  | 流式返回 assistant 文本与 tool 输出                                | —        |


**阶段 C — 回复成功后**


| 步骤  | 动作                                                                                             | 层                     |
| --- | ---------------------------------------------------------------------------------------------- | --------------------- |
| C1  | [旅行] `finalize_assistant_turn`：解析 `TRAVEL_INTAKE`、更新 phase                                     | 会话内提炼                 |
| C2  | L2：`history` += user / assistant / (tool)                                                      | L2 写                  |
| C3  | [旅行] 有 tool：`ingest_tool_round_memory` → `trim_checkpoint_after_tool_ingest()` **换 thread_id** | L1 清空；摘要进 tool_memory |
| C4  | `save_latest_autosave()`                                                                       | L3 写                  |
| C5  | 若导出成功 / 显式「记住」：`memory_pipeline`                                                               | L4 写                  |


---

## 6. L4 向量召回 vs RAG

**结论：L4 向量召回不走 rag-server，也不共用 RAG 的 Chroma collection。**


| 维度             | L4 用户记忆（`data/memory/chroma`）             | RAG（`rag-server`）                 |
| -------------- | ----------------------------------------- | --------------------------------- |
| **存什么**        | 用户会话 **一句摘要**（episodic）                   | **领域文档** chunk（景点、攻略 PDF 等）       |
| **谁写入**        | `memory_pipeline` 归档 / 导出 / 显式记住          | `rag-server` ingest 脚本            |
| **谁检索**        | `memory_store.search_session_summaries()` | Agent 调 MCP `query_knowledge_hub` |
| **何时进 LLM**    | 发消息前 **预注入** `[USER_MEMORY]`              | ReAct **当轮** tool 返回              |
| **Chroma 路径**  | `agents-master/data/memory/chroma`        | `rag-server/data/db/chroma`       |
| **Collection** | `user_memory`                             | 各业务 collection（如旅行知识库）            |
| **Embedding**  | 百炼 `text-embedding-v3`（agents 进程内）        | rag-server 配置的 embedding          |
| **检索 API**     | 进程内 `coll.query(query_texts=…)`           | MCP 工具，Hybrid Search 等            |


```text
用户发消息
    │
    ├─► [预注入，非 tool]  memory_recall → 本地 Chroma user_memory
    │                      + profile.json
    │
    └─► [ReAct 按需]       Agent 决定调 query_knowledge_hub → rag-server
```

**为何分离：** RAG 是 **静态领域知识**；L4 是 **该用户使用史**。混库会导致检索污染（用景点文档回答「我上次去哪」）且生命周期、权限、更新频率不同。

**面试可讲：** 这是 **Profile（结构化）+ Episodic Vector（叙述摘要）** 与 **Document RAG** 的三路记忆；L4 向量是 **write-on-archive 的轻量 episodic store**，不是替代 RAG，也不是把 chat log 做 RAG ingest。

---

## 7. 长期记忆（L4）

### 7.1 流水线

```text
触发（归档 / 旅行导出 / 显式记住）
  → 从快照收集候选（偏好、intake、导出路径、显式句）
  → 规则 + LLM 判「值不值得记」
  → 敏感 regex 拦截
  → profile.json（结构化覆盖/追加）
  → Chroma user_memory（一句摘要，近重复跳过）
```

### 7.2 记 / 不记


| ✅ 记                 | ❌ 不记         |
| ------------------- | ------------ |
| 偏好、稳定事实、任务结论 + 导出路径 | 工具 API 细项    |
| intake 终稿（够完整时）     | 全文 chat、密钥证件 |
| 显式「请记住…」            | 未验证猜测        |
| 会话一句摘要（向量）          | phase 临时态    |


偏好同字段以 **最近一次归档** 为准覆盖 profile。

### 7.3 与 L3 分工


|      | L3 latest / archives   | L4                   |
| ---- | ---------------------- | -------------------- |
| 目的   | 恢复 **整段** 会话 UI        | 跨会话 **facts + 摘要**   |
| 粒度   | 多字段快照                  | profile 字段 + 1 句/次向量 |
| 归档关系 | 归档时 **作为 pipeline 输入** | 归档时 **产出**           |


---

## 8. 设计与演进建议（技术 / 面试）

从 **架构合理性、Token 经济学、一致性、可扩展** 分析；不仅列产品痛点。

### 8.1 当前设计的可取之处（面试先讲优点）

1. **读写分离清晰：** L2 展示 / L1 推理 / L3 灾备 / L4 跨会话，避免「把 UI history 塞进 prompt」的反模式。
2. **旅行模式 Token 治理：** O2/O4 换 `thread_id` + `travel_tool_memory` 外置摘要，是 **checkpoint 裁剪 + 外部结构化记忆** 的组合，比单纯 Message Trimmer 更可解释。
3. **L4 双存储：** profile（精确、可覆盖）+ 向量（模糊召回 episodic），符合 **semantic vs episodic** 常见分法。
4. **与 RAG 解耦：** 用户画像与领域文档分库，边界清楚。

### 8.2 技术债与优化方向

#### A. 一致性与恢复（架构）


| 问题                               | 根因                         | 建议                                                                                                       |
| -------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------- |
| 刷新 / 换 thread 后 AI「断片」           | L1 不持久；L3 恢复不写回 checkpoint | **RestoreSessionSummarizer**：`apply_snapshot` 后生成固定 `[SESSION_RESUME]` 注入首轮，或持久化 checkpoint（SqliteSaver） |
| history 与 checkpoint 双轨          | 产品层 history 不参与推理          | 文档化即可；若需一致，可选 **history 摘要进 L4 而非 checkpoint**                                                           |
| latest / archives 仅 40 条 history | `MAX_HISTORY_PERSIST`      | archives **不截断**；latest 保持 40 降 IO                                                                       |


#### B. Token 与延迟（性能）


| 问题                   | 建议                                      | 预期          |
| -------------------- | --------------------------------------- | ----------- |
| 每轮全量 `[USER_MEMORY]` | profile 小可保留；向量改 **意图触发**（regex / 小分类器） | 降 prompt 噪声 |
| 归档 pipeline 同步调 LLM  | 改 **异步队列** 或「先写规则项，摘要后台补」               | 归档按钮不阻塞 UI  |
| 旅行频繁换 thread         | 已合理；可度量 **换 thread 前后 token 曲线** 写进测试报告 | 面试有数据       |


#### C. 存储与检索（工程）


| 问题                                            | 建议                                                           |
| --------------------------------------------- | ------------------------------------------------------------ |
| agents 与 rag-server **两套 Chroma + Embedding** | 短期保持分离；中期 **统一 embedding 模型与维度**，或 L4 检索走内部 HTTP 服务          |
| L4 无 TTL / 版本                                 | profile 加 `updated_at` per field；向量 metadata 加 `stale_after` |
| 无 `search_user_memory` tool                   | v2 暴露 MCP，Agent **按需检索** 优于每轮预注入向量                           |


#### D. 通用模式长期记忆弱


| 问题           | 建议                                                    |
| ------------ | ----------------------------------------------------- |
| 无 intake 结构  | 通用 `session_facts: dict[str,str]`，规则 + 显式记住写入 profile |
| pipeline 偏旅行 | `build_candidates` 按 `app_mode` 分支，通用模式抽 topic + 结论句  |


#### E. 安全与质量


| 问题                | 建议                                             |
| ----------------- | ---------------------------------------------- |
| regex 敏感过滤        | 落库前 + 注入前 **双检**                               |
| LLM worthiness 幻觉 | 结构化字段 **规则直通**；LLM 只写摘要                        |
| 向量摘要不可审计          | metadata 强制 `archive_path` / `trigger`，侧边栏只读溯源 |


### 8.3 面试话术模板（30 秒 / 2 分钟）

**30 秒：**  
「我们四层记忆：checkpoint 管当页推理，history 只展示，快照做会话恢复，长期记忆用 profile 加独立 Chroma 存用户 episodic 摘要。RAG 管领域文档，走 MCP 工具，和用户记忆分库。旅行模式还会换 thread_id 控 Token，用 intake 和 tool_memory 衔接上下文。」

**2 分钟展开：**  

- **为什么 history 不进 LLM：** 每轮单条 HumanMessage + checkpoint，避免重复 token 与 UI 状态耦合。  
- **为什么换 thread_id：** POI/generating 阶段 tool 消息膨胀；外置摘要比 trim 更可审计。  
- **为什么 L4 不用 RAG：** 数据源、更新频率、检索意图不同；混库污染查准率。  
- **已知短板：** checkpoint 不持久 → 恢复靠摘要注入；可演进 SqliteSaver 或 session resume block。

---

## 9. 代码与数据路径


| 模块    | 文件                                       | 职责                     |
| ----- | ---------------------------------------- | ---------------------- |
| 会话快照  | `session_store.py`                       | L3                     |
| 长期存储  | `memory_store.py`                        | L4 profile + 本地 Chroma |
| 长期流水线 | `memory_pipeline.py`                     | 写入 L4                  |
| 长期召回  | `memory_recall.py`                       | `[USER_MEMORY]`        |
| 旅行提炼  | `travel_mode.py`、`travel_tool_memory.py` | CONTEXT / thread 切换    |
| 对话    | `ui/chat.py`                             | L2、注入、触发 pipeline      |
| 侧边栏   | `ui/sidebar.py`                          | 归档、记忆面板                |
| Agent | `app.py`                                 | L1 checkpoint          |


**依赖：** `chromadb`；L4 embedding：`text-embedding-v3`（`DASHSCOPE_API_KEY`）。Chroma 不可用时降级为仅 profile。

---

