---
id: overview/repo-map
title: 仓库结构与模块地图
tags: [overview, structure, monorepo]
sources:
  - README.md
related: [overview/project, integration/end-to-end]
updated: 2026-09-10
---

# 仓库结构与模块地图

> **TL;DR**：仓库为 monorepo，根下三个顶层目录——`agents-master/`（Host 主应用）、`rag-server/`（RAG 服务）、`QA/`（学习问答记录），外加 `wiki/`（本知识库）；两个子系统各自拥有独立 venv 与配置。

## 是什么

顶层目录与职责：

```
ContextBridge Agent/
├── agents-master/     # 主应用：Streamlit UI + LangGraph ReAct Agent + MCP Host
├── rag-server/        # RAG 服务：文档入库、混合检索、精排、评估 + MCP Server
├── QA/                # Bridge Learn 学习问答与标准答案（学习产物，非知识正文）
├── wiki/              # 本知识库（LLM wiki）
└── README.md          # 仓库门面：定位、结构、快速开始
```

## agents-master/ 模块地图

| 路径 | 职责 |
| --- | --- |
| `app.py` | 主入口：Streamlit 界面 + Agent 初始化与推理 |
| `config.json` | MCP 服务注册表 |
| `config/mcp_config.py` | 配置加载、保存与启动前解析 |
| `modes/` | 模式注册表与扩展（`registry.py`、`types.py`、各模式包） |
| `modes/travel/` | 旅行模式：状态机、handler、pipeline、facts、tool_memory |
| `modes/knowledge_qa/` | 知识库问答模式的系统提示词 |
| `ui/` | 界面分层（chat、sidebar、travel_evidence 等） |
| `prompts/` | 通用系统提示词 |
| `middlewares/` | 中间件 |
| `mcp_server_time.py` | 时间 MCP Server（`get_current_time`） |
| `mcp_server_export.py` | 文档导出 MCP Server（`write_markdown_document`） |
| `export_service.py` | 旅行成稿服务端写盘（省 Token） |
| `memory_store.py` / `memory_recall.py` | 长期记忆 Embedding 与召回 |
| `session_store.py` | 会话归档 |
| `data/outputs/` | 运行时导出的 Markdown |

> 原 `docs/`（设计文档与测试分析）已迁入本 wiki，见 [[host/index]]、[[analysis/index]]。

## rag-server/ 模块地图

| 路径 | 职责 |
| --- | --- |
| `main.py` | RAG MCP Server 启动入口 |
| `dashboard.py` | Streamlit 管理控制台入口 |
| `src/` | 核心实现（ingestion / core / libs / mcp_server / observability） |
| `src/core/query_engine/` | 查询预处理、Dense/Sparse 召回、RRF 融合、精排编排 |
| `src/ingestion/` | 文档入库五阶段流水线 |
| `src/libs/` | 可插拔实现（reranker、embedding 等）+ Factory |
| `src/mcp_server/` | MCP Server 与三工具实现 |
| `config/settings.yaml` | 模型与嵌入配置 |
| `config/collections.yaml` | 知识库 collection 定义 |
| `scripts/` | 运维脚本（ingest、query、evaluate、start_dashboard） |
| `tests/` | unit / integration / e2e 三层测试 |
| `DEV_SPEC.md` | 规格与排期（约 3000 行单体文档，**保留原位存档**；§5「系统架构与模块设计」与 [[rag/architecture]] 互补） |
| `docs/` | 仅存 `知识库扩展计划.md`；其余已迁入本 wiki |

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/app.py` | Host 入口 |
| `rag-server/src/mcp_server/server.py` | RAG MCP Server 入口 |
| `agents-master/config.json` | MCP 注册表 |

## 关联

- 项目定位：[[overview/project]]
- 端到端链路：[[integration/end-to-end]]
- Host 域：[[host/index]]
- RAG 域：[[rag/index]]
