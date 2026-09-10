---
id: analysis/mcp-init-performance
title: MCP 初始化性能分析与优化
tags: [analysis, mcp, performance]
sources:
  - agents-master/config/mcp_config.py
  - agents-master/config.json
  - agents-master/app.py
related: [host/mcp-client, integration/mcp-lifecycle, analysis/token-optimization]
updated: 2026-09-10
---
# MCP 初始化性能分析与优化

> **TL;DR**：Host 首次打开页面要 spawn 4 个 MCP 子进程，`npx` 冷启动是主要耗时；已用「解析本地 mcp-amap + 切模式只重建 Agent 不重连 MCP」把初始化压下来，`get_tools()` 握手仍有固有开销。

> 文档版本：v1.0  
> 更新日期：2026-06-05  
> 适用项目：`agents-master`（Streamlit + LangGraph ReAct + MultiServerMCPClient）

---

## 1. 现象

用户反馈：**初始化连接 MCP 服务器明显比早期变慢**，表现为：

- 首次打开页面「正在连接 MCP 服务器…」等待很久
- 切换「通用模式 / 旅行规划」、切换模型时也会长时间转圈

---

## 2. 测试结论（本机实测）

### 2.1 当前 `config.json` 注册的 MCP（4 个）

| MCP Server | 启动方式 | 单次 `load_mcp_tools` 耗时 |
|------------|----------|---------------------------|
| `get_current_time` | Python stdio | ~0.6s |
| `document-export` | Python stdio | ~0.6s |
| `rag-server` | Python stdio（含 chromadb 预加载） | ~0.5–0.6s |
| **`amap-maps`** | **`npx -y @amap/amap-maps-mcp-server`** | **~15–17s** |

`MultiServerMCPClient.get_tools()` 会**并行**连接各 Server，总墙钟时间 ≈ **最慢的那个**。

因此当前全量初始化约 **15–20 秒**，瓶颈几乎全在高德。

### 2.2 对比「以前为什么快」

早期 README 默认仅 **2 个** MCP：`get_current_time` + `rag-server`，并行后约 **1 秒**。

旅行规划模式上线后新增：

- `document-export`（影响小）
- **`amap-maps`（影响极大，且原先用 `npx -y`）**

### 2.3 高德慢的真正原因

对同一包对比：

| 启动命令 | 耗时 |
|----------|------|
| `npx -y @amap/amap-maps-mcp-server` | **~16s** |
| 直接调用 `mcp-amap` 可执行文件（npx 缓存或 `node_modules/.bin`） | **~45ms** |

**结论：慢在 `npx` 包装层，不是高德 MCP 业务逻辑本身。**

### 2.4 其他加重因素

1. **每次 `reconnect_agent()` 都会 `get_tools()`**，为 4 个 Server 各起子进程 → 握手 → 拉工具列表 → 关闭，无法复用连接。
2. **切换对话模式 / 切换模型** 时原先也走全量重连，但这两类操作**只改 System Prompt 或 LLM**，不必重连 MCP。
3. **`reconnect_agent()` 每次写 `config.json`**，即使配置未变也触发完整流程。
4. 网络或 npm 异常时，`npx` 可能长时间超时（实测失败场景可达 70s+）。

---

## 3. 已实施的优化（对应原建议 ①②③）

### 优化 ①：绕过 `npx -y`，解析本地 `mcp-amap`

**改动：**

- `config.json` 中 `amap-maps` 改为 `command: "mcp-amap"`（由 `resolve_mcp_config()` 解析为绝对路径）
- 解析逻辑在 `config/mcp_config.py` 的 `_resolve_amap_maps_command()`，按优先级查找：
  1. `agents-master/node_modules/.bin/mcp-amap`（`npm install` 后）
  2. `~/.npm/_npx/*/node_modules/.bin/mcp-amap`（历史 npx 缓存）
- 新增 `package.json`，依赖 `@amap/amap-maps-mcp-server`

**首次部署请执行：**

```bash
cd agents-master
npm install
```

**预期效果：** 全量 MCP 初始化从 ~17s 降至 **约 1–2s**。

### 优化 ②：模式切换仅重建 Agent，不重连 MCP

**改动：**

- 新增 `rebuild_agent_only()`，复用 `session_state.mcp_tools` 缓存，只重建 `create_react_agent`（更新 Prompt / 模型）
- 侧边栏切换「通用 / 旅行」、聊天意图进入旅行模式时：若 MCP 已连接 → 调用 `rebuild_agent_only()`，否则才全量 `reconnect_agent()`

**预期效果：** 切换模式从十几秒变为 **亚秒级**。

### 优化 ③：减少无谓的全量重连与写盘

**改动：**

- 切换模型点「应用」→ `rebuild_agent_only()`（不再 `get_tools()`）
- `reconnect_agent()` 仅在 `config.json` 内容实际变化时写入磁盘
- 全量重连保留给：首次连接、MCP 配置增删改

**缓存字段：**

- `st.session_state.mcp_tools`：已加载工具列表
- `st.session_state.applied_mcp_config_sig`：已应用 MCP 配置签名（用于判断是否需要重连）

---

## 4. 架构说明（为何 `get_tools` 仍偏慢）

`langchain-mcp-adapters >= 0.1` 的 `get_tools()` 会为每个 Server **临时**建立 stdio 会话，列出工具后关闭；真正工具调用时再建新会话。因此：

- **全量初始化**仍要启动每个子进程至少一次
- 优化重点是：**少调用全量初始化** + **缩短最慢子进程（高德）的启动时间**

---

## 5. 后续可选优化（未实施）

| 方向 | 说明 |
|------|------|
| 旅行模式懒加载高德 | 通用模式不注册 `amap-maps`，进入旅行再连（需动态工具集） |
| MCP 子进程长驻 | 自管连接池，改动较大 |
| `rag-server` 轻量化启动 | 评估是否可延迟 chromadb 预加载（需改 rag-server） |

---

## 6. 验证方法

1. 重启 `streamlit run app.py`，观察首次「正在连接 MCP 服务器…」耗时（目标 1–2s）
2. 切换通用 ↔ 旅行，应几乎无等待
3. 侧边栏切换模型并「应用」，应几乎无等待
4. 侧边栏增删 MCP 工具后，仍应触发全量重连（预期行为）

可使用侧边栏 **耗时测试** 或浏览器 Network/终端日志辅助对比优化前后。

---

## 7. 相关文件

| 文件 | 说明 |
|------|------|
| `config.json` | MCP Server 注册表 |
| `config/mcp_config.py` | `resolve_mcp_config`、高德 `mcp-amap` 路径解析 |
| `app.py` | `reconnect_agent`、`rebuild_agent_only` |
| `package.json` | 高德 MCP npm 依赖（需 `npm install`） |

## 关联

- 相关：[[host/mcp-client]]
- 相关：[[integration/mcp-lifecycle]]
- 相关：[[analysis/token-optimization]]
