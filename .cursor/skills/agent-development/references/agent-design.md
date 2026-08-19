# Agent 设计规范

## 1. 架构分层

Agent 不应是单个巨型文件，应按职责分层，层间单向依赖（上层可调用下层，禁止反向）：

| 层 | 职责 | ContextBridge 正例 |
|----|------|--------------------|
| 入口层 | 生命周期、会话初始化、UI/协议接线 | `agents-master/app.py` |
| 编排层 | 模式路由、状态机、ReAct 循环 | `agents-master/modes/registry.py` |
| 能力层 | 工具定义、检索、导出 | `rag-server/src/mcp_server/tools/` |
| 记忆层 | 会话存储、偏好、工具记忆 | `agents-master/memory_store.py`、`session_store.py` |

**反例**：把模式路由、状态推进、工具调用、记忆读写全部堆在一个入口文件里，靠 if-else 硬切。加一个新能力要动入口文件，无法单独测试编排逻辑。

## 2. 多模式设计（Multi-mode）

ContextBridge 用 `AgentMode` Protocol 抽象多模式（`modes/types.py`），最小接口：

- `id` / `label` / `branding`：模式身份与展示
- `build_system_prompt`：构建系统提示
- `detect_intent`：意图检测，供路由
- `on_enter` / `on_exit`：进入/退出钩子

注册表（`modes/registry.py`）集中管理：

- 按 `order` 排序
- `detect_intent` 做意图路由
- 模式切换返回「是否需要重建 Agent」——Prompt 变了才重建，避免无谓开销

**原则**：新增一个模式 = 新增一个 mode 目录 + 注册表登记，不动入口层。

## 3. 编排方式选择

| 场景 | 编排 | ContextBridge 示例 |
|------|------|--------------------|
| 开放问答、工具自主选择 | ReAct（`create_react_agent`） | general / knowledge_qa 模式 |
| 强流程、多轮采集 | 显式状态机（phase） | travel 模式 |

**决策依据**：

- 任务步骤确定、需控制每轮做什么 → 状态机
- 任务开放、依赖模型判断 → ReAct
- 两者可组合：状态机做「外层流程」，ReAct 做「单轮内的工具编排」（travel 正是如此）

## 4. 状态机设计要点（强流程）

参考 `agents-master/modes/travel/state_machine.py`：

1. **显式 phase 枚举**：`PHASE_POI_SELECTION / INTAKE_1 / INTAKE_2 / GENERATING / REVISION` 等常量。
2. **phase 推进集中一处**：`prepare_phase_before_agent` 统一决定下一 phase，不在各回调里散落推进逻辑。
3. **进入 Agent 前包装上下文**：`build_travel_context` 注入 phase / intake / missing 字段。
4. **Agent 回复后收敛**：`after_assistant_response` 解析回写、推断下一 phase。

**要点**：状态机的「进入 / 退出 / 推进」要可测试——不依赖真实 Agent 也能单独跑通 phase 转移图。

## 5. 错误处理与降级

正例（`app.py` 的 `_mcp_tool_error_message`）：

- 工具失败不直接崩整轮对话，而是回传可读说明让 Agent 降级。
- 区分错误类型（限流 / 配额 / 密钥无效），给不同引导。
- 兜底 `format_agent_error` 把底层异常映射成用户可读文案。

**原则**：工具层报错「可读 + 可降级」，而非裸抛异常。

## 6. 记忆设计

ContextBridge 分层记忆：

| 层 | 生命周期 | 示例 |
|----|----------|------|
| `session_store` | 会话级 | thread_id、history |
| `memory_store` | 跨会话 | 用户偏好 |
| travel 工具记忆 | 缓存态 | `tool_memory.py`、`facts.py`（预取事实、工具结果缓存） |

**原则**：区分「会话态 / 持久态 / 缓存态」，各自生命周期与失效条件要明确。缓存态必须能回答「何时失效、谁来清」。

## 7. 边界与降级哲学

- **窄桥加护栏**：高德 API 限流时明确禁止连续调用，引导使用已有信息。
- **开阔地带允许多路线**：general 模式让模型自主选工具。

设计 Agent 前先回答：哪些环节必须严格控制（低自由度），哪些可放开（高自由度）。自由度越高，Prompt 约束越弱；自由度越低，越需要状态机 + 命令式 Prompt。

## 8. 检查清单

- [ ] 分层清晰，层间单向依赖，无反向 import
- [ ] 模式可插拔：新增模式不动入口层
- [ ] 编排方式选型有依据（状态机 vs ReAct vs 组合）
- [ ] 状态机 phase 转移集中、可单独测试
- [ ] 工具失败有可读降级，不裸抛异常
- [ ] 各层记忆生命周期与失效条件明确
- [ ] 每个环节的自由度有意识设计，不是默认放开
