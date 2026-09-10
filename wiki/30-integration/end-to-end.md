---
id: integration/end-to-end
title: 端到端主链路
tags: [integration, end-to-end, rag]
sources:
  - README.md
  - agents-master/README.md
  - QA/fast-qa.md
related: [overview/project, integration/config-and-keys, rag/mcp-server]
updated: 2026-09-10
---

# 端到端主链路

> **TL;DR**：用户提问后，由 Host 的 LangGraph ReAct Agent 决策并调用 MCP 工具；**检索发生在 rag-server**（返回带 Citation 的证据片段），**最终自然语言回答由 Host 的 LLM 生成**——rag-server 不生成面向用户的完整长答案。

## 是什么

一次「知识库问答」的完整链路：

```
用户提问
  → Streamlit (agents-master Host) 接收
  → LangGraph ReAct Agent 决策是否调工具
  → MCP Client（stdio 子进程）调用 rag-server 工具
      ├── list_collections      # 列出知识库集合
      ├── query_knowledge_hub   # 混合检索（Dense + BM25 + RRF + 可选精排）
      └── get_document_summary  # 按 doc_id 取摘要
  → rag-server 返回带 Citation 的证据片段
  → 证据作为 tool result 回到 ReAct 上下文
  → Host LLM 阅读证据，生成用户可见的自然语言回答
```

## 为什么这样设计

- **检索与生成分离**：rag-server 专注「找得准」，返回结构化证据；Host 专注「说得好」，负责对话与归纳。两边职责单一，便于独立优化与测试。
- **chromadb 只在 RAG 进程内**：Host **不能**直接访问向量库，必须经 MCP 工具，保证边界清晰。
- **证据非答案**：工具返回的是 chunk / Citation 等中间证据，不是面向用户的完整长答案——最终语言组织由 Host 完成。

## 怎么实现

1. **提问与决策**：Streamlit 收到消息，ReAct Agent 判断是否需要工具。
2. **工具调用**：MCP Client 经 stdio 把请求转发给 rag-server 子进程。
3. **混合检索**：rag-server 内部执行「预处理 → Dense + BM25 双路召回 → RRF 融合 →（可选）Rerank 精排」，组装 Citation 证据返回。
4. **结果回填**：tool message 追加进 ReAct 上下文，下一轮 LLM 看到完整历史再决策。
5. **生成回答**：Host LLM 归纳证据，输出最终回复；若不再发起 tool call，循环终止。

**三条链路分离**（易混淆，务必区分）：

| 链路 | 解决什么 | 本项目入口 |
| --- | --- | --- |
| 入库 | 解析、切分、向量化后**写入** chromadb | `rag-server/scripts/ingest.py` 或 Dashboard |
| 检索 | 从已有 collection **读取**相关片段 | 对话中 MCP 三工具 |
| 导出 | 把 Agent 成品**写入磁盘**供下载 | `document-export` MCP / `export_service` |

> 入库是重型批处理流水线，不通过对话 MCP 触发；MCP 仅暴露**读库**工具，避免 Agent 误触发写库与长时任务。

## 关键代码锚点

| 位置 | 作用 |
| --- | --- |
| `agents-master/app.py` | ReAct 循环与工具编排 |
| `agents-master/mcp_server_export.py` | 文档导出 MCP |
| `rag-server/src/mcp_server/tools/query_knowledge_hub.py` | 混合检索工具实现 |
| `rag-server/scripts/ingest.py` | 文档入库入口 |

## 关联

- 项目定位：[[overview/project]]
- 配置与密钥：[[integration/config-and-keys]]
- RAG MCP Server：[[rag/mcp-server]]
- 检索链细节：[[rag/architecture]]
