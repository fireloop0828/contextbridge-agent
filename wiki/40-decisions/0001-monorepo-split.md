---
id: decisions/0001-monorepo-split
title: ADR-0001 monorepo 双项目不合并
tags: [adr, monorepo, architecture]
sources:
  - README.md
  - QA/fast-qa.md
related: [overview/project, host/mcp-client, integration/end-to-end, decisions/0002-dual-venv]
updated: 2026-09-10
---

# ADR-0001 · 为什么 monorepo 双项目不合并

> **TL;DR**：Host（UI + Agent 编排）与 RAG（入库 + 混合检索 + 精排）依赖差异大、演进节奏不同，因此**同仓分两个子项目、运行时两个进程、用 MCP stdio 连接**，而不是合并成一个 Python 工程。

## 背景

系统需要两种截然不同的能力：

- **Host**（`agents-master/`）：Streamlit 界面、LangGraph ReAct 编排、多模式调度、会话与记忆。
- **RAG**（`rag-server/`）：文档解析与切分、向量化、Chroma 向量库、BM25 + Dense 混合检索、精排、评估。

二者的依赖集合几乎没有交集（RAG 侧有 chromadb、embedding 与 cross-encoder 等重型包），迭代节奏也不同（RAG 会独立换检索后端与评估组件）。如果写在一个 Python 工程里，既难隔离依赖，也让「RAG 能不能单独测」变成一个伪命题。

## 选项

| 选项 | 说明 |
| --- | --- |
| A. 单工程单 venv | 一个包内直接 `import` 调用 RAG 代码，函数级调用最省事 |
| B. monorepo 双子项目 + 双 venv + MCP 跨进程（**采用**） | 同一个仓库里两个独立工程，运行时两进程，经 MCP stdio 通信 |
| C. 两个独立仓库 | 彻底解耦，但接口改动需要跨仓协调 |

## 决策

采用 **B**：monorepo 便于一起改接口、联调与统一文档；但**运行时仍是两个进程**，各自用独立虚拟环境，通过 **MCP 协议（stdio）** 连接，两边**互不 `import`**。

关键理由（对齐 `QA/fast-qa.md` 的口述要点）：

1. **依赖隔离**：RAG 需要 chromadb 等重型包，Host 侧重 UI / Agent，双 venv 避免版本冲突。
2. **职责边界**：RAG 可独立测试（`rag-server/scripts/query.py`）、独立演进；Host 换框架不动 RAG。
3. **MCP 协议**：跨进程工具标准，stdio 解耦，两边可独立重启与升级版本。
4. **分工与扩展**：monorepo 便于联调，运行时仍两进程，符合微服务 / MCP 思想。

## 后果

**收益**

- 依赖互不污染，RAG 侧重型包不会拖累 Host 启动。
- 检索链路可不启 Host 单独验证（`rag-server/scripts/query.py`），排障时能把问题二分为「Host/MCP 编排」还是「RAG 内部检索」。
- 工具边界清晰：Host 只能通过 MCP 三工具访问知识库，无法直接碰 chromadb。

**代价**

- **配置解析成本**：`config.json` 里的相对 `cwd`、通用 `python` 命令、`${VAR}` 占位符都要在运行时解析成可执行形态，这一层由 `resolve_mcp_config()` 承担（见 [[host/mcp-client]]）。
- **双 venv 安装成本**：新机器要装两套依赖（见 [[decisions/0002-dual-venv]]）。
- **跨进程调试**：比函数调用麻烦，需借助 stderr 日志与 Trace。

## 关联

- 相关：[[overview/project]]
- 相关：[[host/mcp-client]]
- 相关：[[integration/end-to-end]]
- 相关：[[decisions/0002-dual-venv]]
