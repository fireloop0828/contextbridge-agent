---
id: integration/mcp-lifecycle
title: MCP 子进程生命周期与重连
tags: [integration, mcp, lifecycle]
sources:
  - wiki/10-host/mcp-client.md
  - agents-master/app.py
related: [host/mcp-client, integration/end-to-end, decisions/0003-mcp-stdio]
updated: 2026-09-10
---

# MCP 子进程生命周期与重连

> **TL;DR**：MCP 服务由 Host 在初始化时**按需 spawn 子进程**（stdio），生命周期与会话绑定；**改 MCP 配置才全量重连**（`reconnect_agent()`），**切模式/换模型只重建 Agent**（`rebuild_agent_only()`，复用已缓存的 `mcp_tools`）。

## 是什么

初始化时序（Host 侧）：

```
打开页面 / 改 MCP 配置
  → load_config_from_json()  读注册表
  → resolve_mcp_config()     解析路径、venv、密钥
  → MultiServerMCPClient     用解析后的配置创建连接器
  → client.get_tools()       spawn 各 Server 子进程、握手、并行拉工具列表
  → 合并为 mcp_tools
  → _build_agent_from_tools() 用模型 + 工具创建 ReAct Agent
  → 用户发消息 → Agent 按需 tools/call
```

## 为什么这样设计

- **stdio 免运维**：Host 启动即自动拉起 4 个 MCP，无需预先起服务、无端口占用，本地联调成本最低。
- **重连有成本**：spawn 子进程 + 握手 + 拉工具列表需要时间（高德冷启动可达十余秒），所以**能复用就复用**。
- **缓存换速度**：三种模式共用同一套 `mcp_tools`，切模式只换提示词与模式逻辑，不重连。

## 怎么实现

**重连策略**：

| 用户操作 | 调用逻辑 | 是否重连 MCP |
| --- | --- | --- |
| 首次打开页面 | `ensure_session_ready()` → `reconnect_agent()` | ✅ |
| 侧边栏增删 / 改 MCP | `reconnect_agent()` | ✅（配置写回 `config.json`） |
| 切换对话模式 | `rebuild_agent_only()` | ❌（复用 `mcp_tools`） |
| 切换 LLM 并「应用模型」 | `rebuild_agent_only()` | ❌ |
| 需重建 Agent 但工具缓存为空 | `rebuild_agent_only()` 回退 `reconnect_agent()` | ✅（兜底） |

**会话状态**（存于 `st.session_state`）：`pending_mcp_config`、`mcp_client`、`mcp_tools`、`tool_count`、`applied_mcp_config_sig`、`session_initialized`。

**stdio vs HTTP/SSE**：

| 维度 | stdio（本项目） | HTTP / SSE（对比） |
| --- | --- | --- |
| 谁启动 Server | 客户端按注册表 spawn 子进程 | 运维事先单独启动 |
| 生命周期 | 与 Host 会话绑定 | Server 可长期驻留 |
| 网络 | 无端口，本机管道 | 需开端口、健康检查 |
| 日志 | stdout 只能走协议，日志须走 stderr | 约束较宽松 |

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/app.py` → `initialize_session()` | 读配置、建客户端、拉工具、建 Agent |
| `agents-master/app.py` → `rebuild_agent_only()` | 轻量重建，复用工具缓存 |
| `agents-master/app.py` → `reconnect_agent()` | 全量重连 |
| `agents-master/app.py` → `cleanup_mcp_client()` | 断开前清空客户端引用 |

## 关联

- MCP 配置解析：[[host/mcp-client]]
- 端到端链路：[[integration/end-to-end]]
- 决策记录：[[decisions/0003-mcp-stdio]]
- 性能分析：[[analysis/mcp-init-performance]]
