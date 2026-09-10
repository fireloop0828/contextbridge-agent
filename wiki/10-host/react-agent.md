---
id: host/react-agent
title: ReAct Agent 与运行方式
tags: [host, react, langgraph, run]
sources:
  - agents-master/app.py
  - agents-master/config/models.py
  - agents-master/requirements.txt
related: [host/architecture, host/mcp-client, host/prompts]
updated: 2026-09-10
---

# ReAct Agent 与运行方式

> **TL;DR**：Host 用 LangGraph 的 `create_react_agent` 构建一个「推理 → 调工具 → 再推理」的 ReAct 智能体，把 MCP 拉取到的工具列表作为可用工具；本地运行只需 `streamlit run app.py`，首次打开页面会自动连接 MCP 并创建 Agent。

## 是什么

ReAct Agent 是 Host 的推理核心：给定「聊天模型 + 工具列表」，它在「思考 → 调用工具 → 读取工具结果 → 继续思考」的循环中推进，直到不再需要工具、输出最终回答。工具列表由 MCP Client 从各 MCP Server 拉取并合并而来（见 [[host/mcp-client]]）。

三种对话模式（通用 / 知识库问答 / 旅行）**共用同一个 ReAct Agent**，区别只在系统提示词与是否由 Python 预调工具，见 [[host/modes]]。

## 为什么这样设计

- **单 Agent + 工具池**：多模式不靠「多个 Agent」实现，而是换提示词与编排，避免为每种场景维护一套推理逻辑。
- **工具即能力边界**：Agent 能做什么完全由 MCP 工具列表决定，新增能力只需注册 MCP Server，不改推理代码。
- **流式可见**：工具调用过程通过流式回调渲染到界面，便于观察与排障。

## 怎么实现

1. **环境**：Python ≥ 3.12，在 `agents-master/` 建 venv 并 `pip install -r requirements.txt`。
2. **配置**：复制 `.env.example` 为 `.env`，至少配置一种模型的 Key（推荐阿里云百炼的 `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL`）。
3. **旅行模式额外依赖**：`npm install` 安装 `@amap/amap-maps-mcp-server`（避免 `npx` 冷启动），并配置 `AMAP_MAPS_API_KEY`。
4. **启动**：`streamlit run app.py`，默认 `http://localhost:8501`；首次打开页面会自动初始化（连接 MCP + 建 Agent）。
5. **模型切换**：侧边栏改模型后点「应用模型」——**只重建 Agent，不重连 MCP**。

> 兼容性：新版本 `langchain-mcp-adapters` 不再支持 `async with client`，当前实现改用 `tools = await client.get_tools()`。

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/app.py` → `_build_agent_from_tools()` | 用模型 + 工具创建 ReAct Agent |
| `agents-master/app.py` → `initialize_session()` | 连接 MCP、拉工具、建 Agent |
| `agents-master/config/models.py` | 模型列表与 `create_chat_model` |
| `agents-master/ui/chat.py` | 聊天渲染与流式回调 |

## 关联

- 相关：[[host/architecture]]
- 相关：[[host/mcp-client]]
- 相关：[[host/prompts]]
