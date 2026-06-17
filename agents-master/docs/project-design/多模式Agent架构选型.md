# 多模式 Agent 架构选型

> agents-master 扩展多垂直模式时的架构决策参考。**偏选型与设计；落地实施见文末「演进方向」。**

## 目录

- [TL;DR](#tldr)
- [1. Prompt 还是模式包（Skill）](#1-prompt-还是模式包skill)
- [2. 单 Agent 还是多 Agent](#2-单-agent-还是多-agent)
- [3. LangGraph 与框架选型](#3-langgraph-与框架选型)
- [4. 多模式架构设计](#4-多模式架构设计)
- [5. 旅行模式：模式包样板](#5-旅行模式模式包样板)
- [6. 演进方向](#6-演进方向)
- [相关文档](#相关文档)

---

## TL;DR

**背景**：单 ReAct Agent + MCP；计划增加多个垂直模式（侧边栏 UI 切换 + 话语自动识别）。


| 问题                 | 推荐                                           |
| ------------------ | -------------------------------------------- |
| Prompt 还是模式包？      | **模式包（Skill/Mode）为主**；Prompt 是模式包的一部分，不是对立方案 |
| 单 Agent 还是多 Agent？ | **单 Agent + 模式切换**；多 Agent 仅在触发条件满足时升级       |
| LangGraph 要不要上多节点？ | **继续单 Agent ReAct**；多节点图作为未来演进选项             |


**多模式最小设计**：注册表 + 路由器 + 各模式包（handler）；UI 与意图走同一路由；单 Agent 复用 MCP 缓存，按模式换 Prompt / handler / `thread_id`。

**当前代码状态**：已落地 `modes/` 注册表与三模式（通用 / 旅行 / 知识库问答）；侧边栏为 **radio**；UI 与意图路由走 `modes.registry`。旅行编排仍由 `travel_mode.py` 等模块承担，尚未物理迁入 `modes/travel/`。

---

## 1. Prompt 还是模式包（Skill）

### 问题定义

多模式扩展时，「换一段 System Prompt」是否足够？还是要把**激活条件、编排逻辑、状态边界**一并工程化封装？

### 评估维度


| 维度      | 仅 Prompt   | 模式包（Skill/Mode）         |
| ------- | ---------- | ----------------------- |
| 扩展成本    | 低（加 md 文件） | 中（需定义模式接口）              |
| 流程可靠性   | 弱（靠模型自觉遵守） | 强（Python 编排兜底）          |
| 状态/工具隔离 | 弱          | 可显式管理 phase、thread、工具策略 |
| 可观测性    | 难追溯「为何这么走」 | 路由与 handler 可记录、可测      |
| 适用场景    | 轻量、无状态     | 强流程、多阶段、预取/校验/导出        |


### 方案对比

**A. 仅 Prompt**：切换 `system.md` / 阶段指令，主链路不变。

- 优点：实现快，适合「写作助手」「面试模拟」等只改语气与输出格式的模式。
- 缺点：工具调用顺序、阶段推进、交付校验难以稳定；逻辑容易散在 `ui/chat.py` 的 `if` 分支里。

**B. 模式包（Skill/Mode）**：`Prompt + 路由 + handler +（可选）工具策略`。

- 优点：强流程模式（如旅行）可把状态机、预取、导出校验内聚；新增模式不改主链路。
- 缺点：需要抽象模式接口与注册表，前期有一定工程投入。

**关系**：`Prompt ⊂ 模式包`。模式包不是另一种智能，是**工程层的可插拔单元**；激活后 Prompt 仍进入 LLM context。

### 推荐与理由

- **推荐 B（模式包）作为多模式的主组织方式**；轻量模式可只实现「Prompt 部分」，不必上完整状态机。
- **旅行等强流程模式必须用模式包**，不能仅靠 Prompt——当前代码已用 Python 管 phase、预取 facts、校验导出，Prompt 只负责「本回合行为建议」。

### 触发条件


| 情况                         | 选择          |
| -------------------------- | ----------- |
| 只换回答风格/输出模板，无状态、无工具约束      | 仅 Prompt 即可 |
| 有阶段流转、预取、交付物校验、thread 重置   | 必须模式包       |
| 某模式需禁用/白名单工具，且 prompt 约束不够 | 模式包 + 工具策略  |


### 当前落点

- 通用模式 ≈ 轻模式包（主要是 `general_system.md`）。
- 旅行模式 ≈ 重模式包（`travel_mode.py` 状态机 + `travel_pipeline.py` 预取 + `prompts/travel-planner.md`）。
- 缺口：尚未有统一 `modes/registry`，模式能力散落在 `app.py` / `ui/`* / `prompts/*`。

---

## 2. 单 Agent 还是多 Agent

### 问题定义

每个垂直模式是独立 Agent 实例，还是共用一个 Agent、切换 Prompt/handler？

### 评估维度


| 维度       | 单 Agent + 切换        | 多 Agent      |
| -------- | ------------------- | ------------ |
| MCP 连接成本 | 低（tools 缓存复用）       | 高（多份连接或复杂路由） |
| 模式互斥体验   | 自然（换 prompt/thread） | 需额外管理实例生命周期  |
| 并行协作     | 不支持                 | 支持           |
| 工具/权限隔离  | 靠过滤或 prompt         | 可硬隔离         |
| 工程复杂度    | 低～中                 | 中～高          |


### 方案对比

**A. 单 Agent + 模式切换**：一个 `create_react_agent`，切模式时 `rebuild_agent_only`（换 system prompt），必要时换 `thread_id`。

- 优点：与现状一致；MCP `get_tools()` 只跑一次；Streamlit 会话简单。
- 缺点：同轮无法并行多角色；工具隔离靠策略层而非进程级隔离。

**B. 多 Agent**：每模式一个 Agent，或 LangGraph 多节点多角色。

- 优点：角色严格分离、可并行子任务、可同轮多模型。
- 缺点：连接与状态管理成本高；对「互斥模式 + 串行 MCP」属于过度设计。

**说明**：多阶段状态机（旅行 intake→生成→改稿）用**单 Agent + handler** 即可，**不需要**多 Agent 来「替代状态机」。

### 推荐与理由

- **推荐 A**：模式互斥、工具大多共用、切换时可清/换 checkpoint——完全符合当前产品形态。
- 模式增至 5～10 个时，仍用**单 Agent + 模式注册表**，避免 N 份 Agent 重复连 MCP。

### 触发条件


| 情况                             | 升级方向                    |
| ------------------------------ | ----------------------- |
| 同会话并行多角色（检索员 + 写作员同时跑）         | 多 Agent 或 LangGraph 多节点 |
| 同轮需对比多个模型输出                    | 多 Agent                 |
| 某模式工具必须硬隔离（安全/权限）且 prompt 过滤不够 | 多 Agent 或按模式过滤 tools    |
| 仅模式互斥、串行工具链                    | 维持单 Agent               |


### 当前落点

- `_build_agent_from_tools` + `rebuild_agent_only`：切模式/模型只重建 Agent，不重连 MCP。
- 旅行 `should_reset_agent_thread_o9`：POI 结束进 intake/generating 时换 `thread_id`，清空 Agent checkpoint，UI 历史保留。

---

## 3. LangGraph 与框架选型

### 问题定义

LangGraph 是否「大材小用」？何时需要多节点图？其它框架是否更合适？

### 评估维度


| 框架                           | 强项                 | 与本项目匹配度             |
| ---------------------------- | ------------------ | ------------------- |
| **LangGraph（单 Agent ReAct）** | 工具循环、checkpoint、流式 | **高**——现状即此         |
| **LangGraph（多节点）**           | 并行、主管路由、可恢复复杂图     | 中——未来可选             |
| **LangChain Chain**          | 固定流水线              | 低——需 Agent 自主调 MCP  |
| **CrewAI / AutoGen**         | 多角色协作 demo         | 低——偏演示，非 MCP 宿主     |
| **Dify / Coze**              | 低代码                | 低——难深度集成自研状态机 + MCP |


### 方案对比

**A. 维持 LangGraph 单 Agent ReAct**（`create_react_agent` + `MemorySaver` + `astream_graph`）。

- 覆盖：多轮工具调用、流式输出、thread checkpoint。
- 「只跑单 Agent」并非浪费——这正是 ReAct + checkpoint 的正当用法。

**B. LangGraph 多节点 / 多 Agent**。

- 收益：子任务并行、角色分离、可视化流程、复杂状态可恢复。
- 成本：图设计、调试、与 Streamlit 集成复杂度上升。

**C. 换框架**。

- 本项目约束：MCP 宿主、自研旅行状态机、Streamlit UI——换框架收益不明显。

### 推荐与理由

- **推荐 A**：当前复杂度在「模式编排 + MCP 工具链」，不在「图拓扑」；单节点 ReAct 已满足。
- **不推荐**为「将来可能多模式」提前上多节点——模式扩展靠模式包，不靠 LangGraph 节点数。

### 触发条件


| 情况                             | 考虑升级          |
| ------------------------------ | ------------- |
| 主管 Agent 路由到多个专职子 Agent        | LangGraph 多节点 |
| 同轮并行调用多路 MCP / 多模型             | 多节点或并行子图      |
| 流程需可视化回放、断点恢复且超出 checkpoint 能力 | 多节点 + 显式状态    |
| 互斥模式 + 串行 MCP（现状）              | 维持单 Agent     |


### 当前落点

- `app.py`：`create_react_agent` + `ToolNode` + `MemorySaver` + `RunnableConfig(thread_id=...)`。
- 旅行 phase 与工具预取在 **LangGraph 之外**的 Python 编排层完成，不依赖图节点。

---

## 4. 多模式架构设计

### 设计目标

- **扩展**：确保**新增模式的改动面最小**，主要改模式包自身，不扩散（不需要到处加） `if app_mode`。
- **一致**：确保**模式行为一致，**UI 切换与意图自动切换走**同一路由器**，避免「界面是 A、Prompt 是 B」。
- **能力不退化**：单 Agent、MCP 缓存、旅行 phase/thread/预取/导出逻辑保持不变。

### 最小抽象（设计层）

```text
注册表（Registry）  → 列出模式、按 id 获取模式包
路由器（Router）    → UI 优先；通用模式下可按 intent 自动切换
模式包（Mode）      → identity + prompt + handler +（可选）intent 规则 +（可选）工具策略
```

**UI 影响（设计约定，非施工清单）**：

- 侧边栏模式选项来自注册表，不再写死「通用 / 旅行」。
- 页面标题、输入 placeholder、模式说明由各模式包提供元信息。
- 新增模式 = 注册一次 → UI 自动多一个选项；旅行专属 UI（证据横幅、进度）仍由旅行 handler 声明是否需要。

**主链路（固定，模式无关）**：

```text
用户输入 → Router 确定模式 → Mode.handler 编排本回合 → 单 Agent ReAct → Mode.handler 后处理 → UI 展示
```

### 非目标（当前阶段）

- 多 Agent 协作、LangGraph 多节点图。
- 按模式硬隔离 MCP Server（除非触发条件出现）。

---

## 5. 旅行模式：模式包样板

旅行模式说明：**不是纯 Prompt**，而是模式包的典型形态。

```text
Python 编排  → phase、intake、[TRAVEL_CONTEXT]、预取 facts、导出校验
Prompt       → System Prompt + 阶段 checklist（工具顺序建议）
ReAct Agent  → LLM 读 Prompt 后自主调 MCP（RAG / 高德 / 导出）
```


| 控制项                          | 层                    |
| ---------------------------- | -------------------- |
| 阶段流转（POI → intake → 生成 → 改稿） | `travel_mode.py`     |
| MCP 预取（RAG/高德）               | `travel_pipeline.py` |
| 本回合行为、工具建议                   | Prompt               |
| 实际工具调用                       | ReAct Agent          |


对未来其它强流程模式的启发：状态机与预取放 handler，Prompt 管「怎么说」，Agent 管「调工具」。

---

## 6. 演进方向

**目标**：把现有「半模式包」标准化，验证「加第 2 个轻量模式不改主链路」。

```text
modes/
├── registry.py       # 注册、路由（UI 优先 → intent 匹配）
├── general/          # 轻模式包（ mainly prompt）
└── travel/           # 重模式包（handler + prompt + 状态）
```

**阶段**（设计路径，非排期承诺）：

1. 引入注册表 + 路由器；`general` / `travel` 迁入，**行为不变**。
2. 新增一个极简第 2 模式（如纯 Prompt 的写作模式），验收插件化扩展。
3. 若出现工具隔离 / 并行协作等触发条件，再评估多 Agent 或多节点图。

---

## 相关文档

- [app.py 架构说明与拆分建议](./app.py架构说明与拆分建议.md)
- [旅行规划-职责分层与步骤依据(实现)](./旅行规划-职责分层与步骤依据(实现).md)
- [旅行规划-需求与架构(产品)](./旅行规划-需求与架构(产品).md)

