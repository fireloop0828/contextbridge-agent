# app.py 架构说明与拆分建议

> 说明为何 `app.py` 内 Prompt 与处理逻辑较多、各区块职责、是否过大及如何组件化。  
> 供优化决策参考；**本文档仅为设计说明，不代表已实施重构**。

---

## 1. 为什么 app.py 里也有很多「提示词和处理」？

`app.py` **不只是旅行 Agent**，而是整个 Streamlit 应用的**主入口**，其中混合了四类内容：

### A. 通用 Agent 的 System Prompt（约 166–243 行）

`SYSTEM_PROMPT` 服务于 **通用模式**，同时也是 **旅行模式的 Prompt 底座**：

- RAG 工具使用说明  
- 文档导出（`write_markdown_document`）说明  
- 通用回答步骤与来源格式

旅行模式启动时，`travel_mode.build_system_prompt()` 会 **再拼接** `data/prompt/travel-planner.md`：

```text
最终 System Prompt（旅行）= SYSTEM_PROMPT + <TRAVEL_MODE> 头 + travel-planner.md
```

因此：**旅行专用流程写在 md 文件里；通用能力写在 app.py 的 SYSTEM_PROMPT 里**——这是「看起来 app.py Prompt 很多」的主要原因之一。

### B. 旅行相关逻辑（已部分外迁）


| 内容                       | 位置                                                                       | 作用                        |
| ------------------------ | ------------------------------------------------------------------------ | ------------------------- |
| 状态机、9 字段 intake、phase 跳转 | `travel_mode.py`                                                         | 核心编排                      |
| 每轮 `[TRAVEL_CONTEXT]`    | `travel_mode.py` → `build_travel_context`                                | 本回合 phase、缺项、工具清单         |
| 用户消息包装 / 回复后处理           | `app.py` → `handle_travel_user_message`、`finalize_travel_assistant_text` | 调用 travel_mode，更新 session |
| 交付校验                     | `travel_mode.py` → `check_travel_delivery`                               | 检查完整 MD、是否导出              |


旅行规则 **不应再堆进 app.py**；当前已基本集中在 `travel_mode.py`。

### C. 基础设施（与具体业务弱相关）

- MCP 连接 / 重连 / `resolve_mcp_config`（含高德 `mcp-amap` 路径解析）  
- 模型工厂 `create_chat_model`、可用模型列表  
- 流式回调、`format_agent_error`、MCP 工具失败降级（`ToolNode.handle_tool_errors`）  
- 耗时日志（`timing_log.py`）、导出路径解析

### D. Streamlit UI（占行数最多）

- 两个 `with st.sidebar:` 大块（约 1174–1513 行）  
- 登录、模型选择、MCP JSON 编辑、导出列表、重置对话  
- 聊天历史渲染、主输入循环

**结论**：app.py 中的「各种处理」大部分是 **宿主应用 + 通用 Agent 运行时**；旅行只是其中一条业务链路。

---

## 2. Prompt 分层一览（避免混淆）


| 层级               | 存储位置                                  | 何时生效           | 内容性质                          |
| ---------------- | ------------------------------------- | -------------- | ----------------------------- |
| 通用 System Prompt | `app.py` → `SYSTEM_PROMPT`            | Agent 创建时      | RAG、导出、通用指令                   |
| 旅行 System Prompt | `data/prompt/travel-planner.md`       | 旅行模式 Agent 创建时 | 阶段行为、MD 模板、工具顺序               |
| 动态回合上下文          | `travel_mode.py` → `[TRAVEL_CONTEXT]` | **每一轮**用户消息前   | phase、intake 快照、本回合 checklist |


**LLM 每轮实际读到**：

1. System：通用 + 旅行（静态）
2. 历史消息
3. 用户消息（实为：`[TRAVEL_CONTEXT]` + 用户原文）

---

## 3. app.py 体量与模块地图

当前约 **1675 行**（参考：`travel_mode.py` 787 行，`timing_log.py` 451 行——已有 partial 拆分）。


| 区块（约）                     | 行数量级      | 职责                    |
| ------------------------- | --------- | --------------------- |
| 配置加载 / 登录 / 页面标题          | 1–165     | 入口、鉴权、模式品牌文案          |
| `SYSTEM_PROMPT`           | 166–243   | 通用 Agent 系统提示         |
| 模型列表 + MCP resolve + 模型工厂 | 245–525   | 配置与 LLM 实例化           |
| 导出 / 聊天渲染 / 流式 / 错误 / 查询  | 526–908   | 对话运行时                 |
| Agent 初始化 / 重连 / 缓存工具     | 909–1034  | MCP + ReAct 生命周期      |
| 模式 UI + 侧边栏设置 + MCP 编辑    | 1036–1513 | **Streamlit UI（最大块）** |
| 旅行薄封装 + 主循环               | 1515–1675 | 聊天入口、travel hook      |


### 已拆出的模块


| 文件                                            | 职责                    |
| --------------------------------------------- | --------------------- |
| `travel_mode.py`                              | 旅行状态机、intake、意图、上下文包装 |
| `timing_log.py`                               | 耗时采集与测试报告导出           |
| `mcp_server_time.py` / `mcp_server_export.py` | 独立 MCP Server         |
| `utils.py`                                    | `astream_graph` 等工具函数 |


### 问题本质

典型 **Streamlit 单文件应用（Monolithic Script）** 模式：

- UI 声明式代码与业务逻辑写在同一文件  
- 侧边栏两个 block 合计约 **350+ 行**  
- 随功能迭代（旅行模式、耗时测试、MCP 优化）持续膨胀

**功能上可维护，结构上不利于单人快速定位与单测。**

---

## 4. 能否拆分？推荐目录结构

**可以，且建议拆**；目标：`app.py` 仅做 **Streamlit 装配与事件接线**，逻辑下沉到模块。

```text
agents-master/
├── app.py                      # 目标：<400 行，layout + wiring
├── prompts/
│   └── general_system.md       # 原 SYSTEM_PROMPT 外置
├── config/
│   ├── mcp_config.py           # load/save/resolve_mcp_config、amap 路径
│   └── models.py               # 模型列表、create_chat_model、OUTPUT_TOKEN_INFO
├── agent/
│   ├── session.py              # initialize_session、reconnect、rebuild_agent_only
│   ├── errors.py               # format_agent_error、_mcp_tool_error_message
│   └── query.py                # process_query、get_streaming_callback
├── ui/
│   ├── sidebar_settings.py     # 模型、超时、MCP JSON 编辑
│   ├── sidebar_mode.py         # 模式切换、caption
│   ├── sidebar_exports.py      # 导出列表、重置、耗时测试
│   └── chat.py                 # print_message、主输入循环
├── travel_mode.py              # 保持现状
├── timing_log.py               # 保持现状
└── data/prompt/
    └── travel-planner.md       # 已有
```

---

## 5. 拆分优先级与风险


| 优先级     | 动作                                            | 收益                                 | 风险 / 成本                                         |
| ------- | --------------------------------------------- | ---------------------------------- | ----------------------------------------------- |
| **P0**  | UI 拆到 `ui/`                                   | app.py 体积减半，改界面不改逻辑                | Streamlit `session_state` 引用需统一从 app 传入或保留全局 st |
| **P1**  | `SYSTEM_PROMPT` → `prompts/general_system.md` | 与 travel-planner 对称，改 Prompt 不碰 py | 启动时多读一个文件，几乎无风险                                 |
| **P2**  | `config/mcp_config.py` + `agent/session.py`   | MCP/Agent 生命周期可单测                  | import 路径调整，需跑通首次连接与模式切换                        |
| **P3**  | `agent/query.py` + `agent/errors.py`          | 对话与错误处理独立                          | 与 session 循环依赖，拆时保持接口稳定                         |
| **不建议** | 再包一层「Agent 框架」                                | —                                  | 当前规模过度设计                                        |


### 拆分原则

1. **行为不变优先**：每拆一步都应能 `streamlit run app.py` 回归旅行全流程。
2. **旅行规则不进 app.py**：继续只调用 `travel_mode` 公开 API。
3. **UI 与 Agent 运行时分离**：便于以后换 UI（如 FastAPI + 前端）时复用 `agent/`、`config/`。
4. **Prompt 文件化**：通用 + 旅行均用 md，py 只负责 `load` 与 `build_system_prompt`。

---

## 6. 优化决策检查清单

在动手重构前，可对照以下问题：

- 主要痛点是 **改 Prompt 不方便**，还是 **改 UI 难找代码**，还是 **无法单测 MCP 连接**？  
- 是否接受 `app.py` 仍保留 `st.session_state` 初始化，子模块只接收/回调？  
- 是否将 `SYSTEM_PROMPT` 外置为 md（与 travel-planner 一致）？  
- 第一轮是否 **只拆 UI**，暂不动 Agent session 逻辑？  
- 是否需要为 `travel_mode.prepare_phase_before_agent` 补单元测试（与 app 拆分独立）？

---

## 7. 相关文档


| 文档                                                                     | 说明                          |
| ---------------------------------------------------------------------- | --------------------------- |
| [旅行规划-职责分层与步骤依据.md](./旅行规划-职责分层与步骤依据.md)                               | Agent / 编排 / Prompt 分工与每步依据 |
| [旅行规划模式-需求与架构.md](./旅行规划模式-需求与架构.md)                                   | 产品需求与原始架构设计                 |
| [../test-analysis/MCP初始化性能分析与优化.md](../test-analysis/MCP初始化性能分析与优化.md) | MCP 连接性能（已实施优化）             |


---

## 8. 一句话总结

- **app.py Prompt 多**：通用底座 + 整站 UI + MCP 运行时都在此文件；旅行规则已在 `travel_mode.py` + `travel-planner.md`。  
- **app.py 偏大**：Streamlit 单体脚本 + 侧边栏 UI 堆叠；已有 partial 拆分（travel_mode、timing_log）。  
- **下一步**：优先 UI 与 Prompt 外置，Agent session 次之；避免过度框架化。

