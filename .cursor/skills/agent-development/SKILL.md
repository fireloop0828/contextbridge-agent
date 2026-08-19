---
name: agent-development
description: "Agent 开发规范与方法论：Agent 设计、Tool Schema、State 定义、Prompt 模板、Evaluation 方法，结合 ContextBridge（agents-master + rag-server）实战正反例。用户说「开发 agent」「设计 agent」「写 agent」「tool schema」「定义 state」「状态定义」「prompt 模板」「评估 agent」「agent 评测」「agent development」「开发规范」时使用。"
---

# Agent Development

指导如何规范地设计、实现与评估一个 Agent。规范为主，ContextBridge（`agents-master` + `rag-server`）实战代码为辅证，每条原则都能在本仓库找到正例或反例对照。

## 模块索引

| 模块 | 内容 | 详细规范 |
|------|------|----------|
| Agent 设计 | 架构分层、多模式、编排方式、记忆、错误处理 | [references/agent-design.md](references/agent-design.md) |
| Tool Schema | MCP/函数工具的参数设计、描述、校验、错误回传 | [references/tool-schema.md](references/tool-schema.md) |
| State 定义 | 会话状态、阶段机、intake、不可变原则 | [references/state-definition.md](references/state-definition.md) |
| Prompt 模板 | 角色/工具/指令/输出四段式、阶段化注入 | [references/prompt-templates.md](references/prompt-templates.md) |
| Evaluation | 检索/生成指标、评估器抽象、黄金集 | [references/evaluation.md](references/evaluation.md) |

## 使用方式

1. 按需加载对应 reference，不要一次读全部。
2. 设计 Agent 时按模块顺序走：设计 → Tool → State → Prompt → 评估。
3. 每个模块内部参考 ContextBridge 正例/反例对照，先对照再动手。

## 快速判断（各模块核心原则）

- **设计**：先定边界，再定模式；强流程用状态机，弱流程用 ReAct；层间单向依赖。
- **Tool**：schema 写清「做什么 + 何时用 + 怎么校验」；失败回传可读错误而非崩整轮。
- **State**：状态集中初始化、不可变合并、变更显式；每个缓存态要能回答「何时失效、谁来清」。
- **Prompt**：标签化分区（ROLE/TOOLS/INSTRUCTIONS/OUTPUT），变的部分按 phase 运行时注入。
- **评估**：先定指标再建集；检索与生成分开评；回归可复现（黄金集 + 工具桩）。

## 流程

### 1. 定边界（Agent 设计）

先回答：哪些环节必须严格控制（低自由度），哪些可放开（高自由度）。据此选编排方式：

- 强流程、多轮采集、需控制每轮做什么 → 显式状态机
- 开放问答、工具自主选择 → ReAct
- 可组合：状态机做外层流程，ReAct 做单轮内工具编排

详见 [references/agent-design.md](references/agent-design.md)。

### 2. 定工具（Tool Schema）

每个工具写清：

- `description`：做什么、何时用、参数含义
- `input schema`：类型、默认值、边界、required
- 错误处理：参数错 → `isError` 说明；业务错 → 可读 + 排查提示；未知错 → 通用文案

详见 [references/tool-schema.md](references/tool-schema.md)。

### 3. 定状态（State 定义）

- 所有状态键集中初始化，避免散弹式 `if key not in session`
- 更新用不可变合并 + 白名单过滤
- 强流程用 phase 枚举 + 集中推进函数，phase 转移图可单独测试

详见 [references/state-definition.md](references/state-definition.md)。

### 4. 定 Prompt（Prompt 模板）

- 四段式：`<ROLE>` 角色 / `<TOOLS>` 工具分组 / `<INSTRUCTIONS>` 步骤化准则 / `<OUTPUT_FORMAT>` 输出模板
- 不变的部分（角色/规则）放 System Prompt；变的部分（phase/数据）运行时注入
- 低自由度场景用命令语气 + 清单，高自由度用建议语气

详见 [references/prompt-templates.md](references/prompt-templates.md)。

### 5. 定评估（Evaluation）

- 检索层：Hit Rate@K、MRR、NDCG@K
- 生成层：Faithfulness、Answer Relevancy、Context Precision
- 统一 Evaluator 接口 + 组合模式；黄金测试集沉淀坏 Case；测试分层 unit/integration/e2e

详见 [references/evaluation.md](references/evaluation.md)。

## 参考代码索引（ContextBridge）

设计 Agent 时对照下列文件，先读正例再动手：

| 主题 | 文件 |
|------|------|
| 多模式抽象（最小接口） | `agents-master/modes/types.py` |
| 模式注册表与路由 | `agents-master/modes/registry.py` |
| 状态机 + intake + phase 推进 | `agents-master/modes/travel/state_machine.py` |
| Tool schema 正例 | `rag-server/src/mcp_server/tools/query_knowledge_hub.py` |
| 轻量工具（FastMCP 装饰器） | `agents-master/mcp_server_rag.py` |
| System Prompt 四段式 | `agents-master/prompts/general_system.md` |
| 工具失败降级 | `agents-master/app.py`（`_mcp_tool_error_message` / `format_agent_error`） |
| 评估体系 | `rag-server/DEV_SPEC.md`（3.3.4 / 4.3 节） |
| 测试分层 | `rag-server/tests/`（unit / integration / e2e） |
