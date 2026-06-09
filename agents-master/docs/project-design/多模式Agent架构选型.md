# 多模式 Agent 架构选型

> agents-master 扩展多垂直模式时的架构决策参考。**设计分析，未实施。**

## 目录

- [1. 待决问题与结论](#1-待决问题与结论)
- [2. Prompt 与 Skill](#2-prompt-与-skill)
- [3. 旅行模式现状](#3-旅行模式现状)
- [4. 单 Agent vs 多 Agent](#4-单-agent-vs-多-agent)
- [5. LangGraph 与框架选型](#5-langgraph-与框架选型)
- [6. 演进方向](#6-演进方向)
- [相关文档](#相关文档)

---

## 1. 待决问题与结论

**背景**：单 ReAct Agent + MCP；计划增加多个垂直模式（UI 切换 + 话语自动识别）。

| 问题 | 结论 |
|------|------|
| Prompt 还是 Skill 组织模式？ | **Skill（模式包）**：Prompt 是内容，Skill 是 Prompt + 激活 + 编排的可插拔单元 |
| 单 Agent 还是多 Agent？ | **单 Agent + Skill 切换**；多 Agent 仅用于并行协作、同轮多模型、强工具隔离 |
| LangGraph 只跑单 Agent 可惜吗？ | **否**；ReAct + checkpoint + 流式已是正当用法 |

**推荐路径**：单 Agent + `modes/` 注册表 + 各模式 handler，保留 MCP 连接缓存与按 phase 换 `thread_id`。

---

## 2. Prompt 与 Skill

| | Prompt | Skill（本项目：模式包） |
|---|--------|----------------------|
| **是什么** | 发给 LLM 的文字 | Prompt + 激活条件 + 编排逻辑 +（可选）工具策略 |
| **解决什么** | 本轮怎么想、怎么做 | 多模式如何注册、路由、按需加载 |
| **关系** | Skill 激活后变为 Prompt 进 context | `Prompt ⊂ Skill` |

两者都能教工作流；Skill 不是另一种智能，是 **工程层的模式打包**。旅行模式已是半 Skill（`prompts/*` + `travel_mode.py` + `detect_travel_intent`），尚未标准化目录。

**Prompt 实现 vs Skill 实现**：底层同为 ReAct + MCP；差别仅在组织——现状是 `if app_mode` 散落各处，演进为 `modes/<name>/` + `registry.py`  plug-in。

---

## 3. 旅行模式现状

**不是全靠 Prompt**，三层分工：

```text
Python 编排 → 算 phase、包装 [TRAVEL_CONTEXT]、解析 intake、校验导出
Prompt      → System Prompt + 每轮阶段指令与工具 checklist
ReAct Agent → LLM 读 Prompt 后自主调 MCP（RAG / 高德 / 导出）
```

| 控制项 | 层 |
|--------|-----|
| 阶段流转（intake→生成→改稿） | Python `travel_mode.py` |
| 本回合行为、工具顺序建议 | Prompt |
| 实际 MCP 调用 | LLM ReAct |

---

## 4. 单 Agent vs 多 Agent

| 条件 | 选型 |
|------|------|
| 模式互斥、工具大多共用、切换清历史 | **单 Agent + Skill**，换 Prompt / handler / `thread_id` |
| 多阶段状态机 | **单 Agent + handler**（多 Agent 不替代状态机） |
| 模式 5～10 个 | **Skill Registry**，避免多份 Agent + 重复连 MCP |
| 工具差异大 | 单 Agent **按模式过滤 tools**；仍不够再考虑多 Agent |
| 同会话并行多模式 / 同 thread 内换模型 | **多 Agent** 或 LangGraph 多节点 |

---

## 5. LangGraph 与框架选型

| 框架 | 适合 |
|------|------|
| **LangGraph** | 有状态 Agent、ReAct、工具循环；单 Agent 亦合理 |
| **LangChain Chain** | 固定步骤流水线，不需 Agent 自主决策 |
| **CrewAI / AutoGen** | 多角色协作 demo |
| **Dify / Coze** | 低代码；不适合深度 MCP + 自研状态机 |

**何时在 LangGraph 里加多节点/多 Agent**：子任务并行、角色严格分离、同轮多模型、主管路由——当前互斥模式 + 串行 MCP **不需要**。

---

## 6. 演进方向

```text
modes/
├── registry.py          # 注册、路由（UI 优先 → intent 匹配）
└── travel/
    ├── manifest.yaml    # id、意图规则、UI 标签
    ├── system.md        # 模式 Prompt
    └── handler.py       # 原 travel_mode.py
```

步骤：① 旅行迁入 `modes/travel/` → ② 实现 Registry/Router → ③ 加第二个简单模式验证 plug-in。

---

## 相关文档

- [app.py 架构说明与拆分建议](./app.py架构说明与拆分建议.md)
- [旅行规划-职责分层与步骤依据(实现)](./旅行规划-职责分层与步骤依据(实现).md)
