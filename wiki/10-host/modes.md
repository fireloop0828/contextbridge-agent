---
id: host/modes
title: 多模式 Agent 架构选型
tags: [host, modes, registry]
sources:
  - agents-master/modes/registry.py
  - agents-master/modes/types.py
  - agents-master/modes/travel/
related: [host/mcp-client, host/travel-impl, host/prompts]
updated: 2026-09-10
---

# 多模式 Agent 架构选型

> **TL;DR**：三种模式（通用 / 知识库问答 / 旅行）共用**同一个单 Agent 与同一套 MCP 工具**，通过「模式包 + registry」替换系统提示词与处理逻辑；旅行模式额外叠加强流程状态机。

> agents-master 多垂直模式的架构说明与选型参考。**对外可讲版**：主线讲清「是什么、怎么跑、已落地什么」；细节与对比见附录。

## 目录

- [TL;DR](#tldr)
- [1. Prompt 还是模式包](#1-prompt-还是模式包)
- [2. 单 Agent 还是多 Agent](#2-单-agent-还是多-agent)
- [3. LangGraph 与框架选型](#3-langgraph-与框架选型)
- [4. 多模式架构设计](#4-多模式架构设计)
- [5. 已注册模式](#5-已注册模式)
- [6. 演进方向](#6-演进方向)
- [附录](#附录)
- [相关文档](#相关文档)

---

## TL;DR

**一句话**：单 ReAct Agent + MCP，多个垂直模式通过侧边栏切换；强流程由 Python 模式包编排，Prompt 只管本回合怎么说。

**背景**：侧边栏 **radio** 切模式；通用模式下支持话语自动识别并切入对应模式。

| 问题 | 推荐 |
| --- | --- |
| Prompt 还是模式包？ | **模式包为主**；Prompt 是模式包的一部分 |
| 单 Agent 还是多 Agent？ | **单 Agent + 模式切换**；必要时再升级多 Agent |
| LangGraph 要不要上多节点？ | **继续单 Agent ReAct**；多节点图作为未来选项 |

**术语（Skill 两层，勿混淆）**：

| 名称 | 是什么 | 在哪 |
| --- | --- | --- |
| **应用模式包**（本文亦称 Runtime Skill） | 用户聊天时的真实能力：`Prompt + 路由 + handler +（可选）状态机` | `agents-master/modes/<name>/` |
| **Cursor Skill** | IDE 开发时的 SOP：教 Agent 如何改代码、维护规范 | `~/.cursor/skills/` 或 `.cursor/skills/` 下的 `SKILL.md` |

**多模式最小设计**：`modes/registry`（注册表 + 路由器）+ 各模式包；UI 与意图走同一路由；单 Agent 复用 MCP 缓存，按模式换 Prompt / handler / `thread_id`。

**已落地（2026-06）**：三模式（通用 / 旅行 / 知识库问答）+ registry 路由；旅行重模式包收进 `modes/travel/`，外部仅经 `modes.registry` + `modes.travel.handler` 接入。

**可复用原则**：旅行包已是完整的应用模式包，**不必为可复用而拆**；有第二个重流程或开发协作成本升高时，再补 Cursor Skill 或 `modes/common/`。见 [§6](#6-演进方向)。

---

## 1. Prompt 还是模式包

**本质区别**：

> *Prompt 约束 **模型行为**；模式包约束 **系统行为 + 模型行为**。*
>
> `Prompt ⊂ 模式包`。模式包多出来的是工程层：路由、handler、阶段、预取、交付校验。

| 维度 | 仅 Prompt | 模式包 |
| --- | --- | --- |
| 扩展成本 | 低（加 md） | 中（接口 + 注册） |
| 流程可靠性 | 弱（靠模型自觉） | 强（Python 编排兜底） |
| 适用场景 | 轻量、无状态 | 强流程、多阶段、预取/导出 |

**推荐**：模式包作为多模式主组织方式。轻量模式只需 `mode.py` + Prompt + intent；**旅行等强流程**必须上 handler + 状态机——Python 管 phase、预取、导出，Prompt 管本回合行为。

| 情况 | 选择 |
| --- | --- |
| 只换风格/模板，无状态 | 轻模式包 |
| 有阶段流转、预取、交付校验 | 重模式包 + handler |
| 需工具白名单且 prompt 不够 | 模式包 + 工具策略 |

**当前落点**：

| 模式 | 类型 | 入口 |
| --- | --- | --- |
| 通用 | 轻 | `modes/general/` |
| 知识库问答 | 轻 | `modes/knowledge_qa/` |
| 旅行 | 重 | `modes/travel/`（handler · state_machine · pipeline · prompts） |

**与 Cursor Skill 的关系**：应用模式包 = 运行时能力；Cursor Skill = 开发时可选补充（如 `github-push-workflow`），**不参与**用户侧编排。详见 [附录 A](#附录-a-两种-skill-分层)。

---

## 2. 单 Agent 还是多 Agent

**推荐**：**单 Agent + 模式切换**——模式互斥、MCP 共用、切换时换 Prompt / `thread_id`，避免重复连 MCP。

| 维度 | 单 Agent + 切换 | 多 Agent |
| --- | --- | --- |
| MCP 连接成本 | 低（tools 缓存复用） | 高 |
| 模式互斥体验 | 自然 | 需管理多实例 |
| 并行协作 | 不支持 | 支持 |

多阶段状态机用 **单 Agent + handler** 即可，不需多 Agent 替代。

| 情况 | 方向 |
| --- | --- |
| 互斥模式 + 串行 MCP（现状） | 维持单 Agent |
| 同会话并行多角色 / 同轮多模型对比 | 考虑多 Agent 或多节点图 |
| 工具必须硬隔离 | 按模式过滤 tools，或升级多 Agent |

**当前落点**：`rebuild_agent_only` 切模式/模型不重连 MCP；旅行在 POI→intake 等节点换 `thread_id`。

---

## 3. LangGraph 与框架选型

**推荐**：**维持单 Agent ReAct**（`create_react_agent` + `ToolNode` + `MemorySaver`）。复杂度在模式编排与 MCP，不在图拓扑；模式扩展靠**模式包**，不靠增加 LangGraph 节点数。

| 方案 | 匹配度 | 说明 |
| --- | --- | --- |
| LangGraph 单 Agent ReAct | **高（现状）** | 工具循环、checkpoint、流式 |
| LangGraph 多节点 | 中（未来） | 并行、主管路由 |
| 固定 Chain 流水线 | 低 | 不适配 ReAct + MCP |

旅行 phase 与预取在 **LangGraph 之外**的 Python 编排层（`handler` / `pipeline`）完成。

---

## 4. 多模式架构设计

### 设计目标

- **扩展**：新增模式 = 模式包 + 注册表一行，不扩散 `if app_mode`
- **一致**：UI 切换与意图自动切换走**同一路由器**
- **不退化**：单 Agent、MCP 缓存、旅行 phase/预取/导出保持不变

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

### 主链路

```text
用户输入 → route_by_intent（可选）→ enter_mode
        → [旅行] handler 编排（phase / 预取 / 包装 query）
        → 单 Agent ReAct
        → [旅行] 后处理 / 导出
        → UI 展示
```

### UI 与路由

| 元素 | 来源 |
| --- | --- |
| 模式选项 | `registry.list_mode_labels()`，radio |
| 页面标题 / 副标题 | `mode.branding()` |
| 输入 placeholder | `mode.chat_placeholder()` |
| 模式说明 | `mode.description()`；旅行进行中用 `sidebar_caption()` |

**意图路由**：仅在通用模式下扫描 `detect_intent`；按注册顺序匹配（**旅行优先于知识库问答**）；匹配后 `enter_mode` + 同步 radio + 按需 `rebuild_agent_only`。

**非目标（当前）**：多 Agent、LangGraph 多节点图、按模式硬隔离 MCP Server。

---

## 5. 已注册模式

### 通用（轻）

- **id**：`general` — 开放问答 + 全量 MCP；无 intent，作默认回落。

### 知识库问答（轻）

- **id**：`knowledge_qa` — 专注 RAG 三件套；独立 `system.md`。
- **意义**：验证「加模式 = 新模式包 + 注册」，主链路无需改分支。

### 旅行（重）——强流程样板

旅行是**应用模式包**的参考实现：`Prompt + 路由 + handler + 状态机` 已落地，不是「待 Skill 化」的旧设计。

```text
Python 编排  → phase、intake、预取 facts、导出校验
Prompt       → travel-planner.md 阶段规范
ReAct Agent  → 调 MCP；预取阶段少重复调工具
```

**三条设计亮点**（对外介绍用）：

1. **边界收口**：`ui/chat` 旅行回合只经 `handler`；不散落 `if app_mode`。
2. **编排层预取**：`pipeline` 先拉高德/RAG/天气/路线，Agent 用角标写叙述——省 Token、降编造。
3. **单 Agent 切换**：共用 MCP；关键节点换 `thread_id`，不必多 Agent。

文件职责与目录细节见 [旅行规划-职责分层与步骤依据(实现)](./travel-impl.md)。

**新增强流程模式**：复制 handler +（可选）state_machine + pipeline 骨架；Prompt 管「怎么说」，Agent 管「补调工具」。

---

## 6. 演进方向

### 已完成

- 三模式 + `modes/registry` 路由（UI radio + `route_by_intent`）
- 旅行重模式包 `modes/travel/` 收口，外部经 `handler` 接入

### 可复用演进（有需求再做）

| 层级 | 时机 | 做法 |
| --- | --- | --- |
| L1 Cursor Skill | 改 travel 常踩坑、需统一 prompt 规范 | 增 `.cursor/skills/...`；不改 Python |
| L2 `modes/common/` | 第二个重流程需复用解析/预取 | 抽纯函数，原路径 re-export |
| L3 新垂直模式 | 新产品意图（如 GitHub 推送） | 轻：`mode.py` + md；重：参照旅行样板 |

**封装前三问**：（1）运行时要执行？→ 留 Python；（2）只教 IDE 怎么改？→ Cursor Skill；（3）`ui/chat` 调用链变不变？→ 不变则先 L1 后 L2。

### 后续（可选）

- 按模式过滤 MCP tools（如 QA 仅 RAG）
- `session_store` 精简，多用 `is_travel_mode()`
- 多 Agent / 多节点（见 §2、§3 触发条件）

---

## 附录

### 附录 A：两种 Skill 分层

```text
Cursor Skill（IDE）     →  教 Agent 如何改代码、写 commit
        ↕ 互补
应用模式包（运行时）    →  用户聊天时的真实行为
```

| 层级 | 位置 | 旅行现状 |
| --- | --- | --- |
| Cursor Skill | `~/.cursor/skills/`、`.cursor/skills/` | 可选（如 `travel-mode-dev`） |
| 应用模式包 | `modes/travel/` | **已落地** |

与本仓库 GitHub 推送分工一致：`.cursor/rules/github-workflow.mdc`（项目默认）+ `github-push-workflow` Skill（口令 SOP）。

### 附录 B：为何强流程不用「纯 Prompt / 纯 Cursor Skill」

若把旅行等能力全部交给 Prompt 或 Cursor `SKILL.md`、少写 Python：

| 维度 | 纯 Prompt / Cursor Skill | 当前重模式包（旅行） |
| --- | --- | --- |
| 阶段推进 | 靠模型自觉，易跳步 | `state_machine` 硬约束 |
| MCP 调用 | 模型每轮自调，易超限、费 Token | `pipeline` 预取 + 角标引用 |
| 交付校验 | 难保证导出一致 | Python 校验 |
| thread / 记忆 | 难控 checkpoint | `tool_memory`、换 `thread_id` |

**结论**：强流程本该是 Python 模式包；Cursor Skill 是开发时补充，不能替代 `handler` / `state_machine` / `pipeline`。

---

## 相关文档

- [MCP设计与管理.md](./mcp-client.md)（MCP 流程、注册表、配置与三模式工具关系）
- [GitHub 推送模式目标分析](../50-analysis/github-push-mode.md)（轻工作流 vs 重模式包；Rule + Cursor Skill 分工）
- [旅行规划-职责分层与步骤依据(实现)](./travel-impl.md)（旅行文件职责、目录、实现细节）
- [旅行规划-需求与架构(产品)](./travel-product.md)
- [app.py 架构说明与拆分建议](./architecture.md)

---

## 关联

- 相关：[[host/mcp-client]]
- 相关：[[host/travel-impl]]
- 相关：[[host/prompts]]
