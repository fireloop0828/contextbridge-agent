# app.py 架构说明与拆分建议

> 说明 `app.py` 与各模块的职责边界、已完成的拆分，以及后续可选优化。  
> **2026-07 更新**：P0（UI 拆分）与 P1（Prompt 外置）已落地；下文「当前结构」以代码为准。

---

## 1. 当前结构概览

`app.py`（约 **668 行**）是 Streamlit **主入口 + Agent 运行时装配**，不再承载大块 UI 与内联 Prompt。

| 模块 | 行数（约） | 职责 |
|------|-----------|------|
| `app.py` | 668 | 事件循环、登录、MCP 连接/重连、`create_react_agent`、流式回调、旅行自动导出 |
| `ui/sidebar.py` | 562 | 模式切换、模型/MCP 配置、会话归档恢复、记忆面板 |
| `ui/chat.py` | 252 | 聊天渲染、意图路由、旅行回合（经 `modes/travel/handler`） |
| `ui/travel_evidence.py` | — | 旅行预取数据（RAG/高德）展示 |
| `modes/travel/state_machine.py` | 997 | 旅行状态机、intake、上下文拼接、交付检测 |
| `modes/travel/handler.py` | 217 | 旅行回合编排入口（`prepare_before_agent` / `process_after_agent`） |
| `modes/travel/pipeline.py` | — | 编排层 MCP 预取（RAG/高德） |
| `modes/travel/facts.py` | — | `travel_facts` 结构化事实与展示格式化 |
| `modes/travel/tool_memory.py` | — | 工具跨回合记忆（O7/O10）、checkpoint 换 thread（O4） |
| `config/mcp_config.py` | — | `load/save/resolve_mcp_config`、高德 `mcp-amap` 路径解析 |
| `config/models.py` | — | 模型列表、`create_chat_model` |
| `prompts/general_system.md` | — | 通用模式 System Prompt（原 `SYSTEM_PROMPT`） |

---

## 2. Prompt 分层（避免混淆）

| 层级 | 存储位置 | 何时生效 | 内容性质 |
|------|----------|----------|----------|
| 通用 System Prompt | `prompts/general_system.md`（`prompts.load_general_system_prompt()`） | Agent 创建时 | RAG、导出、通用指令 |
| 旅行 System Prompt | `modes/travel/general_system_travel.md` + `travel-planner.md` | 旅行模式 Agent 创建时 | 阶段行为、MD 模板、工具顺序 |
| 动态回合上下文 | `modes/travel/state_machine.py` → `[TRAVEL_CONTEXT]` | **每一轮**用户消息前 | phase、intake 快照、工具 checklist、O7 工具记忆 |

**LLM 每轮实际读到**：

1. System：通用或旅行专用（静态）
2. 历史消息（LangGraph `MemorySaver` + `thread_id`）
3. 用户消息：旅行模式下为 `[TRAVEL_CONTEXT]` + 用户原文（由 `handler` / `state_machine` 包装）

---

## 3. app.py 仍负责什么？

### A. Agent 与 MCP 生命周期

- `initialize_session()`、`reconnect_agent()`、`rebuild_agent_only()`
- `resolve_mcp_config()`（来自 `config/mcp_config.py`）
- 流式回调、`format_agent_error`、高德 CUQPS 降级文案
- `ToolNode(handle_tool_errors=...)`

### B. 旅行导出（服务端写盘）

- `auto_export_travel_plan_from_chat()` → `export_service.save_markdown_export()`
- 由 `ui/chat.py` 在 `plan_ready` 时调用；**不走** MCP `write_markdown_document`

### C. Streamlit 装配

- `render_sidebar()` + `render_chat()`（`ui/`）
- `st.session_state` 初始化
- 首次进入自动 `reconnect_agent()`

### D. 已迁出 app.py 的内容

- 侧边栏 UI → `ui/sidebar.py`
- 聊天主循环与旅行 hook → `ui/chat.py` + `modes/travel/handler.py`
- 旅行状态机 → `modes/travel/state_machine.py`
- 通用 Prompt → `prompts/general_system.md`
- MCP 配置解析 → `config/mcp_config.py`、`config/models.py`

---

## 4. 已完成的拆分（对照原建议）

| 原优先级 | 动作 | 状态 |
|---------|------|------|
| **P0** | UI 拆到 `ui/` | ✅ `sidebar.py`、`chat.py`、`travel_evidence.py` |
| **P1** | `SYSTEM_PROMPT` → `prompts/general_system.md` | ✅ |
| **P2** | `config/mcp_config.py` | ✅；`agent/session.py` 仍在 `app.py` |
| **P3** | `agent/query.py` + `agent/errors.py` | ⏸ 未拆；`process_query` 等仍在 `app.py` |
| 旅行编排 | `modes/travel/` 包 | ✅ handler + state_machine + pipeline + facts |

---

## 5. 后续可选优化（非必须）

| 方向 | 说明 | 风险 |
|------|------|------|
| `agent/session.py` | 将 MCP 连接/重连从 `app.py` 抽出 | import 与 `session_state` 耦合需小心 |
| `agent/query.py` | 对话流式与错误处理独立 | 与 session 循环依赖 |
| 旅行模式懒加载高德 | 通用模式不连 `amap-maps` | 需动态工具集 |
| 单元测试 | `state_machine.prepare_phase_before_agent` 等 | 与 UI 拆分独立，收益高 |

**不建议**：再包一层「Agent 框架」——当前规模足够。

---

## 6. 拆分原则（仍适用）

1. **行为不变优先**：每拆一步都应能 `streamlit run app.py` 回归旅行全流程。
2. **旅行规则不进 app.py**：经 `modes.travel.handler` 公开 API 接入。
3. **UI 与 Agent 运行时分离**：便于以后换 UI 时复用 `config/`、旅行包。
4. **Prompt 文件化**：通用 + 旅行均用 md，py 只负责 load 与 build。

---

## 7. 相关文档

| 文档 | 说明 |
|------|------|
| [旅行规划-职责分层与步骤依据(实现).md](./旅行规划-职责分层与步骤依据(实现).md) | Agent / 编排 / Prompt 分工 |
| [旅行规划-需求与架构(产品).md](./旅行规划-需求与架构(产品).md) | 产品需求与架构 |
| [多模式Agent架构选型.md](./多模式Agent架构选型.md) | 三模式 + registry 设计 |
| [../test-analysis/MCP初始化性能分析与优化.md](../test-analysis/MCP初始化性能分析与优化.md) | MCP 连接性能优化 |

---

## 8. 一句话总结

- **Prompt**：通用在 `prompts/general_system.md`，旅行在 `modes/travel/*.md`，动态上下文在 `state_machine`。
- **app.py**：已从 ~1675 行瘦身至 ~668 行，专注装配与 MCP/Agent 生命周期；UI 与旅行编排已外迁。
- **下一步（可选）**：`agent/session.py` 抽出、状态机单测；避免过度框架化。
