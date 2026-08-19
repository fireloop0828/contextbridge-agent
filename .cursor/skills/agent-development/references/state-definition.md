# State 定义规范

## 1. State 的分类

先明确各类状态及其生命周期：

| 类型 | 生命周期 | ContextBridge 示例 |
|------|----------|--------------------|
| 会话态 | 单次对话 | `thread_id`、`history` |
| 业务态 | 单次任务流程 | `travel_phase`、`travel_intake` |
| 持久态 | 跨会话 | `user_preferences`（memory_store） |
| 缓存态 | 有失效条件 | `travel_facts`、`tool_memory` |

## 2. 集中初始化

所有状态键在**一处**集中定义默认值，避免散落各处导致「幽灵键」。

正例（`init_travel_state` 模式）：

```python
defaults = {
    "app_mode": APP_MODE_GENERAL,
    "travel_phase": PHASE_INTAKE_1,
    "travel_intake": empty_intake(),
    # ... 其余键
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value
```

**反例**：在 UI 各处 `if "xxx" not in st.session_state` 散弹式初始化，新增一个键要到处找哪里该初始化。

## 3. 不可变合并原则

更新状态时返回新对象，而非原地修改；更新字段走白名单，跳过空值。

正例（`merge_intake` 模式）：

```python
def merge_intake(intake, updates):
    merged = dict(intake)  # 先复制，不原地改
    for key, value in updates.items():
        if key not in INTAKE_FIELDS:  # 白名单过滤
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue  # 跳过空值
        merged[key] = value
    return merged
```

**要点**：白名单字段、跳过空值、返回新 dict。变更集中、可测试、可追溯。

## 4. 状态机 phase 定义

强流程用显式枚举 + 集中推进：

- phase 用字符串常量（`PHASE_*`），配中文 label 映射。
- 推进逻辑集中在一个函数（`prepare_phase_before_agent`）。
- 每个 phase 有对应的 Agent 指令（`_phase_instruction`）。

**原则**：phase 转移图应能单独画出来、单独测试，不依赖真实 Agent 运行。

## 5. 状态与 Agent 的边界

状态机「外层」与 Agent「内层」要解耦：

- 状态机决定「当前该做什么 phase」。
- Agent 在 phase 约束下「自主完成工具编排」。
- 通过 `build_travel_context` 把 phase / intake 注入给 Agent。

**反例**：把 phase 判断逻辑塞进 Prompt 让模型自己猜（不稳定、难调试、无法单独测状态机）。

## 6. 缓存态的失效

- 明确缓存何时失效（如目的地变更时重置 POI 确认状态，`reset_poi_selection_state`）。
- 失效条件写成可测试的纯函数（如 `should_reset_agent_thread_*`）。

**原则**：每个缓存态都要能回答「何时失效、谁来清」。失效条件不可测试 = 迟早出 bug。

## 7. 检查清单

- [ ] 所有状态键集中初始化，无散弹式 `if key not in ...`
- [ ] 状态更新用不可变合并，白名单过滤，跳过空值
- [ ] phase 用显式常量 + 集中推进函数
- [ ] phase 转移图可单独测试（不依赖真实 Agent）
- [ ] 状态机外层与 Agent 内层解耦，不把 phase 判断塞进 Prompt
- [ ] 每个缓存态明确失效条件与清理时机
- [ ] 状态结构可序列化（能落库/恢复/调试打印）
