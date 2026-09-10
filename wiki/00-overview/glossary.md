---
id: overview/glossary
title: 术语表
tags: [overview, glossary]
sources:
  - wiki/10-host/mcp-client.md
  - rag-server/DEV_SPEC.md
related: [overview/project, integration/end-to-end]
updated: 2026-09-10
---

# 术语表

> **TL;DR**：本页汇总项目高频术语（MCP 三角色、ReAct、RAG 检索链、模式与状态机等）的一句话定义，供阅读其它页面时快速对照。

## 是什么

| 术语 | 一句话定义 |
| --- | --- |
| **MCP** | Model Context Protocol，跨进程接入外部工具的开放协议；本项目用 stdio 传输。 |
| **MCP Host** | 承载智能体的主应用；本项目为 `agents-master/app.py` 的 Streamlit 应用。 |
| **MCP Client** | 代表 Host 连接各 Server、拉取并转发工具调用的连接器；本项目用 `MultiServerMCPClient`。 |
| **MCP Server** | 对外暴露工具能力的服务进程，如 `mcp_server_time.py`、`rag-server`。 |
| **Tool（工具）** | Server 暴露的一条可调用能力，如 `get_current_time`、`query_knowledge_hub`。 |
| **LangGraph** | 用于编排 Agent 推理循环的图框架；本项目用其 ReAct Agent。 |
| **ReAct** | 「推理 → 调工具 → 看结果 → 再推理」的循环范式，直到 LLM 给出最终回答。 |
| **stdio** | 通过标准输入输出管道与子进程通信的传输方式；Host 启动时 spawn Server 子进程。 |
| **SSE / HTTP** | 远程 MCP 传输方式，Server 需独立常驻监听；本项目未用于生产路径。 |
| **venv** | Python 虚拟环境；本项目 Host 与 RAG 各用一套（双 venv）以隔离依赖。 |
| **RAG** | Retrieval-Augmented Generation，检索增强生成：先检索证据，再由 LLM 生成回答。 |
| **Chunk** | 文档切分后的片段，是向量检索与引用的基本单位。 |
| **Embedding** | 把文本转成向量的模型；用于 Dense 语义检索与长期记忆召回。 |
| **Dense 检索** | 基于向量余弦相似度的语义召回，擅长大意与同义表达。 |
| **Sparse / BM25** | 基于关键词词频的召回，擅长精确词项与专有名词。 |
| **RRF** | Reciprocal Rank Fusion，按各路排名（而非分数）融合多路召回结果。 |
| **Rerank（精排）** | 用更强模型对粗排结果重算相关性并重排；失败可 Fallback 回粗排。 |
| **Collection** | 向量库中的知识库集合，检索时需指定；对应 Chroma 的一个库。 |
| **Citation** | 检索返回的证据引用来源，供回答溯源。 |
| **Ingest（入库）** | 文档解析 → 切分 → 增强 → 向量化 → 写入的流水线。 |
| **Mode（模式）** | 通用 / 旅行规划 / 知识库问答三种对话场景，各自裁剪工具与提示词。 |
| **状态机** | 旅行模式中固定阶段顺序的编排机制，位于 LangGraph 之外。 |
| **Fallback** | 组件失败时的降级路径，如精排失败回退 RRF 粗排顺序。 |
| **ADR** | Architecture Decision Record，架构决策记录；见 [[decisions/index]]。 |

## 关联

- 项目定位：[[overview/project]]
- 端到端链路：[[integration/end-to-end]]
