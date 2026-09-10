---
id: host/middleware
title: 中间件化改造方案
tags: [host, middleware, architecture]
sources:
  - agents-master/ui/chat.py
  - agents-master/middlewares/
related: [host/architecture, host/memory, host/modes]
updated: 2026-09-10
---

# 中间件（Middleware）化改造方案

> **TL;DR**：用 `TurnContext`（贯穿一轮请求）+ `TurnMiddleware`（4 个钩子）+ `TurnOrchestrator`（驱动链），把记忆注入、模式路由、后处理等横切逻辑从 `ui/chat.py` 抽成可插拔中间件链，让一轮请求的流程可读、可插拔。

> 将 `ui/chat.py` 回合编排中散落的横切能力（记忆注入/抽取、错误处理、计时、导出、会话落盘等）收敛为**有序中间件链**的方案说明。
> **2026-08 更新**：V0（`middlewares/` 骨架 + `TurnContext` + `TurnOrchestrator`，空链可运行）已落地，**未注入现有流程**。V1 起的迁移以本文档为实施依据。

---

## TL;DR

**一句话**：一轮请求 = 一条有序中间件链；横切能力各自封装为 `TurnMiddleware`，挂在 `before_agent / after_agent / on_error / on_agent_built` 四个钩子上，由 `TurnOrchestrator` 驱动，**主战场是编排层，不改 LangGraph**。

| 问题 | 推荐 |
| --- | --- |
| 横切逻辑散在 `ui/chat.py` 的显式调用 | 收敛为有序中间件链，可排序、可启停、可测试 |
| 新增能力要改 `render_chat` | 注册一个中间件即可 |
| 错误处理三套并存 | 统一走 `on_error` 链 |
| 时序靠代码顺序隐式表达 | `order` 显式声明 + `TurnContext` 承载状态 |

---

## 1. 现状痛点

`render_chat()`（`ui/chat.py`，约 250 行）是一轮请求的「上帝函数」，横跨 7 类横切能力，全部是散落的显式调用 + 裸 `try/except`：

```python
# ui/chat.py（现状示例）
agent_query = wrap_query_with_user_memory(agent_query, search_query=user_query)  # 记忆注入

resp, final_text, final_tool = ... process_query(agent_query, ...)               # Agent 调用

if export_paths and travel_after and travel_after.plan_ready:
    try:
        run_memory_pipeline_from_current(trigger="travel_export")                # 记忆流水线
    except Exception:
        pass
try:
    run_explicit_remember_from_user_text(user_query)
except Exception:
    pass
```

| # | 痛点 | 表现 |
|---|------|------|
| 1 | 职责混杂 | 同一函数同时干：意图路由、旅行编排、记忆注入/抽取、导出、归档、计时、错误处理 |
| 2 | 横切逻辑不可插拔 | 记忆注入写在函数中间，想关掉要改源码 |
| 3 | 错误处理三套并存 | `format_agent_error`（Agent）/ `_mcp_tool_error_message`（工具）/ `st.error`（UI）各管一摊 |
| 4 | 新增能力成本高 | 加审计日志/限流/脱敏都要再改 `render_chat` |
| 5 | 时序不可见 | 记忆、计时、归档顺序靠代码顺序隐式表达，无法排序、跳过、单测 |

---

## 2. 设计目标与原则

1. **一轮请求 = 一条中间件链**：横切能力以 `TurnMiddleware` 挂在 4 个生命周期钩子上，可排序、可启停、可测试。
2. **旅行编排降级为「一个模式级中间件」**：与其他中间件平级，不再特判。
3. **零侵入 LangGraph**：当前用 `create_react_agent`（内置图），业务横切点大多在图外（路由、导出、UI），**主战场是编排层**，不是 LangGraph middleware。
4. **错误、计时、记忆统一收敛**：错误归一化走 `on_error` 链；时序统一由 `TurnContext` 承载。
5. **迁移守则（沿用项目拆分原则）**：行为不变优先；每步迁移后能 `streamlit run app.py` 回归通用/旅行全流程；一个中间件「先包一层再拆层」，避免一步重写。

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────┐
│  ui/chat.py  →  精简为：ctx = orchestrator.run(query) │
└──────────────────────┬───────────────────────────────┘
                       ▼
        ┌──────────────────────────────┐
        │   TurnOrchestrator（编排器）   │
        │  ┌──────────────────────────┐ │
        │  │   Middleware Chain（有序） │ │
        │  │  1. TimingMiddleware     │ │
        │  │  2. ModeRoutingMiddleware│ │   ── modes/registry
        │  │  3. TravelMiddleware     │ │   ── modes/travel/handler
        │  │  4. MemoryRecallMid.     │ │   ── memory_recall
        │  │  5. AgentInvokeMid.      │ │   ── app.process_query
        │  │  6. ExportMiddleware     │ │   ── extract/auto_export
        │  │  7. MemoryPipelineMid.   │ │   ── memory_pipeline
        │  │  8. SessionPersistMid.   │ │   ── history/autosave
        │  │  9. ErrorMiddleware      │ │   ── format_agent_error
        │  └──────────────────────────┘ │
        └──────────────────────────────┘
                       ▼
        LangGraph create_react_agent（不改）
```

---

## 4. 核心抽象

### 4.1 `TurnContext` —— 贯穿一轮请求的上下文

```python
@dataclass
class TurnContext:
    user_query: str                    # 原始用户输入
    agent_query: str                   # 注入后传给 Agent 的 query
    resp: dict | None                  # Agent 调用返回
    final_text: str
    final_tool: str
    error: str | None
    error_detail: str | None
    mode_id: str
    phase_this_turn: str | None
    export_paths: list[str]
    aborted: bool                      # before 链可设置，跳过 invoke 与 after
    extra: dict                        # 中间件间附加数据
```

> 骨架中 `travel_turn / travel_after / timing` 等暂不内建，V1 按需以字段或 `extra` 扩展。

### 4.2 `TurnMiddleware` 协议 —— 4 个钩子（全部默认空实现）

```python
class TurnMiddleware(ABC):
    name: str                          # 唯一名，用于排序/启停
    order: int                         # 链执行顺序（升序）

    def before_agent(self, ctx: TurnContext) -> None:
        # 请求前：改写 agent_query、切换 thread、预取等

    def after_agent(self, ctx: TurnContext) -> None:
        # 请求后：记忆抽取、导出、落盘、历史记录等

    def on_error(self, ctx: TurnContext, exc: Exception) -> None:
        # 异常时：错误归一化、降级、告警

    def on_agent_built(self, build_ctx: Any) -> None:
        # （预留）Agent 构建/重建钩子
```

### 4.3 `TurnOrchestrator` —— 管理链并驱动一轮请求

```python
class TurnOrchestrator:
    def __init__(self, chain=None, invoke=None): ...   # invoke 可注入，默认占位实现

    def register(self, mw) -> "TurnOrchestrator": ...
    def unregister(self, name) -> bool: ...             # 按名启停
    def reorder(self, names) -> None: ...               # 显式排序（校验一致）

    def run(self, user_query, **kwargs) -> TurnContext: # 同步入口
        # before 正序 → invoke → on_error（逆序）→ after（逆序）
    async def arun(self, user_query, **kwargs) -> TurnContext:  # 异步入口（预留）
```

**关键语义：洋葱模型**。`before_agent` 正序执行，`after_agent` / `on_error` **逆序**执行（与 Web 框架中间件一致：先注入的 Memory 最后归档）。任一 `before_agent` 可设 `ctx.aborted = True` 跳过 invoke 与后续 before。

---

## 5. 中间件清单

### 5.1 现有能力 → 中间件映射（V1 迁移目标）

| 中间件 | 钩子 | 迁移来源（现代码） | 职责 |
|---|---|---|---|
| `TimingMiddleware` | before/after/on_error | `ui/chat.py` 119-131、242-249、`timing_log.py` | 一轮计时生命周期，`finish(status=...)` 统一收口 |
| `ModeRoutingMiddleware` | before | `modes/registry.route_by_intent` + `enter_mode` | 意图路由、模式切换、重建 Agent |
| `TravelMiddleware` | before/after | `modes/travel/handler.py` | phase 推进、`[TRAVEL_CONTEXT]`、预取、tool_memory、交付校验 |
| `MemoryRecallMiddleware` | before | `memory_recall.wrap_query_with_user_memory` | 拼 `[USER_MEMORY]` 注入块（可配置开关/搜索词） |
| `AgentInvokeMiddleware` | invoke | `app.py process_query` | 流式回调、`astream_graph`、超时包裹、thread_id |
| `ExportMiddleware` | after | `app.py extract_export_paths / auto_export_travel_plan_from_chat` | 导出文件解析、注册、下载渲染 |
| `MemoryPipelineMiddleware` | after | `ui/chat.py` 202-214 + `session_store.py` 归档钩子 | explicit remember + travel_export + 归档流水线 |
| `SessionPersistenceMiddleware` | after | `ui/chat.py` 224-241 + `save_latest_autosave` | history 写入、autosave |
| `ErrorMiddleware` | on_error | `app.py format_agent_error` + `_mcp_tool_error_message` | 异常 → 用户可读消息 + 技术详情 |

### 5.2 建议顺带新增（低成本、高收益）

| 中间件 | 钩子 | 说明 |
|---|---|---|
| `SensitiveFilterMiddleware` | before/after | 入站/出站脱敏（API Key、手机号），复用 `memory_pipeline.rule_worthiness` 的敏感正则 |
| `AuditLogMiddleware` | after/on_error | 每轮记录 query/模型/耗时/错误码到 JSONL |
| `RetryMiddleware` | invoke | 对 429/限流做 1 次指数退避重试 |
| `MCPGuardMiddleware` | before | MCP 未就绪统一提示，替代 `render_chat` 245-252 分支 |

---

## 6. 一轮请求时序（改造后）

```
render_chat()
  └─ TurnOrchestrator.run(user_query)
        │  before 链（正序）
        ├─ TimingMiddleware            → timing 创建 + set_meta
        ├─ ModeRoutingMiddleware       → 意图路由/切模式
        ├─ TravelMiddleware            → prepare_before_agent + prefetch
        ├─ MemoryRecallMiddleware      → agent_query += [USER_MEMORY]
        │
        ├─ AgentInvokeMiddleware       → astream_graph(thread_id)   ← 原 process_query
        │     └─ 异常 → on_error 链（逆序）
        │           ErrorMiddleware   → 归一化消息
        │           TimingMiddleware  → status="error" 收尾
        │
        └─ after 链（逆序）
        ├─ TravelMiddleware            → process_after_agent（display_text 先成型）
        ├─ ExportMiddleware            → 解析导出路径（依赖 travel_after.display_text）
        ├─ MemoryPipelineMiddleware    → explicit remember + pipeline
        ├─ SessionPersistenceMiddleware→ history + autosave
        └─ TimingMiddleware            → finish(status="ok")
```

> `TravelMiddleware.after` 必须在 `ExportMiddleware.after` 之前——这就是「排序显式化」带来的收益，现状靠代码顺序隐式保证。

---

## 7. 落地步骤

### V0 —— 骨架（✅ 已落地）

- 新增 `middlewares/` 包：`base.py`（`TurnContext` / `TurnMiddleware` / `TurnOrchestrator`）+ `__init__.py`。
- 仅依赖标准库，不依赖 Streamlit / LangGraph；**不注入现有流程**，空链可运行。

### V1 —— 编排层中间件化（核心，2~3 天）

1. 建 `middlewares/registry.py`：`build_default_chain()` 默认有序链 + 配置开关。
2. 逐块迁移：Timing → Travel → MemoryRecall → AgentInvoke → Export → MemoryPipeline → SessionPersistence → Error。每迁一个，`render_chat` 减一段，回归一轮（用 `QA/` 目录用例）。
3. `render_chat()` 收敛为 ~40 行：建 ctx → `orchestrator.run()` → 按 ctx 渲染 UI。
4. `session_store.archive_current_session` 归档钩子改调 `orchestrator.run_memory_only()`（复用链但只跑记忆类中间件）。

### V2 —— LangGraph 层面（可选，暂不建议优先）

- `create_react_agent(middleware=[...])` 可挂 LangChain `BaseMiddleware`，用于**单次模型调用**维度（每轮 LLM 调用前注入、调用后工具结果审计）。
- **不建议优先做**：模型调用级记忆注入会放大 Token 成本，且与编排层 `[USER_MEMORY]` 语义重复。

---

## 8. 文件结构规划

```
agents-master/
├── middleware/ 或 middlewares/
│   ├── __init__.py            # 导出 TurnContext / TurnMiddleware / TurnOrchestrator（✅ 已建）
│   ├── base.py                # 协议与编排器（✅ 已建）
│   ├── registry.py            # build_default_chain()：默认有序链 + 配置开关（V1）
│   ├── timing_mw.py           # V1
│   ├── mode_routing_mw.py     # V1
│   ├── travel_mw.py           # V1：薄封装，复用 modes/travel/handler
│   ├── memory_recall_mw.py    # V1
│   ├── agent_invoke_mw.py     # V1：原 process_query
│   ├── export_mw.py           # V1
│   ├── memory_pipeline_mw.py  # V1
│   ├── session_persist_mw.py  # V1
│   ├── error_mw.py            # V1
│   └── extras/                # 新增：sensitive_filter / audit_log / retry / mcp_guard
└── ui/chat.py                 # V1 瘦身：建 ctx、跑链、渲染
```

---

## 9. 风险与取舍

| 风险 | 对策 |
|---|---|
| Streamlit `run_until_complete` / `st.rerun` 与纯 async 链混合 | Orchestrator 提供 `run()`（同步）与 `arun()` 双入口，UI 层只调同步版 |
| 中间件间隐式数据依赖（Export 依赖 Travel 的 display_text） | 契约写进 `TurnContext` 字段注释 + `order` 显式声明，链初始化做依赖检查 |
| 记忆流水线含后台线程（archive 快路径） | 线程内不碰 `st.session_state`，只走纯函数，与现状一致 |
| 迁移期回归风险 | 每步「先包一层再拆层」，保持与原模块函数签名转发；逐步迁移逐个回归 |
| 过度框架化 | V1 只做编排层中间件；**不建议**包「Agent 框架」或提前上 V2 |

---

## 10. 相关文档

| 文档 | 说明 |
|------|------|
| [app.py架构说明与拆分建议.md](./architecture.md) | app.py 职责边界与既有拆分 |
| [多模式Agent架构选型.md](./modes.md) | 模式包 + registry 设计（TravelMiddleware 的底座） |
| [旅行规划-职责分层与步骤依据(实现).md](./travel-impl.md) | Agent / 编排 / Prompt 分工 |
| [../test-analysis/记忆系统现状与优化.md](./memory.md) | 记忆注入/抽取现状（Memory 类中间件的依据） |

---

## 关联

- 相关：[[host/architecture]]
- 相关：[[host/memory]]
- 相关：[[host/modes]]
