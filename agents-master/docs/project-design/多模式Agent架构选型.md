# 多模式 Agent 架构选型

> agents-master 扩展多垂直模式时的架构决策参考。**偏选型与设计**；文末「落地现状」记录已与代码对齐的实现快照。

## 目录

- [TL;DR](#tldr)
- [1. Prompt 还是模式包（Skill）](#1-prompt-还是模式包skill)
- [2. 单 Agent 还是多 Agent](#2-单-agent-还是多-agent)
- [3. LangGraph 与框架选型](#3-langgraph-与框架选型)
- [4. 多模式架构设计](#4-多模式架构设计)
- [5. 已注册模式](#5-已注册模式)
- [6. 演进方向](#6-演进方向)
- [相关文档](#相关文档)

---

## TL;DR

**背景**：单 ReAct Agent + MCP；多个垂直模式通过侧边栏 **radio** 切换，通用模式下支持话语自动识别切模式。


| 问题                 | 推荐                                     |
| ------------------ | -------------------------------------- |
| Prompt 还是模式包？      | **模式包（Skill/Mode）为主**；Prompt 是模式包的一部分  |
| 单 Agent 还是多 Agent？ | **单 Agent + 模式切换**；多 Agent 仅在触发条件满足时升级 |
| LangGraph 要不要上多节点？ | **继续单 Agent ReAct**；多节点图作为未来演进选项       |


**多模式最小设计**：`modes/registry`（注册表 + 路由器）+ 各模式包；UI 与意图走同一路由；单 Agent 复用 MCP 缓存，按模式换 Prompt / handler / `thread_id`。

**落地快照（2026-06）**：旅行模式包收口完成——`modes/travel/` 含全部实现；根目录无 `travel_*.py`；外部经 `modes.registry` + `modes.travel.handler` 接入。

---

## 1. Prompt 还是模式包（Skill）

**本质区别一句话**：

> *Prompt 约束的是 **模型行为**；Skill/模式包约束的是 **系统行为 + 模型行为**。*
>
> `Prompt ⊂ Skill`。Skill 激活后，Prompt 照样进 context；Skill 多出来的是 **工程层**。

### 问题定义

多模式扩展时，「换一段 System Prompt」是否足够？还是要把**激活条件、编排逻辑、状态边界**一并工程化封装？

### 评估维度


| 维度      | 仅 Prompt   | 模式包（Skill/Mode）         |
| ------- | ---------- | ----------------------- |
| 扩展成本    | 低（加 md 文件） | 中（需定义模式接口 + 注册）         |
| 流程可靠性   | 弱（靠模型自觉遵守） | 强（Python 编排兜底）          |
| 状态/工具隔离 | 弱          | 可显式管理 phase、thread、工具策略 |
| 可观测性    | 难追溯「为何这么走」 | 路由与 handler 可记录、可测      |
| 适用场景    | 轻量、无状态     | 强流程、多阶段、预取/校验/导出        |


### 方案对比

**A. 仅 Prompt**：切换 `system.md`，主链路不变。

- 优点：实现快，适合只改语气与输出格式。
- 缺点：阶段推进、工具约束、交付校验难稳定；逻辑易散在 UI 分支。

**B. 模式包（Skill/Mode）**：`Prompt + 路由 + handler +（可选）工具策略`。

- 优点：强流程可内聚；新增模式主要改模式包自身。
- 缺点：需注册表与模式接口，前期有工程投入。

**关系**：`Prompt ⊂ 模式包`。模式包是工程层可插拔单元，不是另一种智能。

### 推荐与理由

- **推荐 B 作为多模式主组织方式**；轻量模式可只实现 Prompt + 元信息 + intent，不必上状态机。
- **旅行等强流程必须用模式包**——Python 管 phase、预取、导出；Prompt 只管本回合行为建议。

### 触发条件


| 情况                      | 选择              |
| ----------------------- | --------------- |
| 只换风格/模板，无状态、无工具约束       | 轻模式包（实质≈Prompt） |
| 有阶段流转、预取、交付校验、thread 重置 | 重模式包 + handler  |
| 需禁用/白名单工具且 prompt 不够    | 模式包 + 工具策略      |


### 当前落点


| 模式    | 类型   | 主要文件                                                                |
| ----- | ---- | ------------------------------------------------------------------- |
| 通用    | 轻模式包 | `modes/general/mode.py` → `prompts/general_system.md`               |
| 知识库问答 | 轻模式包 | `modes/knowledge_qa/mode.py` + `system.md`                          |
| 旅行    | 重模式包 | `modes/travel/`（state_machine、pipeline、handler、prompts） |


---

## 2. 单 Agent 还是多 Agent

### 问题定义

每个垂直模式是独立 Agent 实例，还是共用一个 Agent、切换 Prompt/handler？

### 评估维度


| 维度       | 单 Agent + 切换        | 多 Agent |
| -------- | ------------------- | ------- |
| MCP 连接成本 | 低（tools 缓存复用）       | 高       |
| 模式互斥体验   | 自然（换 prompt/thread） | 需管理多实例  |
| 并行协作     | 不支持                 | 支持      |
| 工具/权限隔离  | 靠过滤或 prompt         | 可硬隔离    |


### 方案对比

**A. 单 Agent + 模式切换**：`create_react_agent`，切模式时 `rebuild_agent_only`，必要时换 `thread_id`。

**B. 多 Agent**：每模式一实例，或 LangGraph 多角色节点。

多阶段状态机用 **单 Agent + handler** 即可，不需多 Agent 替代状态机。

### 推荐与理由

- **推荐 A**：模式互斥、工具共用、切换可换 checkpoint——与现状一致。
- 模式增至多个时仍用**单 Agent + 注册表**，避免重复连 MCP。

### 触发条件


| 情况                | 升级方向                    |
| ----------------- | ----------------------- |
| 同会话并行多角色          | 多 Agent 或 LangGraph 多节点 |
| 同轮多模型对比           | 多 Agent                 |
| 工具必须硬隔离           | 多 Agent 或按模式过滤 tools    |
| 互斥模式 + 串行 MCP（现状） | 维持单 Agent               |


### 当前落点

- `rebuild_agent_only`：切模式/模型只重建 Agent，不重连 MCP。
- 旅行 `should_reset_agent_thread_o9`：POI 结束进 intake/generating 时换 `thread_id`。

---

## 3. LangGraph 与框架选型

### 问题定义

LangGraph 是否「大材小用」？何时需要多节点图？

### 评估维度


| 框架                      | 强项                 | 匹配度                |
| ----------------------- | ------------------ | ------------------ |
| LangGraph 单 Agent ReAct | 工具循环、checkpoint、流式 | **高（现状）**          |
| LangGraph 多节点           | 并行、主管路由            | 中（未来）              |
| LangChain Chain         | 固定流水线              | 低                  |
| CrewAI / Dify 等         | 协作 demo / 低代码      | 低（难深度 MCP + 自研状态机） |


### 推荐与理由

- **推荐维持单 Agent ReAct**；复杂度在模式编排与 MCP，不在图拓扑。
- 模式扩展靠**模式包**，不靠增加 LangGraph 节点数。

### 触发条件


| 情况                | 考虑升级      |
| ----------------- | --------- |
| 主管路由多专职子 Agent    | 多节点       |
| 同轮并行多路 MCP / 多模型  | 多节点或子图    |
| 互斥模式 + 串行 MCP（现状） | 维持单 Agent |


### 当前落点

- `app.py`：`create_react_agent` + `ToolNode` + `MemorySaver`。
- 旅行 phase 与预取在 **LangGraph 之外**的 Python 编排层完成。

---

## 4. 多模式架构设计

### 设计目标

- **扩展**：新增模式主要改模式包 + 注册表一行，不扩散 `if app_mode`。
- **一致**：UI 切换与意图自动切换走**同一路由器**。
- **不退化**：单 Agent、MCP 缓存、旅行 phase/thread/预取/导出保持不变。

### 最小抽象

```text
注册表（modes/registry.py）
  list_modes / get_mode / build_system_prompt / branding
  route_by_intent   ← 仅 general 模式下扫描其他模式
  enter_mode        ← 切换并返回是否需 rebuild Agent

模式包（modes/<name>/mode.py）
  id, label, order, description
  branding / chat_placeholder / build_system_prompt
  detect_intent / on_enter / on_exit
```

**主链路（固定）**：

```text
用户输入 → route_by_intent（可选）→ enter_mode
        → [旅行] handler 编排（phase / 预取 / 包装 query）
        → 单 Agent ReAct
        → [旅行] 后处理 / 导出
        → UI 展示
```

### UI 设计约定


| 元素             | 来源                                                |
| -------------- | ------------------------------------------------- |
| 模式选项           | `registry.list_mode_labels()`，**radio** 展示        |
| 页面标题 / 副标题     | `mode.branding()`                                 |
| 输入 placeholder | `mode.chat_placeholder()`                         |
| 模式说明           | `mode.description()`；旅行进行中用动态 `sidebar_caption()` |
| 旅行专属 UI        | 证据横幅、进度面板——仍绑定 `is_travel_mode()`                 |


**意图路由规则**：

- 仅在 **通用模式** 下扫描 `detect_intent`。
- 按注册顺序匹配：**旅行优先于知识库问答**（避免「去杭州查攻略」误进 QA）。
- 匹配后 `enter_mode` + 同步 radio + `rebuild_agent_only`（若 Prompt 变化）。

### 非目标（当前阶段）

- 多 Agent、LangGraph 多节点图。
- 按模式硬隔离 MCP Server。

---

## 5. 已注册模式

### 通用模式（轻）

- **id**：`general`
- **能力**：开放问答 + 全量 MCP 工具（RAG、时间、导出等）。
- **intent**：无（作为默认回落模式）。

### 知识库问答（轻）——插件化验收模式

- **id**：`knowledge_qa`
- **能力**：专注 RAG 三件套（`list_collections` / `query_knowledge_hub` / `get_document_summary`）；独立 `system.md`。
- **intent 示例**：知识库、检索、collection、RAG、文档、资料…
- **设计意义**：验证「加第 2 个模式 = 新模式包 + 注册表注册」，主链路无需改分支。

### 旅行规划（重）——模式包样板

```text
Python 编排  → phase、intake、[TRAVEL_CONTEXT]、预取 facts、导出校验
Prompt       → System Prompt + 阶段 checklist
ReAct Agent  → LLM 自主调 MCP（RAG / 高德 / 导出）
```


| 控制项    | 层                                    |
| ------ | ------------------------------------ |
| 阶段流转   | `modes/travel/state_machine.py` |
| MCP 预取 | `modes/travel/pipeline.py` |
| 回合编排入口 | `modes/travel/handler.py` ← `ui/chat` |
| 本回合行为  | Prompt                               |
| 工具调用   | ReAct Agent                          |


对未来强流程模式的启发：状态机与预取放 handler，Prompt 管「怎么说」，Agent 管「调工具」。

---

## 6. 演进方向

### 已完成（多模式 + 旅行模式包收口）

1. `modes/registry` + 三模式（通用 / 旅行 / 知识库问答）。
2. UI radio + `route_by_intent` 意图路由。
3. 旅行模式包 `modes/travel/`：`state_machine` · `pipeline` · `facts` · `tool_memory` · `handler` · `prompts`。
4. `ui/chat` 旅行回合只经 `handler`；根目录已删除全部 `travel_*.py`。

### 后续（可选，非阻塞）

| 项 | 说明 |
| --- | --- |
| 工具策略 | 按模式过滤 MCP tools（如 QA 仅 RAG） |
| `session_store` 精简 | 更多用 `is_travel_mode()`，少直接读 travel session 键 |
| 多 Agent / 多节点 | 见 §2、§3 触发条件 |


### 目录目标形态

```text
modes/travel/
├── mode.py              # 注册表元信息
├── handler.py           # ui/chat 唯一编排入口
├── state_machine.py     # phase / intake / context
├── pipeline.py          # MCP 预取
├── facts.py             # travel_facts
├── tool_memory.py       # 工具轮次记忆
├── prompts.py + *.md
```

---

## 相关文档

- [app.py 架构说明与拆分建议](./app.py架构说明与拆分建议.md)
- [旅行规划-职责分层与步骤依据(实现)](./旅行规划-职责分层与步骤依据(实现).md)
- [旅行规划-需求与架构(产品)](./旅行规划-需求与架构(产品).md)

