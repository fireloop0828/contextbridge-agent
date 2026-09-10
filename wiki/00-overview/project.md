---
id: overview/project
title: 项目定位与架构总览
tags: [overview, architecture, monorepo]
sources:
  - README.md
  - agents-master/README.md
  - rag-server/README.md
related: [overview/repo-map, integration/end-to-end, decisions/0001-monorepo-split]
updated: 2026-09-10
---

# 项目定位与架构总览

> **TL;DR**：ContextBridge Agent 是基于 **LangGraph + MCP** 的多模式智能体工作台，采用 monorepo 双子系统结构——`agents-master` 作为 MCP Host 负责界面与 Agent 编排，`rag-server` 作为 RAG MCP Server 负责知识入库与混合检索，二者通过 MCP（stdio）协议解耦联动。

## 是什么

本项目是一个**智能体工作台**：用户在网页里与 Agent 对话，Agent 通过 MCP 动态接入外部工具（时间、地图、知识库、文档导出）完成任务。它由两个可独立运行的子系统组成：

- `agents-master/`：**主应用 / MCP Host**。承载 Streamlit 聊天界面与 LangGraph ReAct 推理循环，负责会话、多模式切换、MCP 客户端管理与工具编排。
- `rag-server/`：**RAG MCP Server**。负责文档入库、Dense + BM25 混合检索、精排与评估，并对外暴露 `list_collections` / `query_knowledge_hub` / `get_document_summary` 三个工具。

两者**不互相 import Python 包**，仅通过 MCP 协议通信，因此可以各自独立启动、独立测试、独立演进。

![项目架构图](../../rag-server/assets/image.png)

## 为什么这样设计

一个 Python 项目直接包揽 Host 与 RAG 最省事，但会带来三个问题：**依赖冲突**（RAG 需要 chromadb 等重型包，Host 偏 UI/Agent）、**职责纠缠**（无法单独测试或替换任一侧）、**部署僵化**（改一边要动整体）。

因此选择 monorepo + 双进程 + MCP 解耦：

1. **依赖隔离**：两边各用独立 venv，互不污染。
2. **职责边界**：rag-server 可脱离 Host 单独用 `scripts/query.py` 验证检索链路。
3. **协议解耦**：MCP 是跨进程工具标准，可独立重启与版本演进。
4. **联调便利**：同一仓库便于一起改接口，运行时仍是两个进程。

## 怎么实现

- **启动**：在 `agents-master/` 执行 `streamlit run app.py`，首次打开页面时自动连接各 MCP 服务并创建 Agent（无需手动点击）。
- **连接**：`config.json` 声明要连的服务，`resolve_mcp_config()` 在启动前把相对路径、Python 解释器、密钥解析为可执行配置，MCP Client 按此 **spawn 子进程**（含 `cwd: ../rag-server` 的 RAG 服务）并拉取工具列表。
- **主链路**：用户提问 → Streamlit → LangGraph ReAct → MCP Client → rag-server 混合检索 → 证据回填 → **Host LLM 生成最终回答**。
- **三种模式**：通用（全量工具自由问答）、旅行规划（高德 + 时间 + RAG + 导出，叠加状态机强流程）、知识库问答（聚焦 RAG 三工具）。

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/app.py` | Host 主入口：Streamlit 界面 + ReAct 循环 |
| `agents-master/config.json` | MCP 服务注册表（4 个默认服务） |
| `agents-master/config/mcp_config.py` | 配置加载与启动前解析 `resolve_mcp_config()` |
| `rag-server/src/mcp_server/server.py` | RAG MCP Server 入口 |
| `rag-server/config/settings.yaml` | RAG 模型与检索配置 |

## 关联

- 仓库结构与模块地图：[[overview/repo-map]]
- 术语解释：[[overview/glossary]]
- 端到端主链路：[[integration/end-to-end]]
- 决策记录：[[decisions/0001-monorepo-split]]
